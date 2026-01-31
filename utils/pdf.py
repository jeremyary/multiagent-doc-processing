# This project was developed with assistance from AI tools.
"""
Shared PDF text extraction utility.

Provides a unified interface for extracting text from PDFs,
with automatic OCR fallback for scanned/image-based documents.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from config import config as app_config
from utils.ocr import needs_ocr, ocr_pdf

logger = logging.getLogger(__name__)


@dataclass
class PDFExtractionResult:
    """Result of PDF text extraction."""
    text: str
    page_count: int
    ocr_used: bool = False
    ocr_confidence: float | None = None
    pdf_metadata: dict = field(default_factory=dict)
    
    @property
    def is_empty(self) -> bool:
        """Check if extraction yielded no text."""
        return not self.text.strip()


def extract_text_from_pdf(
    pdf_path: Path | str,
    include_page_markers: bool = False,
    use_ocr: bool | None = None,
    min_chars_per_page: int | None = None,
) -> PDFExtractionResult:
    """
    Extract text from a PDF file with optional OCR fallback.
    
    Args:
        pdf_path: Path to the PDF file
        include_page_markers: If True, add "--- Page X ---" markers between pages
        use_ocr: Override OCR setting (None = use config.OCR_ENABLED)
        min_chars_per_page: Override minimum chars threshold for OCR trigger
        
    Returns:
        PDFExtractionResult with extracted text and metadata
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        RuntimeError: If extraction fails completely
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Determine OCR settings
    ocr_enabled = use_ocr if use_ocr is not None else app_config.OCR_ENABLED
    chars_threshold = min_chars_per_page or app_config.OCR_MIN_CHARS_PER_PAGE
    
    text_parts = []
    page_count = 0
    pdf_metadata = {}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            
            # Extract PDF metadata if available
            if pdf.metadata:
                pdf_metadata = {
                    k: str(v) for k, v in pdf.metadata.items() 
                    if v is not None
                }
            
            # Extract text from each page
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    if include_page_markers:
                        text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
                    else:
                        text_parts.append(page_text)
        
        full_text = "\n\n".join(text_parts)
        
        # Check if OCR is needed
        ocr_used = False
        ocr_confidence = None
        
        if ocr_enabled and needs_ocr(full_text, page_count, chars_threshold):
            try:
                ocr_text, ocr_metadata = ocr_pdf(pdf_path)
                if ocr_text.strip():
                    full_text = ocr_text
                    ocr_used = True
                    ocr_confidence = ocr_metadata.get("ocr_avg_confidence")
            except Exception as e:
                logger.debug(f"OCR failed for {pdf_path.name}, using pdfplumber text: {e}")
        
        return PDFExtractionResult(
            text=full_text,
            page_count=page_count,
            ocr_used=ocr_used,
            ocr_confidence=ocr_confidence,
            pdf_metadata=pdf_metadata,
        )
        
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {pdf_path}: {str(e)}")
