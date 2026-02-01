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
from langchain_core.tools import tool
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
        
        # Pending download (set by tool, consumed by frontend)
        self._pending_download: dict | None = None
        
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
    
    def _get_tools(self, anonymous: bool = False) -> list:
        """
        Get the list of tools available to the agent.
        
        Args:
            anonymous: If True, only include public tools (RAG, web search)
        """
        from prompts import TOOL_SEARCH_KNOWLEDGE_BASE
        
        tools = []
        
        @tool(description=TOOL_SEARCH_KNOWLEDGE_BASE)
        def search_knowledge_base(query: str) -> str:
            rag = self.rag_manager
            if rag is None:
                return "Knowledge base is not available. Answering from general knowledge."
            
            try:
                if not rag.has_documents():
                    return "Knowledge base is empty. Answering from general knowledge."
                
                context = rag.retrieve_with_context(query, k=config.RAG_TOP_K)
                if not context:
                    return "No relevant information found in the knowledge base."
                return context
            except Exception as e:
                logger.warning(f"Knowledge base search failed: {e}")
                return "Knowledge base search failed. Answering from general knowledge."
        
        tools.append(search_knowledge_base)
        
        # User-specific tools (only for authenticated users)
        if not anonymous:
            from prompts import (
                TOOL_RECALL_CONVERSATIONS,
                TOOL_GET_USER_FACTS,
                TOOL_GET_MY_REPORTS,
                TOOL_GET_MY_DOCUMENTS,
                TOOL_PREPARE_DOWNLOAD,
            )
            
            @tool(description=TOOL_RECALL_CONVERSATIONS)
            def recall_past_conversations(query: str) -> str:
                memory = self.conversation_memory
                if memory is None:
                    return "Conversation memory is not available."
                
                user_id = self._current_user_id
                if not user_id:
                    return "Unable to identify user for memory search."
                
                try:
                    result = memory.search_formatted(
                        user_id=user_id,
                        query=query,
                        k=config.MEMORY_RECALL_TOP_K,
                        exclude_thread=self._current_thread_id
                    )
                    return result
                except Exception as e:
                    logger.warning(f"Conversation memory search failed: {e}")
                    return "Failed to search conversation memory."
            
            tools.append(recall_past_conversations)
            
            @tool(description=TOOL_GET_USER_FACTS)
            def get_my_stored_facts() -> str:
                user_id = self._current_user_id
                if not user_id:
                    return "Unable to identify user."
                
                facts_store = self.facts_store
                if facts_store is None:
                    return "User memory is not available."
                
                try:
                    facts = facts_store.get_facts(user_id)
                    if not facts:
                        return "No facts stored about you yet. As we chat, I'll remember important details you share."
                    
                    lines = [f"Here's what I remember about you ({len(facts)} facts):"]
                    for fact_type, details in facts.items():
                        label = fact_type.replace("_", " ").title()
                        lines.append(f"- {label}: {details['value']}")
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning(f"Failed to retrieve user facts: {e}")
                    return "Failed to retrieve stored facts."
            
            tools.append(get_my_stored_facts)
            
            @tool(description=TOOL_GET_MY_REPORTS)
            def get_my_reports() -> str:
                user_id = self._current_user_id
                if not user_id:
                    return "Unable to identify user."
                
                try:
                    from utils.report_store import get_report_store
                    store = get_report_store()
                    reports = store.get_reports(owner_id=user_id)
                    
                    if not reports:
                        return "You don't have any reports yet. Upload and process documents to generate a report."
                    
                    lines = [f"You have {len(reports)} report(s):\n"]
                    
                    for r in reports[:5]:
                        date = r["created_at"][:10]
                        doc_count = r.get("document_count", 0)
                        lines.append(f"Report from {date} ({doc_count} documents):")
                        
                        summary = r.get("classification_summary")
                        if summary:
                            for category, data in sorted(summary.items()):
                                count = data.get("count", 0)
                                docs = data.get("documents", [])
                                lines.append(f"  {category}: {count} document(s)")
                                for doc in docs[:3]:
                                    conf = doc.get("confidence", 0)
                                    reviewed = " [human reviewed]" if doc.get("human_reviewed") else ""
                                    lines.append(f"    - {doc['name']} ({conf:.0%}){reviewed}")
                                if len(docs) > 3:
                                    lines.append(f"    ... and {len(docs) - 3} more")
                        else:
                            lines.append("  (No classification details available)")
                        lines.append("")
                    
                    if len(reports) > 5:
                        lines.append(f"... and {len(reports) - 5} older report(s)")
                    
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning(f"Failed to retrieve reports: {e}")
                    return "Failed to retrieve report information."
            
            tools.append(get_my_reports)
            
            @tool(description=TOOL_GET_MY_DOCUMENTS)
            def get_my_documents() -> str:
                user_id = self._current_user_id
                if not user_id:
                    return "Unable to identify user."
                
                try:
                    from pathlib import Path
                    from utils.document_cache import DocumentCache
                    
                    cache = DocumentCache()
                    
                    uploads_dir = Path("uploads") / user_id
                    if not uploads_dir.exists():
                        return "You haven't uploaded any documents yet."
                    
                    unique_docs = {}
                    batch_dirs = sorted(uploads_dir.glob("batch-*"), reverse=True)
                    
                    for batch_dir in batch_dirs:
                        for pdf in batch_dir.glob("*.pdf"):
                            if pdf.name in unique_docs:
                                continue
                            
                            try:
                                content_hash = cache.compute_hash(pdf)
                                classified = cache.get_classification(content_hash)
                                if classified:
                                    unique_docs[pdf.name] = {
                                        "name": pdf.name,
                                        "category": classified.category,
                                        "confidence": classified.confidence,
                                    }
                                else:
                                    unique_docs[pdf.name] = {
                                        "name": pdf.name,
                                        "category": "Not yet classified",
                                        "confidence": 0,
                                    }
                            except Exception:
                                unique_docs[pdf.name] = {
                                    "name": pdf.name,
                                    "category": "Unknown",
                                    "confidence": 0,
                                }
                    
                    documents = list(unique_docs.values())
                    
                    if not documents:
                        return "No documents found in your upload history."
                    
                    by_category = {}
                    for doc in documents:
                        cat = doc["category"]
                        if cat not in by_category:
                            by_category[cat] = []
                        by_category[cat].append(doc["name"])
                    
                    lines = [f"You have {len(documents)} unique document(s) on file:"]
                    for category, files in sorted(by_category.items()):
                        lines.append(f"\n{category} ({len(files)}):")
                        for f in sorted(files):
                            conf = next((d["confidence"] for d in documents if d["name"] == f), 0)
                            if conf > 0:
                                lines.append(f"  - {f} ({conf:.0%} confidence)")
                            else:
                                lines.append(f"  - {f}")
                    
                    lines.append(f"\nDocuments from {len(batch_dirs)} upload session(s).")
                    
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning(f"Failed to retrieve documents: {e}")
                    return "Failed to retrieve document information."
            
            tools.append(get_my_documents)
            
            @tool(description=TOOL_PREPARE_DOWNLOAD)
            def prepare_report_download(report_id: int | None = None, confirmed: bool = False) -> str:
                user_id = self._current_user_id
                if not user_id:
                    return "Unable to identify user."
                
                try:
                    from utils.report_store import get_report_store
                    from config import config
                    
                    store = get_report_store()
                    
                    if report_id is None:
                        reports = store.get_reports(owner_id=user_id)
                        if not reports:
                            return "You don't have any reports to download."
                        report = reports[0]
                        report_id = report["id"]
                    else:
                        report = store.get_report_by_id(report_id, owner_id=user_id)
                        if not report:
                            return "Report not found or you don't have access to it."
                    
                    report_path = config.OUTPUT_REPORT_DIR / report["filename"]
                    if not report_path.exists():
                        return "The report file is no longer available."
                    
                    if not confirmed:
                        date = report["created_at"][:10]
                        doc_count = report.get("document_count", 0)
                        
                        details = [
                            f"I found this report ready for download:",
                            f"",
                            f"  Report ID: {report_id}",
                            f"  Date: {date}",
                            f"  Documents: {doc_count}",
                            f"  Filename: {report['filename']}",
                            f"",
                            f"Would you like me to prepare this report for download?",
                        ]
                        return "\n".join(details)
                    else:
                        self._pending_download = {
                            "report_id": report_id,
                            "filename": report["filename"],
                            "filepath": str(report_path),
                        }
                        return f"Your report '{report['filename']}' is ready. A download button will appear below."
                
                except Exception as e:
                    logger.warning(f"Failed to prepare download: {e}")
                    return "Failed to prepare report for download."
            
            tools.append(prepare_report_download)
        
        # Property Data Tools (if BatchData API key is configured)
        from utils.batchdata import is_available as batchdata_available
        
        if batchdata_available():
            from prompts import (
                TOOL_VERIFY_ADDRESS,
                TOOL_PROPERTY_LOOKUP,
                TOOL_SEARCH_PROPERTIES,
                TOOL_GEOCODE_ADDRESS,
            )
            from utils.batchdata import get_batchdata_client
            
            @tool(description=TOOL_VERIFY_ADDRESS)
            def verify_property_address(street: str, city: str, state: str, zip_code: str) -> str:
                try:
                    client = get_batchdata_client()
                    result = client.verify_address(street, city, state, zip_code)
                    if result and result.is_valid:
                        return result.format_display()
                    return "Address could not be verified."
                except Exception as e:
                    logger.warning(f"Address verification failed: {e}")
                    return f"Unable to verify address: {str(e)}"
            
            tools.append(verify_property_address)
            
            @tool(description=TOOL_PROPERTY_LOOKUP)
            def get_property_details(street: str, city: str, state: str, zip_code: str | None = None) -> str:
                try:
                    client = get_batchdata_client()
                    result = client.lookup_property(street, city, state, zip_code)
                    if result:
                        return result.format_display()
                    return "No property data found for this address."
                except Exception as e:
                    logger.warning(f"Property lookup failed: {e}")
                    return f"Unable to retrieve property details: {str(e)}"
            
            tools.append(get_property_details)
            
            @tool(description=TOOL_SEARCH_PROPERTIES)
            def search_properties(
                query: str | None = None,
                city: str | None = None,
                state: str | None = None,
                zip_code: str | None = None,
                min_price: int | None = None,
                max_price: int | None = None,
                property_type: str | None = None,
                min_beds: int | None = None,
                max_beds: int | None = None,
                limit: int = 10,
            ) -> str:
                if not any([query, city, state, zip_code]):
                    return "Please provide a location query, city/state, or ZIP code to search."
                
                try:
                    client = get_batchdata_client()
                    results = client.search_properties(
                        query=query,
                        city=city,
                        state=state,
                        zip_code=zip_code,
                        min_price=min_price,
                        max_price=max_price,
                        property_type=property_type,
                        min_beds=min_beds,
                        max_beds=max_beds,
                        limit=limit,
                    )
                    if not results:
                        return "No properties found matching your criteria."
                    
                    lines = [f"Found {len(results)} properties:"]
                    for i, prop in enumerate(results, 1):
                        lines.append(f"{i}. {prop.format_line()}")
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning(f"Property search failed: {e}")
                    return f"Unable to search properties: {str(e)}"
            
            tools.append(search_properties)
            
            @tool(description=TOOL_GEOCODE_ADDRESS)
            def geocode_address(address: str) -> str:
                try:
                    client = get_batchdata_client()
                    result = client.geocode_address(address)
                    if result:
                        return result.format_display()
                    return "Could not geocode this address."
                except Exception as e:
                    logger.warning(f"Geocoding failed: {e}")
                    return f"Unable to geocode address: {str(e)}"
            
            tools.append(geocode_address)
            
            logger.info("BatchData property tools enabled")
        else:
            logger.info("BatchData API key not configured - property tools disabled")
        
        # Web Search Tools (only if Brave Search API key is configured)
        from utils.brave_search import is_available as brave_available
        
        if brave_available():
            from prompts import TOOL_WEB_SEARCH
            from utils.brave_search import get_brave_search_client
            
            @tool(description=TOOL_WEB_SEARCH)
            def web_search(query: str, count: int = 5, freshness: str | None = None) -> str:
                try:
                    client = get_brave_search_client()
                    result = client.search(query=query, count=count, freshness=freshness)
                    return result.format_display()
                except Exception as e:
                    logger.warning(f"Web search failed: {e}")
                    return f"Unable to perform web search: {str(e)}"
            
            tools.append(web_search)
            
            logger.info("Brave Search web search tool enabled")
        else:
            logger.info("Brave Search API key not configured - web search disabled")
        
        # FRED Economic Data Tools (if API key is configured)
        from utils.fred import is_available as fred_available
        
        if fred_available():
            from prompts import (
                TOOL_FRED_GET_SERIES,
                TOOL_FRED_SEARCH,
                TOOL_FRED_MORTGAGE_RATES,
            )
            from utils.fred import get_fred_client
            
            @tool(description=TOOL_FRED_GET_SERIES)
            def fred_get_series(
                series_id: str,
                limit: int = 1,
                start_date: str | None = None,
                end_date: str | None = None,
            ) -> str:
                try:
                    client = get_fred_client()
                    if limit == 1 and not start_date and not end_date:
                        result = client.get_latest_value(series_id)
                        if result:
                            return result.format_latest()
                        return f"No data found for series {series_id}."
                    else:
                        result = client.get_observations(
                            series_id,
                            start_date=start_date,
                            end_date=end_date,
                            limit=limit,
                        )
                        if result:
                            return result.format_display()
                        return f"No data found for series {series_id}."
                except Exception as e:
                    logger.warning(f"FRED get_series failed: {e}")
                    return f"Unable to retrieve economic data: {str(e)}"
            
            tools.append(fred_get_series)
            
            @tool(description=TOOL_FRED_SEARCH)
            def fred_search_series(search_text: str, limit: int = 5) -> str:
                try:
                    client = get_fred_client()
                    result = client.search_series(search_text, limit=limit)
                    return result.format_display()
                except Exception as e:
                    logger.warning(f"FRED search failed: {e}")
                    return f"Unable to search economic data series: {str(e)}"
            
            tools.append(fred_search_series)
            
            @tool(description=TOOL_FRED_MORTGAGE_RATES)
            def fred_mortgage_rates() -> str:
                try:
                    client = get_fred_client()
                    return client.get_mortgage_rates()
                except Exception as e:
                    logger.warning(f"FRED mortgage rates failed: {e}")
                    return f"Unable to retrieve mortgage rates: {str(e)}"
            
            tools.append(fred_mortgage_rates)
            
            logger.info("FRED economic data tools enabled")
        else:
            logger.info("FRED API key not configured - economic data tools disabled")
        
        return tools
    
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
    
    def chat(self, message: str, thread_id: str) -> str:
        """
        Send a message and get a response.
        
        The LangGraph workflow handles:
        - Layer 1: Input guardrails (sanitization, PII masking)
        - Agent processing with tool calls
        - Layer 3: Output guardrails (leak detection, PII masking)
        
        After responding, it stores the exchange and extracts any user facts.
        
        Args:
            message: User's message
            thread_id: Session/thread ID for persistence
            
        Returns:
            Assistant's response text
        """
        # Set current context for tools
        self._current_user_id = self._extract_user_id(thread_id)
        self._current_thread_id = thread_id
        
        invoke_config = {"configurable": {"thread_id": thread_id}}
        
        # Add LangFuse callback if enabled (traces show guardrail nodes)
        langfuse_enabled = bool(os.getenv('LANGFUSE_SECRET_KEY'))
        if langfuse_enabled:
            try:
                from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
                langfuse_handler = LangfuseCallbackHandler(
                    session_id=self._current_user_id,
                    metadata={
                        "agent": "chat_agent",
                        "thread_id": thread_id,
                        "user_id": self._current_user_id,
                    }
                )
                invoke_config["callbacks"] = [langfuse_handler]
            except ImportError:
                logger.warning("LangFuse enabled but langfuse package not available")
        
        try:
            # Invoke the graph - guardrails are handled as nodes
            result = self.compiled_graph.invoke(
                {"messages": [HumanMessage(content=message)]},
                invoke_config
            )
            
            # Check if input was blocked by guardrails
            if result.get("input_blocked"):
                logger.info(f"Request blocked by input guardrails: {result.get('input_block_reason')}")
                return "I'm not able to process that request. Please try rephrasing."
            
            # Log any guardrail warnings
            for warning in result.get("guardrail_warnings", []):
                logger.info(f"Guardrail: {warning}")
            
            # Get the last AI message (not a tool message)
            response_text = None
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and not getattr(msg, 'tool_calls', None):
                    response_text = msg.content
                    break
            
            if response_text is None:
                response_text = "I apologize, but I couldn't generate a response."
            
            # Store exchange and extract facts (async would be better but keeping simple)
            self._store_exchange_and_extract_facts(
                user_id=self._current_user_id,
                thread_id=thread_id,
                user_message=message,  # Store original message for memory
                assistant_response=response_text
            )
            
            return response_text
            
        finally:
            # Clear context
            self._current_user_id = None
            self._current_thread_id = None
    
    def chat_anonymous(self, message: str, session_messages: list[dict] | None = None) -> str:
        """
        Send a message as an anonymous (unauthenticated) user.
        
        Anonymous users:
        - Only have access to RAG knowledge base and web search tools
        - No history is persisted (must pass previous messages if needed)
        - No user facts or personal data access
        - Still traced in LangFuse for monitoring
        
        Args:
            message: User's message
            session_messages: Optional list of previous messages for context
                              Each dict should have 'role' ('user'/'assistant') and 'content'
            
        Returns:
            Assistant's response text
        """
        self._current_user_id = "anonymous"
        self._current_thread_id = None
        
        invoke_config = {}
        
        # Add LangFuse callback for tracing
        langfuse_enabled = bool(os.getenv('LANGFUSE_SECRET_KEY'))
        if langfuse_enabled:
            try:
                from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
                langfuse_handler = LangfuseCallbackHandler(
                    session_id="anonymous-landing",
                    metadata={
                        "agent": "chat_agent",
                        "mode": "anonymous",
                    }
                )
                invoke_config["callbacks"] = [langfuse_handler]
            except ImportError:
                pass
        
        try:
            # Build messages list with optional context
            messages = []
            if session_messages:
                for msg in session_messages:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
            
            messages.append(HumanMessage(content=message))
            
            result = self._anonymous_compiled.invoke(
                {"messages": messages},
                invoke_config
            )
            
            if result.get("input_blocked"):
                logger.info(f"Anonymous request blocked: {result.get('input_block_reason')}")
                return "I'm not able to process that request. Please try rephrasing."
            
            response_text = None
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and not getattr(msg, 'tool_calls', None):
                    response_text = msg.content
                    break
            
            return response_text or "I apologize, but I couldn't generate a response."
            
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
                cursor = self._db_conn.execute(
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


# Singleton instance
_chat_agent: ChatAgent | None = None


def get_chat_agent() -> ChatAgent:
    """Get or create the singleton chat agent instance."""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatAgent()
    return _chat_agent
