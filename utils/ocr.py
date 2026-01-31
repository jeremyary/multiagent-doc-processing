# This project was developed with assistance from AI tools.
"""
OCR utility using docTR with dynamic device selection.
Falls back to CPU if GPU memory is insufficient.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded OCR model
_ocr_model = None
_ocr_device = None


def _get_device() -> str:
    """
    Determine the best device for OCR.
    Uses GPU if available and has sufficient free memory.
    """
    from config import config as app_config
    min_free_gb = app_config.OCR_MIN_FREE_VRAM_GB
    
    try:
        import torch
        if torch.cuda.is_available():
            free_mem_gb = torch.cuda.mem_get_info()[0] / (1024 ** 3)
            if free_mem_gb >= min_free_gb:
                logger.info(f"OCR using GPU (free VRAM: {free_mem_gb:.1f}GB)")
                return "cuda"
            else:
                logger.info(f"OCR using CPU (only {free_mem_gb:.1f}GB VRAM free, need {min_free_gb}GB)")
                return "cpu"
    except ImportError:
        pass
    
    logger.info("OCR using CPU (no GPU available)")
    return "cpu"


def _get_ocr_model():
    """
    Lazy-load the OCR model on first use.
    This avoids the ~2-3 second model load time if OCR is never needed.
    """
    global _ocr_model, _ocr_device
    
    if _ocr_model is None:
        from doctr.models import ocr_predictor
        
        _ocr_device = _get_device()
        
        # Use efficient model architecture
        _ocr_model = ocr_predictor(
            det_arch='db_resnet50',
            reco_arch='crnn_vgg16_bn',
            pretrained=True
        )
        
        if _ocr_device == "cuda":
            _ocr_model = _ocr_model.cuda()
    
    return _ocr_model


def ocr_pdf(pdf_path: Path) -> tuple[str, dict]:
    """
    Perform OCR on a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (extracted_text, metadata)
    """
    from doctr.io import DocumentFile
    
    model = _get_ocr_model()
    
    # Load PDF as images
    doc = DocumentFile.from_pdf(str(pdf_path))
    
    # Run OCR
    result = model(doc)
    
    # Extract text with page structure
    text_content = []
    total_confidence = 0.0
    word_count = 0
    
    for page_idx, page in enumerate(result.pages):
        page_text = []
        for block in page.blocks:
            for line in block.lines:
                line_text = " ".join(word.value for word in line.words)
                page_text.append(line_text)
                
                # Track confidence
                for word in line.words:
                    total_confidence += word.confidence
                    word_count += 1
        
        if page_text:
            text_content.append(f"--- Page {page_idx + 1} ---\n" + "\n".join(page_text))
    
    full_text = "\n\n".join(text_content)
    
    metadata = {
        "ocr_used": True,
        "ocr_device": _ocr_device,
        "ocr_avg_confidence": total_confidence / word_count if word_count > 0 else 0.0,
        "ocr_word_count": word_count,
    }
    
    return full_text, metadata


def needs_ocr(text: str, page_count: int, min_chars_per_page: int = 50) -> bool:
    """
    Determine if a document needs OCR based on extracted text quality.
    
    Args:
        text: Text extracted via pdfplumber
        page_count: Number of pages in the document
        min_chars_per_page: Minimum expected characters per page
        
    Returns:
        True if OCR is recommended
    """
    if not text or not text.strip():
        return True
    
    # Check if we have reasonable text per page
    chars_per_page = len(text.strip()) / max(page_count, 1)
    
    return chars_per_page < min_chars_per_page

