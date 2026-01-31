# This project was developed with assistance from AI tools.
"""
LangGraph-based orchestrator for the document processing workflow.

Manages the multi-agent workflow: extraction -> classification -> report generation.
Supports checkpointing, human-in-the-loop review, and observability via LangFuse.
"""
import os
import sqlite3
from datetime import datetime
from typing import Any, Callable, Literal

from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy

from agents import ClassifierAgent, PDFExtractorAgent
from config import config
from models import WorkflowError, WorkflowState
from utils.human_review import review_unknown_documents
from utils.report_generator import generate_report_from_state


# Define retry policy for LLM-calling nodes
LLM_RETRY_POLICY = RetryPolicy(
    initial_interval=config.LLM_RETRY_DELAY,
    backoff_factor=2.0,
    max_interval=30.0,
    max_attempts=config.LLM_MAX_RETRIES,
    jitter=True,
    retry_on=(TimeoutError, ConnectionError, RuntimeError),
)

class WorkflowOrchestrator:
    """
    LangGraph-based orchestrator for the document processing workflow.
    
    The workflow follows this sequence:
    1. extract_documents - PDF Extractor reads all PDFs from input directory
    2. classify_documents - Classifier categorizes each extracted document
    3. generate_report - Report Builder creates a summary PDF
    """
    
    def __init__(self, checkpointing: bool = True):
        """
        Initialize the orchestrator.
        
        Args:
            checkpointing: Enable state checkpointing for resumability
        """
        self.extractor = PDFExtractorAgent()
        self.classifier = ClassifierAgent()
        self.graph = self._build_graph()
        self.checkpointing = checkpointing
        
        if checkpointing:
            self._db_conn = sqlite3.connect(config.APP_DATA_DB_PATH, check_same_thread=False)
            self.checkpointer = SqliteSaver(self._db_conn)
            self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
        else:
            self._db_conn = None
            self.checkpointer = None
            self.compiled_graph = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow graph."""
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node(
            "extract_documents", 
            self.extractor.run, 
            retry_policy=LLM_RETRY_POLICY,
            metadata={"agent": "extractor", "has_llm": True}
        )
        workflow.add_node(
            "classify_documents", 
            self.classifier.run, 
            retry_policy=LLM_RETRY_POLICY,
            metadata={"agent": "classifier", "has_llm": True}
        )
        workflow.add_node(
            "human_review", 
            review_unknown_documents,
            metadata={"agent": "human_review", "has_llm": False}
        )
        workflow.add_node(
            "generate_report", 
            generate_report_from_state,
            metadata={"agent": "report_generator", "has_llm": False}
        )
        
        workflow.add_edge(START, "extract_documents")
        workflow.add_conditional_edges(
            "extract_documents",
            self._should_continue_after_extraction,
            {
                "continue": "classify_documents",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "classify_documents",
            self._should_review_unknown,
            {
                "review": "human_review",
                "skip": "generate_report"
            }
        )
        workflow.add_edge("human_review", "generate_report")
        workflow.add_edge("generate_report", END)
        
        return workflow
    
    def _has_critical_errors(self, state: WorkflowState) -> bool:
        """Check if any critical errors exist in the workflow state."""
        all_errors = state.get("workflow_errors", []) + state.get("extraction_errors", [])
        return any(
            isinstance(e, WorkflowError) and e.severity == "critical" 
            for e in all_errors
        )
    
    def _should_continue_after_extraction(self, state: WorkflowState) -> Literal["continue", "end"]:
        """
        Conditional edge: decide whether to continue after extraction.
        
        Ends early if:
        - No documents were successfully extracted
        - Critical errors occurred
        """
        if self._has_critical_errors(state):
            print("\n[CRITICAL] Critical error detected - halting workflow")
            return "end"
        
        extracted_docs = state.get("extracted_documents", [])
        
        if not extracted_docs:
            print("\n[WARNING] No documents extracted - ending workflow early")
            return "end"
        
        return "continue"
    
    def _should_review_unknown(self, state: WorkflowState) -> Literal["review", "skip"]:
        """
        Conditional edge: decide whether to trigger human review.
        
        Triggers review if any documents are classified as 'Unknown Relevance'.
        """
        classified_docs = state.get("classified_documents", [])
        unknown_count = sum(1 for doc in classified_docs if doc.category == "Unknown Relevance")
        
        if unknown_count > 0:
            return "review"
        
        return "skip"
    
    def _has_checkpoint(self, thread_id: str) -> bool:
        """Check if a checkpoint exists for the given thread_id."""
        if not self.checkpointer or not thread_id:
            return False
        try:
            checkpoint = self.checkpointer.get({"configurable": {"thread_id": thread_id}})
            return checkpoint is not None
        except Exception:
            return False
    
    def _get_human_review_interrupt(self, state_snapshot) -> dict | None:
        """Extract human_review interrupt data from a state snapshot, if present."""
        if not state_snapshot or "human_review" not in (state_snapshot.next or ()):
            return None
        
        for task in (state_snapshot.tasks or []):
            for interrupt in (task.interrupts or []):
                value = interrupt.value if hasattr(interrupt, 'value') else interrupt
                if isinstance(value, dict) and value.get("type") == "human_review":
                    return value
        return None
    
    def list_pending_reviews(self) -> list[dict]:
        """
        List all workflows waiting for human review.
        
        Returns:
            List of dicts with thread_id and interrupt data
        """
        if not self._db_conn:
            return []
        
        pending = []
        try:
            cursor = self._db_conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE '%doc-%' OR thread_id LIKE '%ui-%'"
            )
            thread_ids = [row[0] for row in cursor.fetchall()]
            
            for thread_id in thread_ids:
                state_snapshot = self.compiled_graph.get_state({"configurable": {"thread_id": thread_id}})
                interrupt_data = self._get_human_review_interrupt(state_snapshot)
                
                if interrupt_data:
                    pending.append({
                        "thread_id": thread_id,
                        "interrupt_data": interrupt_data,
                        "documents": interrupt_data.get("documents", []),
                        "categories": interrupt_data.get("categories", []),
                    })
        except Exception as e:
            print(f"Error listing pending reviews: {e}")
        
        return pending
    
    def get_workflow_state(self, thread_id: str) -> dict | None:
        """
        Get the current state of a workflow by thread_id.
        
        Args:
            thread_id: The workflow thread ID
            
        Returns:
            The workflow state dict, or None if not found
        """
        if not self.checkpointer:
            return None
        
        try:
            state = self.compiled_graph.get_state({"configurable": {"thread_id": thread_id}})
            if state and state.values:
                return state.values
        except Exception:
            pass
        
        return None
    
    def resume_with_decisions(self, thread_id: str, decisions: dict[str, str | None]) -> dict:
        """
        Resume a paused workflow with human review decisions.
        
        Args:
            thread_id: The workflow thread ID
            decisions: Dict mapping filename to chosen category
            
        Returns:
            Final workflow state
        """
        invoke_config = {"configurable": {"thread_id": thread_id}}
        
        # Extract owner_id from thread_id pattern: "{user}-ui-{timestamp}"
        owner_id = None
        if "-ui-" in thread_id:
            owner_id = thread_id.split("-ui-")[0]
        elif "-doc-" in thread_id:
            owner_id = thread_id.split("-doc-")[0] if "-" in thread_id.split("-doc-")[0] else None
        
        langfuse_enabled = bool(os.getenv('LANGFUSE_SECRET_KEY'))
        if langfuse_enabled:
            langfuse_handler = LangfuseCallbackHandler(
                session_id=owner_id,
                metadata={
                    "workflow": "document_orchestrator",
                    "thread_id": thread_id,
                    "owner_id": owner_id,
                    "resumed_from_ui": True,
                }
            )
            invoke_config["callbacks"] = [langfuse_handler]
        
        # Resume with the human decisions
        result = self.compiled_graph.invoke(
            Command(resume=decisions),
            invoke_config
        )
        
        # Handle any additional interrupts (shouldn't happen, but be safe)
        while "__interrupt__" in result:
            return result  # Return early if another interrupt occurs
        
        return result
    
    def run(
        self, 
        input_directory: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        use_cache: bool = True,
        doc_limit: int | None = None,
        interrupt_handler: Callable | None = None,
        owner_id: str | None = None
    ) -> tuple[WorkflowState, str | None]:
        """
        Execute the full workflow with interrupt handling.
        
        If thread_id is provided and a checkpoint exists, resumes from that state.
        Otherwise, starts a new workflow.
        
        Args:
            input_directory: Path to directory containing PDF files
            thread_id: Thread ID for checkpointing. If exists, resumes; otherwise starts fresh.
            session_id: Optional session ID for LangFuse tracking
            use_cache: Whether to use document cache for LLM results
            doc_limit: Optional limit on number of documents to process
            interrupt_handler: Callback to handle interrupts (receives interrupt data, returns resume data)
            owner_id: User who owns this workflow (for report filtering)
        
        Returns:
            Tuple of (final workflow state, thread_id used)
        """
        langfuse_enabled = bool(os.getenv('LANGFUSE_SECRET_KEY'))
        print(f"LangFuse Tracking: {'Enabled' if langfuse_enabled else 'Disabled'}")
        
        if self.checkpointing:
            resuming = self._has_checkpoint(thread_id)
        else:
            resuming = False
        
        initial_state: WorkflowState = {
            "input_directory": input_directory,
            "doc_limit": doc_limit,
            "owner_id": owner_id,
            "pdf_files": [],
            "extracted_documents": [],
            "extraction_errors": [],
            "classified_documents": [],
            "classification_summary": {},
            "report_path": "",
            "report_generated": False,
            "workflow_errors": [],
            "messages": [],
            "use_cache": use_cache,
        }
        
        invoke_config: dict = {}
        if self.checkpointing and thread_id:
            invoke_config["configurable"] = {"thread_id": thread_id}
            print(f"Thread ID: {thread_id}")
        
        if langfuse_enabled:
            langfuse_handler = LangfuseCallbackHandler(
                session_id=session_id or owner_id,  # Use owner_id as fallback
                metadata={
                    "workflow": "document_orchestrator",
                    "use_cache": use_cache,
                    "thread_id": thread_id,
                    "owner_id": owner_id,
                }
            )
            invoke_config["callbacks"] = [langfuse_handler]
        
        try:
            # If checkpoint exists, resume; otherwise start fresh
            if resuming:
                print(f"Resuming workflow from checkpoint...")
                result = self.compiled_graph.invoke(None, invoke_config)
            else:
                result = self.compiled_graph.invoke(initial_state, invoke_config)
            
            # Handle interrupts in a loop
            while "__interrupt__" in result:
                interrupt_data = result["__interrupt__"]
                
                if interrupt_handler is None:
                    print("\n[WARNING] Workflow interrupted but no handler provided")
                    print(f"To resume later, run with: --thread-id {thread_id}")
                    return result, thread_id
                
                # Get the interrupt value (first interrupt's value)
                if interrupt_data and len(interrupt_data) > 0:
                    interrupt_value = interrupt_data[0].value if hasattr(interrupt_data[0], 'value') else interrupt_data[0]
                else:
                    interrupt_value = interrupt_data
                
                # Call the interrupt handler to get resume data
                resume_data = interrupt_handler(interrupt_value)
                
                # Resume the workflow with the human input
                result = self.compiled_graph.invoke(
                    Command(resume=resume_data),
                    invoke_config
                )
            
            self._print_summary(result)
            return result, thread_id
            
        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            if thread_id:
                print(f"To resume, run with: --thread-id {thread_id}")
            raise
    
    def _print_summary(self, state: WorkflowState) -> None:
        """Print a summary of the workflow execution."""
        print("\n" + "="*60)
        print("WORKFLOW SUMMARY")
        print("="*60)
        
        extracted = state.get("extracted_documents", [])
        classified = state.get("classified_documents", [])
        summary = state.get("classification_summary", {})
        
        print(f"Documents Processed: {len(extracted)}")
        print(f"Documents Classified: {len(classified)}")
        print(f"Categories Found: {len(summary)}")
        
        if summary:
            print("\nClassification Breakdown:")
            for category, info in sorted(summary.items()):
                print(f"  - {category}: {info['count']} docs (avg conf: {info['avg_confidence']:.0%})")
        
        if state.get("report_generated"):
            print(f"\nReport Generated: {state.get('report_path')}")
        else:
            print("\n[WARNING] No report was generated")
        
        workflow_errors = state.get("workflow_errors", [])
        extraction_errors = state.get("extraction_errors", [])
        all_errors = workflow_errors + extraction_errors
        
        if all_errors:
            critical = [e for e in all_errors if isinstance(e, WorkflowError) and e.severity == "critical"]
            errors = [e for e in all_errors if isinstance(e, WorkflowError) and e.severity == "error"]
            warnings = [e for e in all_errors if isinstance(e, WorkflowError) and e.severity == "warning"]
            
            print(f"\nErrors Summary: {len(critical)} critical, {len(errors)} errors, {len(warnings)} warnings")
            
            for error in critical:
                doc_info = f" ({error.document})" if error.document else ""
                print(f"  [CRITICAL] {error.code}{doc_info}: {error.message}")
            
            for error in (errors + warnings)[:5]:
                severity = error.severity.upper()
                doc_info = f" ({error.document})" if error.document else ""
                print(f"  [{severity}] {error.code}{doc_info}: {error.message}")
            
            remaining = len(errors) + len(warnings) - 5
            if remaining > 0:
                print(f"  ... and {remaining} more errors/warnings")
        
        print("="*60)


def create_orchestrator(checkpointing: bool = True) -> WorkflowOrchestrator:
    """
    Factory function to create a workflow orchestrator.
    
    Args:
        checkpointing: Enable state checkpointing
    
    Returns:
        Configured WorkflowOrchestrator instance
    """
    return WorkflowOrchestrator(checkpointing=checkpointing)
