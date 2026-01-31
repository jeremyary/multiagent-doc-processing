# This project was developed with assistance from AI tools.
from typing import TypedDict, Annotated, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from operator import add


class WorkflowError(BaseModel):
    """Structured error for workflow operations."""
    
    code: str = Field(description="Error code, e.g., 'EXTRACTION_FAILED', 'LLM_TIMEOUT'")
    message: str = Field(description="Human-readable error message")
    severity: Literal["warning", "error", "critical"] = Field(
        description="warning: logged but continues, error: node fails but workflow continues, critical: workflow halts"
    )
    recoverable: bool = Field(default=True, description="Whether the operation can be retried")
    node: str = Field(description="Name of the node that produced this error")
    document: str | None = Field(default=None, description="Document name if error is document-specific")
    details: dict = Field(default_factory=dict, description="Additional error context")
    timestamp: datetime = Field(default_factory=datetime.now)


class ExtractionResult(BaseModel):
    """Structured output from the extraction LLM call."""
    
    summary: str = Field(description="A concise 2-3 sentence summary of the document")
    entities: list[str] = Field(description="Key entities: names, organizations, dates, amounts, important terms")


class ClassificationResult(BaseModel):
    """Structured output from the classification LLM call."""
    
    category: str = Field(description="The document category from the provided list")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    sub_categories: list[str] = Field(default_factory=list, description="Optional sub-categories")
    reasoning: str = Field(description="Brief explanation of why this category was chosen")


class ExtractedDocument(BaseModel):
    """Represents extracted content from a single PDF document."""
    
    file_path: str = Field(description="Path to the source PDF file")
    file_name: str = Field(description="Name of the PDF file")
    page_count: int = Field(description="Number of pages in the document")
    raw_text: str = Field(description="Extracted raw text content")
    summary: str = Field(default="", description="AI-generated summary of the document")
    key_entities: list[str] = Field(default_factory=list, description="Key entities found")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class ClassifiedDocument(BaseModel):
    """Represents a classified document with category and confidence."""
    
    document: ExtractedDocument = Field(description="The extracted document")
    category: str = Field(description="Classified category of the document")
    confidence: float = Field(description="Confidence score of classification (0-1)")
    sub_categories: list[str] = Field(default_factory=list, description="Sub-categories if applicable")
    reasoning: str = Field(default="", description="Reasoning for classification")
    human_reviewed: bool = Field(default=False, description="Whether classification was done/confirmed by human")
    original_category: str | None = Field(default=None, description="Original AI category before human review")


class WorkflowState(TypedDict):
    """State that flows through the LangGraph workflow."""
    
    # Input
    input_directory: str
    doc_limit: int | None
    owner_id: str | None  # User who initiated the workflow (for report filtering)
    
    # Extraction phase
    pdf_files: list[str]
    extracted_documents: Annotated[list[ExtractedDocument], add]
    extraction_errors: Annotated[list[WorkflowError], add]
    
    # Classification phase (no reducer - allows replacement during human review)
    classified_documents: list[ClassifiedDocument]
    classification_summary: dict
    
    # Report generation phase
    report_path: str
    report_generated: bool
    
    # Workflow metadata
    workflow_errors: Annotated[list[WorkflowError], add]
    messages: Annotated[list[str], add]
    use_cache: bool
