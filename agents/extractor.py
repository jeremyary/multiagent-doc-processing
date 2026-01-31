# This project was developed with assistance from AI tools.
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .base import BaseAgent
from config import config as app_config
from models import ExtractedDocument, WorkflowState, WorkflowError, ExtractionResult
from utils.document_cache import document_cache
from utils.pdf import extract_text_from_pdf
from prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT


class PDFExtractorAgent(BaseAgent):
    """Agent responsible for extracting content from PDF documents."""
    
    def __init__(self):
        super().__init__(name="PDF Extractor")
        
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", EXTRACTION_SYSTEM_PROMPT),
            ("human", EXTRACTION_USER_PROMPT)
        ])
        self.extraction_chain = self.extraction_prompt | self.llm.with_structured_output(ExtractionResult)
    
    def analyze_content(self, filename: str, text: str, config: RunnableConfig) -> ExtractionResult:
        """Use LLM to summarize and extract entities from the text."""
        max_chars = app_config.EXTRACTION_MAX_CHARS
        truncated_text = text[:max_chars] + "..." if len(text) > max_chars else text

        return self.extraction_chain.invoke(
            {"filename": filename, "text": truncated_text},
            config=config
        )
    
    def run(self, state: WorkflowState, config: RunnableConfig) -> dict:
        """Extract content from all PDF files in the input directory."""
        print("\n" + "="*60)
        print("STEP 1: Document Extraction")
        print("="*60)
        self.log("Starting PDF extraction...")
        
        input_dir = Path(state["input_directory"])
        pdf_files = list(input_dir.glob("*.pdf"))
        
        if not pdf_files:
            self.log(f"No PDF files found in {input_dir}")
            return {
                "pdf_files": [],
                "extracted_documents": [],
                "extraction_errors": [WorkflowError(
                    code="NO_PDF_FILES",
                    message=f"No PDF files found in {input_dir}",
                    severity="warning",
                    recoverable=False,
                    node="extractor",
                )],
                "messages": [f"No PDF files found in {input_dir}"]
            }
        
        # Apply document limit if specified
        doc_limit = state.get("doc_limit")
        total_found = len(pdf_files)
        if doc_limit is not None and doc_limit > 0:
            pdf_files = pdf_files[:doc_limit]
            self.log(f"Found {total_found} PDF files, processing first {len(pdf_files)} (--limit {doc_limit})")
        else:
            self.log(f"Found {len(pdf_files)} PDF files")
        
        extracted_docs: list[ExtractedDocument] = []
        errors: list[WorkflowError] = []
        cache_hits = 0
        use_cache = state.get("use_cache", True)
        
        print(f"LLM URL: {app_config.OPENAI_BASE_URL}")
        print(f"LLM MODEL: {app_config.OPENAI_MODEL}")

        for pdf_path in pdf_files:
            self.log(f"Processing: {pdf_path.name}")
            
            try:
                content_hash = document_cache.compute_hash(pdf_path)
                
                cached_doc = document_cache.get_extraction(content_hash) if use_cache else None
                if cached_doc:
                    cached_doc.file_path = str(pdf_path)
                    cached_doc.file_name = pdf_path.name
                    cached_doc.metadata["content_hash"] = content_hash
                    cached_doc.metadata["from_cache"] = True
                    extracted_docs.append(cached_doc)
                    cache_hits += 1
                    self.log(f"  [CACHE HIT] Using cached extraction")
                    continue
                
                # Use shared PDF extraction utility
                extraction = extract_text_from_pdf(pdf_path, include_page_markers=True)
                
                if extraction.ocr_used:
                    self.log(f"  OCR used (confidence: {extraction.ocr_confidence:.0%})")
                
                if extraction.is_empty:
                    errors.append(WorkflowError(
                        code="EMPTY_DOCUMENT",
                        message="No text content extracted from PDF",
                        severity="warning",
                        recoverable=False,
                        node="extractor",
                        document=pdf_path.name,
                    ))
                    continue
                
                result = self.analyze_content(pdf_path.name, extraction.text, config)
                
                metadata = {
                    "page_count": extraction.page_count,
                    "ocr_used": extraction.ocr_used,
                    "content_hash": content_hash,
                    "from_cache": False,
                }
                if extraction.pdf_metadata:
                    metadata["pdf_metadata"] = extraction.pdf_metadata
                if extraction.ocr_confidence is not None:
                    metadata["ocr_confidence"] = extraction.ocr_confidence
                
                doc = ExtractedDocument(
                    file_path=str(pdf_path),
                    file_name=pdf_path.name,
                    page_count=extraction.page_count,
                    raw_text=extraction.text,
                    summary=result.summary,
                    key_entities=result.entities,
                    metadata=metadata
                )
                extracted_docs.append(doc)
                
                if use_cache:
                    document_cache.store_extraction(content_hash, pdf_path.name, doc)
                self.log(f"  Extracted {extraction.page_count} pages, {len(result.entities)} entities")
                
            except RuntimeError as e:
                errors.append(WorkflowError(
                    code="PDF_EXTRACTION_FAILED",
                    message=str(e),
                    severity="error",
                    recoverable=False,
                    node="extractor",
                    document=pdf_path.name,
                ))
                self.log(f"  [ERROR] {e}")
                
            except Exception as e:
                errors.append(WorkflowError(
                    code="EXTRACTION_UNEXPECTED_ERROR",
                    message=str(e),
                    severity="error",
                    recoverable=False,
                    node="extractor",
                    document=pdf_path.name,
                    details={"error_type": type(e).__name__},
                ))
                self.log(f"  [ERROR] {e}")
        
        self.log(f"Extraction complete: {len(extracted_docs)} successful, {cache_hits} from cache, {len(errors)} errors")
        
        return {
            "pdf_files": [str(p) for p in pdf_files],
            "extracted_documents": extracted_docs,
            "extraction_errors": errors,
            "messages": [f"Extracted {len(extracted_docs)} documents with {len(errors)} errors"]
        }
