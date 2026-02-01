# This project was developed with assistance from AI tools.
"""
LangGraph-based chat agent with mortgage expertise and persistent memory.

A general-purpose conversational assistant that specializes in mortgage
and real estate knowledge. Features:
- ReAct-style agent that autonomously decides when to use tools
- Persistent user facts (loan preferences, status, etc.)
- Semantic search over past conversations for recall
"""
import logging
import os
import sqlite3
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from config import config
from prompts import CHAT_AGENT_WITH_TOOLS_PROMPT, USER_CONTEXT_TEMPLATE

logger = logging.getLogger(__name__)


class ChatState(BaseModel):
    """State for the chat agent."""
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    
    # Guardrail state
    input_blocked: bool = False
    input_block_reason: str | None = None
    output_blocked: bool = False
    guardrail_warnings: list[str] = Field(default_factory=list)


class ChatAgent:
    """
    LangGraph-based chat agent with tool-calling capabilities and persistent memory.
    
    The agent can autonomously decide when to:
    - Search the knowledge base for regulations/requirements
    - Recall past conversations with this user
    
    It also maintains:
    - User facts (extracted from conversations)
    - Conversation memory (for semantic search)
    """
    
    def __init__(self, checkpoint_db_path: str | None = None):
        """
        Initialize the chat agent.
        
        Args:
            checkpoint_db_path: Path to SQLite DB for chat history persistence.
        """
        self.db_path = checkpoint_db_path or config.APP_DATA_DB_PATH
        self._db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self._db_conn)
        
        self._llm: ChatOpenAI | None = None
        self._rag_manager = None
        self._facts_store = None
        self._conversation_memory = None
        
        # Current context (set per-request for tool access)
        self._current_user_id: str | None = None
        self._current_thread_id: str | None = None
        self._current_user_email: str | None = None
        
        # Pending download (set by tool, consumed by frontend)
        self._pending_download: dict | None = None
        
        # Pending email (set by draft_email tool, consumed by frontend)
        self._pending_email: dict | None = None
        self._email_count: int = 0
        
        # Build authenticated graph with all tools (uses checkpointer)
        self._tools = self._get_tools(anonymous=False)
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
        
        # Build anonymous graph with limited tools (no checkpointer - no history saved)
        self._anonymous_tools = self._get_tools(anonymous=True)
        self._anonymous_graph = self._build_graph(tools=self._anonymous_tools)
        self._anonymous_compiled = self._anonymous_graph.compile()
    
    @property
    def llm(self) -> ChatOpenAI:
        """Lazy initialization of the LLM."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=config.OPENAI_MODEL,
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL,
                temperature=config.CHAT_TEMPERATURE,
            )
        return self._llm
    
    @property
    def rag_manager(self):
        """Lazy initialization of the RAG manager."""
        if self._rag_manager is None:
            try:
                from utils.rag import get_rag_manager
                self._rag_manager = get_rag_manager()
            except Exception as e:
                logger.warning(f"RAG unavailable: {e}")
                return None
        return self._rag_manager
    
    @property
    def facts_store(self):
        """Lazy initialization of the user facts store."""
        if self._facts_store is None:
            try:
                from utils.user_memory import get_facts_store
                self._facts_store = get_facts_store()
            except Exception as e:
                logger.warning(f"Facts store unavailable: {e}")
                return None
        return self._facts_store
    
    @property
    def conversation_memory(self):
        """Lazy initialization of conversation memory."""
        if self._conversation_memory is None:
            try:
                from utils.user_memory import get_conversation_memory
                self._conversation_memory = get_conversation_memory()
            except Exception as e:
                logger.warning(f"Conversation memory unavailable: {e}")
                return None
        return self._conversation_memory
    
    def _extract_user_id(self, thread_id: str) -> str:
        """
        Extract user ID from thread ID.
        
        Thread IDs follow pattern: "{user_id}-chat-{timestamp}"
        e.g., "borrower-chat-20260131-120707" -> "borrower"
        """
        if "-chat-" in thread_id:
            return thread_id.split("-chat-")[0]
        return "anonymous"
    
    def _create_tool_context(self):
        """Create the context object passed to tool factories."""
        from agents.tools import ToolContext
        
        return ToolContext(
            get_user_id=lambda: self._current_user_id,
            get_thread_id=lambda: self._current_thread_id,
            get_user_email=lambda: self._current_user_email,
            get_rag_manager=lambda: self.rag_manager,
            get_facts_store=lambda: self.facts_store,
            get_conversation_memory=lambda: self.conversation_memory,
            set_pending_download=lambda d: setattr(self, '_pending_download', d),
            set_pending_email=lambda e: setattr(self, '_pending_email', e),
            get_email_count=lambda: self._email_count,
        )
    
    def _get_tools(self, anonymous: bool = False) -> list:
        """
        Get the list of tools available to the agent.
        
        Args:
            anonymous: If True, only include public tools (no user-specific tools)
        """
        from agents.tools import get_all_tools
        
        context = self._create_tool_context()
        return get_all_tools(context, anonymous=anonymous)
    
    def _build_system_prompt(self, user_id: str) -> str:
        """
        Build the system prompt with user context if available.
        
        Args:
            user_id: The user's identifier
            
        Returns:
            Complete system prompt with user facts injected
        """
        base_prompt = CHAT_AGENT_WITH_TOOLS_PROMPT
        
        # Add user facts if available
        if self.facts_store:
            try:
                facts_summary = self.facts_store.get_facts_summary(user_id)
                if facts_summary:
                    user_context = USER_CONTEXT_TEMPLATE.format(user_facts=facts_summary)
                    base_prompt = base_prompt + "\n" + user_context
            except Exception as e:
                logger.warning(f"Failed to load user facts: {e}")
        
        return base_prompt
    
    def _build_graph(self, tools: list | None = None) -> StateGraph:
        """Build the chat graph with guardrails and tool-calling capabilities."""
        tools = tools or self._tools
        llm_with_tools = self.llm.bind_tools(tools)
        
        from utils.guardrails import (
            create_input_guardrails_node,
            create_intent_evaluator_node,
            create_output_guardrails_node,
        )
        
        input_guardrails_node = create_input_guardrails_node(
            human_message_class=HumanMessage,
            mask_pii=config.GUARDRAILS_MASK_PII,
            block_on_pii=config.GUARDRAILS_BLOCK_PII,
        )
        
        intent_evaluator_node = create_intent_evaluator_node(
            human_message_class=HumanMessage,
        )
        
        output_guardrails_node = create_output_guardrails_node(
            ai_message_class=AIMessage,
            get_system_prompt=lambda: self._build_system_prompt(self._current_user_id or "anonymous"),
            mask_output_pii=config.GUARDRAILS_MASK_OUTPUT_PII,
        )
        
        def agent_node(state: ChatState) -> dict:
            """Process messages and may call tools."""
            messages = list(state.messages)
            system_prompt = self._build_system_prompt(self._current_user_id or "anonymous")
            
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_prompt)] + messages
            else:
                messages[0] = SystemMessage(content=system_prompt)
            
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}
        
        def after_input_guardrails(state: ChatState) -> str:
            return "blocked" if state.input_blocked else "intent_eval"
        
        def after_intent_eval(state: ChatState) -> str:
            return "blocked" if state.input_blocked else "agent"
        
        def should_continue(state: ChatState) -> str:
            last_message = state.messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return "output_guardrails"
        
        # Build graph: input_guardrails → intent_eval → agent ↔ tools → output_guardrails
        workflow = StateGraph(ChatState)
        
        workflow.add_node("input_guardrails", input_guardrails_node)
        workflow.add_node("intent_eval", intent_evaluator_node)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", ToolNode(tools))
        workflow.add_node("output_guardrails", output_guardrails_node)
        
        workflow.add_edge(START, "input_guardrails")
        workflow.add_conditional_edges(
            "input_guardrails",
            after_input_guardrails,
            {"blocked": END, "intent_eval": "intent_eval"}
        )
        workflow.add_conditional_edges(
            "intent_eval",
            after_intent_eval,
            {"blocked": END, "agent": "agent"}
        )
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {"tools": "tools", "output_guardrails": "output_guardrails"}
        )
        workflow.add_edge("tools", "agent")
        workflow.add_edge("output_guardrails", END)
        
        return workflow
    
    def _store_exchange_and_extract_facts(
        self,
        user_id: str,
        thread_id: str,
        user_message: str,
        assistant_response: str
    ):
        """
        Store the conversation exchange and extract any facts.
        
        This is called after each successful response.
        """
        # Store in conversation memory for recall
        if config.MEMORY_STORE_CONVERSATIONS and self.conversation_memory:
            try:
                self.conversation_memory.store_exchange(
                    user_id=user_id,
                    thread_id=thread_id,
                    user_message=user_message,
                    assistant_response=assistant_response
                )
            except Exception as e:
                logger.warning(f"Failed to store conversation: {e}")
        
        # Extract facts from the exchange
        if config.MEMORY_EXTRACT_FACTS and self.facts_store:
            try:
                from utils.user_memory import extract_facts_from_exchange
                
                existing_facts = self.facts_store.get_facts(user_id)
                extracted = extract_facts_from_exchange(
                    llm=self.llm,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    existing_facts=existing_facts
                )
                
                # Store facts that meet confidence threshold
                for fact in extracted:
                    confidence = fact.get("confidence", 0.0)
                    if confidence >= config.MEMORY_FACT_MIN_CONFIDENCE:
                        self.facts_store.set_fact(
                            user_id=user_id,
                            fact_type=fact["fact_type"],
                            fact_value=fact["fact_value"],
                            confidence=confidence,
                            source_thread_id=thread_id
                        )
                        logger.info(f"Extracted fact for {user_id}: {fact['fact_type']}={fact['fact_value']}")
            except Exception as e:
                logger.warning(f"Failed to extract facts: {e}")
    
    def _create_langfuse_handler(self, session_id: str, metadata: dict):
        """
        Create LangFuse callback handler if enabled.
        
        Returns:
            LangfuseCallbackHandler or None if disabled/unavailable
        """
        if not os.getenv('LANGFUSE_SECRET_KEY'):
            return None
        try:
            from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
            return LangfuseCallbackHandler(session_id=session_id, metadata=metadata)
        except ImportError:
            logger.warning("LangFuse enabled but package not available")
            return None
    
    def _extract_response_text(self, result: dict) -> str:
        """
        Extract the final AI response from graph result.
        
        Handles blocked requests and finds the last non-tool AI message.
        """
        if result.get("input_blocked"):
            reason = result.get("input_block_reason", "unknown")
            logger.info(f"Request blocked by guardrails: {reason}")
            return "I'm not able to process that request. Please try rephrasing."
        
        # Log any guardrail warnings
        for warning in result.get("guardrail_warnings", []):
            logger.info(f"Guardrail: {warning}")
        
        # Find the last AI message that isn't a tool call
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and not getattr(msg, 'tool_calls', None):
                return msg.content
        
        return "I apologize, but I couldn't generate a response."
    
    def _build_messages_from_history(self, session_messages: list[dict] | None) -> list:
        """
        Convert session message history to LangChain message objects.
        
        Args:
            session_messages: List of dicts with 'role' and 'content'
            
        Returns:
            List of HumanMessage/AIMessage objects
        """
        messages = []
        if session_messages:
            for msg in session_messages:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        return messages
    
    def chat(self, message: str, thread_id: str) -> str:
        """
        Send a message and get a response.
        
        The LangGraph workflow handles guardrails, agent processing, and tool calls.
        After responding, stores the exchange and extracts any user facts.
        
        Args:
            message: User's message
            thread_id: Session/thread ID for persistence
            
        Returns:
            Assistant's response text
        """
        self._current_user_id = self._extract_user_id(thread_id)
        self._current_thread_id = thread_id
        
        invoke_config = {"configurable": {"thread_id": thread_id}}
        
        handler = self._create_langfuse_handler(
            session_id=self._current_user_id,
            metadata={"agent": "chat_agent", "thread_id": thread_id, "user_id": self._current_user_id}
        )
        if handler:
            invoke_config["callbacks"] = [handler]
        
        try:
            result = self.compiled_graph.invoke(
            {"messages": [HumanMessage(content=message)]},
                    invoke_config
            )
        
            response_text = self._extract_response_text(result)
            
            # Store exchange and extract facts for authenticated users
            if not result.get("input_blocked"):
                self._store_exchange_and_extract_facts(
                    user_id=self._current_user_id,
                    thread_id=thread_id,
                    user_message=message,
                    assistant_response=response_text
                )
            
            return response_text
            
        finally:
            self._current_user_id = None
            self._current_thread_id = None
    
    def chat_anonymous(self, message: str, session_messages: list[dict] | None = None) -> str:
        """
        Send a message as an anonymous (unauthenticated) user.
        
        Anonymous users have limited tools (RAG, property, web search, economic data)
        and no history persistence or personal data access.
        
        Args:
            message: User's message
            session_messages: Optional list of previous messages for context
            
        Returns:
            Assistant's response text
        """
        self._current_user_id = "anonymous"
        self._current_thread_id = None
        
        invoke_config = {}
        
        handler = self._create_langfuse_handler(
            session_id="anonymous-landing",
            metadata={"agent": "chat_agent", "mode": "anonymous"}
        )
        if handler:
            invoke_config["callbacks"] = [handler]
        
        try:
            messages = self._build_messages_from_history(session_messages)
            messages.append(HumanMessage(content=message))
            
            result = self._anonymous_compiled.invoke(
                {"messages": messages},
                invoke_config
            )
            
            return self._extract_response_text(result)
            
        finally:
            self._current_user_id = None
            self._current_thread_id = None
    
    def get_history(self, thread_id: str) -> list[dict]:
        """
        Get chat history for a session (excluding tool calls).
        
        Args:
            thread_id: Session/thread ID
            
        Returns:
            List of message dicts with 'role' and 'content'
        """
        invoke_config = {"configurable": {"thread_id": thread_id}}
        
        try:
            state = self.compiled_graph.get_state(invoke_config)
            if state and state.values and "messages" in state.values:
                messages = state.values["messages"]
                history = []
                for m in messages:
                    if isinstance(m, SystemMessage):
                        continue
                    if isinstance(m, AIMessage):
                        if m.tool_calls:
                            continue
                        history.append({"role": "assistant", "content": m.content})
                    elif isinstance(m, HumanMessage):
                        history.append({"role": "user", "content": m.content})
                return history
        except Exception:
            pass
        
        return []
    
    def list_sessions(self, user_prefix: str | None = None) -> list[str]:
        """
        List chat session thread IDs.
        
        Args:
            user_prefix: If provided, only return sessions for this user prefix
        
        Returns:
            List of thread IDs that have chat history
        """
        try:
            if user_prefix:
                cursor = self._db_conn.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE ?",
                    (f"{user_prefix}chat-%",)
                )
            else:
                ursor = self._db_conn.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE '%chat-%'"
                )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []
    
    def get_user_facts(self, user_id: str) -> dict:
        """
        Get all stored facts for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict of fact_type -> fact details
        """
        if self.facts_store:
            return self.facts_store.get_facts(user_id)
        return {}
    
    def clear_user_memory(self, user_id: str) -> dict:
        """
        Clear all memory for a user (facts and conversation memory).
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with counts of cleared items
        """
        result = {"facts_cleared": 0, "conversations_cleared": 0}
        
        if self.facts_store:
            result["facts_cleared"] = self.facts_store.clear_user(user_id)
        
        if self.conversation_memory:
            result["conversations_cleared"] = self.conversation_memory.clear_user(user_id)
        
        return result
    
    def rag_has_documents(self) -> bool:
        """Check if the RAG knowledge base has any documents."""
        if self._rag_manager is None:
            return False
        try:
            return self._rag_manager.has_documents()
        except Exception:
            return False
    
    def rag_available(self) -> bool:
        """Check if RAG system is available."""
        return self._rag_manager is not None
    
    def get_pending_download(self) -> dict | None:
        """
        Get and clear any pending download set by the download tool.
        
        Returns:
            Download info dict with 'report_id', 'filename', 'filepath' or None
        """
        download = self._pending_download
        self._pending_download = None
        return download
    
    def get_pending_email(self) -> dict | None:
        """
        Get any pending email draft (does NOT clear it - call send_pending_email or clear_pending_email).
        
        Returns:
            Email info dict with 'to', 'subject', 'body', 'user_id' or None
        """
        return self._pending_email
    
    def clear_pending_email(self):
        """Clear the pending email without sending."""
        self._pending_email = None
    
    def send_pending_email(self) -> str:
        """
        Actually send the pending email via Maileroo API.
        
        Returns:
            Success/failure message
        """
        if not self._pending_email:
            return "No email pending to send."
        
        from utils.email import is_available, get_client
        
        if not is_available():
            self._pending_email = None
            return "Email service is not configured."
        
        try:
            client = get_client()
            to_email = self._pending_email["to"]
            result = client.send(
                to_email=to_email,
                subject=self._pending_email["subject"],
                body=self._pending_email["body"],
            )
            
            if result.success:
                self._email_count += 1
                self._pending_email = None
                return f"Email sent successfully to {to_email}."
            else:
                self._pending_email = None
                return f"Failed to send email: {result.error}"
                
        except Exception as e:
            logger.error(f"Email send error: {e}")
            self._pending_email = None
            return f"Failed to send email: {str(e)}"
    
    def set_user_email(self, email: str | None):
        """Set the current user's email (called by frontend before chat)."""
        self._current_user_email = email


# Singleton instance
_chat_agent: ChatAgent | None = None


def get_chat_agent() -> ChatAgent:
    """Get or create the singleton chat agent instance."""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatAgent()
    return _chat_agent
