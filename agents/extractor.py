# This project was developed with assistance from AI tools.
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
import pdfplumber

from .base import BaseAgent
from config import config as app_config
from models import ExtractedDocument, WorkflowState, WorkflowError, ExtractionResult
from utils.document_cache import document_cache
from utils.ocr import ocr_pdf, needs_ocr
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
    
    def extract_text_from_pdf(self, pdf_path: Path) -> tuple[str, int, dict]:
        """
        Extract text content from a PDF file.
        Uses pdfplumber for machine-generated PDFs, falls back to OCR for scanned docs.
        """
        text_content = []
        metadata = {}
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                metadata["page_count"] = page_count
                
                if pdf.metadata:
                    metadata["pdf_metadata"] = {
                        k: str(v) for k, v in pdf.metadata.items() 
                        if v is not None
                    }
                
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_content.append(f"--- Page {i + 1} ---\n{page_text}")
                
                full_text = "\n\n".join(text_content)
                metadata["ocr_used"] = False
                
                # Check if OCR is needed (scanned/image-based PDF)
                if app_config.OCR_ENABLED and needs_ocr(
                    full_text, 
                    page_count, 
                    app_config.OCR_MIN_CHARS_PER_PAGE
                ):

                    self.log(f"  Low text content detected, using OCR...")
                    ocr_text, ocr_metadata = ocr_pdf(pdf_path)
                    if ocr_text.strip():
                        full_text = ocr_text
                
                return full_text, page_count, metadata
                
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from {pdf_path}: {str(e)}")
    
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
                
                raw_text, page_count, metadata = self.extract_text_from_pdf(pdf_path)
                
                if not raw_text.strip():
                    errors.append(WorkflowError(
                        code="EMPTY_DOCUMENT",
                        message="No text content extracted from PDF",
                        severity="warning",
                        recoverable=False,
                        node="extractor",
                        document=pdf_path.name,
                    ))
                    continue
                
                result = self.analyze_content(pdf_path.name, raw_text, config)
                
                metadata["content_hash"] = content_hash
                metadata["from_cache"] = False
                doc = ExtractedDocument(
                    file_path=str(pdf_path),
                    file_name=pdf_path.name,
                    page_count=page_count,
                    raw_text=raw_text,
                    summary=result.summary,
                    key_entities=result.entities,
                    metadata=metadata
                )
                extracted_docs.append(doc)
                
                if use_cache:
                    document_cache.store_extraction(content_hash, pdf_path.name, doc)
                self.log(f"  Extracted {page_count} pages, {len(result.entities)} entities")
                
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
