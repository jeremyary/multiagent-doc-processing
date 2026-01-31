# This project was developed with assistance from AI tools.
import os
from datetime import datetime
from typing import Literal
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import RetryPolicy
from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

from models import WorkflowState, WorkflowError
from agents import PDFExtractorAgent, ClassifierAgent
from utils.report_generator import generate_report_from_state
from utils.human_review import review_unknown_documents
from config import config


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
        
        if checkpointing:
            self.memory = MemorySaver()
            self.compiled_graph = self.graph.compile(checkpointer=self.memory)
        else:
            self.memory = None
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
    
    def run(
        self, 
        input_directory: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        use_cache: bool = True
    ) -> WorkflowState:
        """
        Execute the full workflow.
        
        Args:
            input_directory: Path to directory containing PDF files
            thread_id: Optional thread ID for checkpointing
            session_id: Optional session ID for LangFuse tracking
            use_cache: Whether to use document cache for LLM results
        
        Returns:
            Final workflow state with all results
        """
        langfuse_enabled = bool(os.getenv('LANGFUSE_SECRET_KEY'))
        print(f"LangFuse Tracking: {'Enabled' if langfuse_enabled else 'Disabled'}")
        
        initial_state: WorkflowState = {
            "input_directory": input_directory,
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
        if self.memory:
            default_thread_id = f"doc-orchestrator-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            invoke_config["configurable"] = {"thread_id": thread_id or default_thread_id}
        
        if langfuse_enabled:
            langfuse_handler = LangfuseCallbackHandler(
                session_id=session_id,
                metadata={
                    "workflow": "document_orchestrator",
                    "use_cache": use_cache,
                }
            )
            invoke_config["callbacks"] = [langfuse_handler]
        
        try:
            final_state = self.compiled_graph.invoke(initial_state, invoke_config)
            self._print_summary(final_state)
            return final_state
            
        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
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
