# This project was developed with assistance from AI tools.
"""
LangGraph-based chat agent for mortgage document assistance.

This agent can:
- Answer questions about mortgage regulations and document requirements
- Use RAG to retrieve context from the knowledge base
- (Future) Trigger document processing workflows
- (Future) Help with pending human reviews
"""
import sqlite3
from typing import Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field

from config import config
from prompts import (
    CHAT_ASSISTANT_SYSTEM_PROMPT,
    CHAT_ASSISTANT_RAG_SYSTEM_PROMPT,
    RAG_CONTEXT_TEMPLATE,
    RAG_NO_CONTEXT_TEMPLATE,
)


# Chat state with message history and RAG context
class ChatState(BaseModel):
    """State for the chat agent."""
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    rag_context: str = ""  # Retrieved context for current query
    use_rag: bool = True   # Whether to use RAG retrieval


class ChatAgent:
    """LangGraph-based chat agent with session persistence and optional RAG."""
    
    def __init__(self, checkpoint_db_path: str | None = None):
        """
        Initialize the chat agent.
        
        Args:
            checkpoint_db_path: Path to SQLite DB for checkpointing.
        """
        self.db_path = checkpoint_db_path or config.CHECKPOINT_DB_PATH
        self._db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self._db_conn)
        
        self._llm: ChatOpenAI | None = None
        self._rag_manager = None
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
    
    @property
    def llm(self) -> ChatOpenAI:
        """Lazy initialization of the LLM."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=config.OPENAI_MODEL,
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL,
                temperature=0.7,
            )
        return self._llm
    
    @property
    def rag_manager(self):
        """Lazy initialization of the RAG manager."""
        if self._rag_manager is None:
            from utils.rag import get_rag_manager
            self._rag_manager = get_rag_manager()
        return self._rag_manager
    
    def _build_graph(self) -> StateGraph:
        """Build the chat graph with optional RAG retrieval."""
        workflow = StateGraph(ChatState)
        
        # Add nodes
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("respond", self._respond_node)
        
        # Add edges
        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "respond")
        workflow.add_edge("respond", END)
        
        return workflow
    
    def _retrieve_node(self, state: ChatState) -> dict:
        """Retrieve relevant context from RAG knowledge base."""
        if not state.use_rag:
            return {"rag_context": ""}
        
        # Get the last user message
        user_message = ""
        for msg in reversed(state.messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        if not user_message:
            return {"rag_context": ""}
        
        # Check if RAG has documents
        if not self.rag_manager.has_documents():
            return {"rag_context": ""}
        
        # Retrieve relevant context
        context = self.rag_manager.retrieve_with_context(user_message, k=4)
        return {"rag_context": context}
    
    def _respond_node(self, state: ChatState) -> dict:
        """Generate a response using the LLM."""
        messages = list(state.messages)
        
        # Choose system prompt based on RAG
        if state.use_rag and state.rag_context:
            system_prompt = CHAT_ASSISTANT_RAG_SYSTEM_PROMPT
        else:
            system_prompt = CHAT_ASSISTANT_SYSTEM_PROMPT
        
        # Prepend system message if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        else:
            # Update system message for RAG mode
            messages[0] = SystemMessage(content=system_prompt)
        
        # If RAG context available, augment the last user message
        if state.use_rag and state.rag_context:
            # Find and augment the last human message
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    original_question = messages[i].content
                    augmented_content = RAG_CONTEXT_TEMPLATE.format(
                        context=state.rag_context,
                        question=original_question
                    )
                    messages[i] = HumanMessage(content=augmented_content)
                    break
        elif state.use_rag and not state.rag_context:
            # RAG enabled but no context found - add note
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    original_question = messages[i].content
                    augmented_content = RAG_NO_CONTEXT_TEMPLATE.format(
                        question=original_question
                    )
                    messages[i] = HumanMessage(content=augmented_content)
                    break
        
        # Generate response
        response = self.llm.invoke(messages)
        
        return {"messages": [response], "rag_context": ""}  # Clear context after use
    
    def chat(self, message: str, thread_id: str, use_rag: bool = True) -> str:
        """
        Send a message and get a response.
        
        Args:
            message: User's message
            thread_id: Session/thread ID for persistence
            use_rag: Whether to use RAG retrieval for this message
            
        Returns:
            Assistant's response text
        """
        invoke_config = {"configurable": {"thread_id": thread_id}}
        
        result = self.compiled_graph.invoke(
            {
                "messages": [HumanMessage(content=message)],
                "use_rag": use_rag,
            },
            invoke_config
        )
        
        # Get the last AI message
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                return msg.content
        
        return "I apologize, but I couldn't generate a response."
    
    def get_history(self, thread_id: str) -> list[dict]:
        """
        Get chat history for a session.
        
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
                return [
                    {
                        "role": "assistant" if isinstance(m, AIMessage) else "user" if isinstance(m, HumanMessage) else "system",
                        "content": m.content
                    }
                    for m in messages
                    if not isinstance(m, SystemMessage)
                ]
        except Exception:
            pass
        
        return []
    
    def list_sessions(self) -> list[str]:
        """
        List all chat session thread IDs.
        
        Returns:
            List of thread IDs that have chat history
        """
        try:
            cursor = self._db_conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE 'chat-%'"
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []
    
    def rag_has_documents(self) -> bool:
        """Check if the RAG knowledge base has any documents."""
        return self.rag_manager.has_documents()


# Singleton instance
_chat_agent: ChatAgent | None = None


def get_chat_agent() -> ChatAgent:
    """Get or create the singleton chat agent instance."""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatAgent()
    return _chat_agent
