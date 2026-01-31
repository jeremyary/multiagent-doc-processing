# This project was developed with assistance from AI tools.
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _resolve_db_path(env_var: str, default: str, base_dir: Path) -> str:
    """Resolve database path, making relative paths absolute from base_dir."""
    path = os.getenv(env_var, default)
    if os.path.isabs(path):
        return path
    return str(base_dir / path)


class Config:
    """Application configuration."""
    
    # ==========================================================================
    # OpenAI / LLM Settings
    # ==========================================================================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # LLM parameters
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_RETRY_DELAY: float = float(os.getenv("LLM_RETRY_DELAY", "1.0"))
    
    # ==========================================================================
    # Text Processing Limits
    # ==========================================================================
    # Maximum characters to send to LLM for extraction/summarization
    EXTRACTION_MAX_CHARS: int = int(os.getenv("EXTRACTION_MAX_CHARS", "8000"))
    
    # Maximum characters of sample text for classification
    CLASSIFICATION_SAMPLE_CHARS: int = int(os.getenv("CLASSIFICATION_SAMPLE_CHARS", "2000"))
    
    # ==========================================================================
    # OCR Settings (for scanned PDFs)
    # ==========================================================================
    # Enable OCR fallback for scanned/image-based PDFs
    OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "true").lower() in ("true", "1", "yes")
    
    # Minimum characters per page before triggering OCR
    OCR_MIN_CHARS_PER_PAGE: int = int(os.getenv("OCR_MIN_CHARS_PER_PAGE", "50"))
    
    # Minimum free VRAM (GB) required to use GPU for OCR
    OCR_MIN_FREE_VRAM_GB: float = float(os.getenv("OCR_MIN_FREE_VRAM_GB", "3.0"))
    
    # ==========================================================================
    # Directory Paths and Storage
    # ==========================================================================
    BASE_DIR: Path = Path(__file__).parent
    INPUT_PDF_DIR: Path = Path(os.getenv("INPUT_PDF_DIR", "./input_pdfs"))
    OUTPUT_REPORT_DIR: Path = Path(os.getenv("OUTPUT_REPORT_DIR", "./output_reports"))
    
    # Database paths (relative paths resolved from BASE_DIR)
    CHECKPOINT_DB_PATH: str = _resolve_db_path("CHECKPOINT_DB_PATH", ".workflow_checkpoints.db", BASE_DIR)
    DOCUMENT_CACHE_DB_PATH: str = _resolve_db_path("DOCUMENT_CACHE_DB_PATH", ".document_cache.db", BASE_DIR)
    
    # ==========================================================================
    # Document Categories (Mortgage Loan Process)
    # ==========================================================================
    DOCUMENT_CATEGORIES: list[str] = [
        "Loan Application",
        "Pre-Approval Letter",
        "Income Verification",          # W-2, pay stubs, tax returns
        "Employment Verification",
        "Bank Statement",               # Asset verification
        "Credit Report",
        "Property Appraisal",
        "Title Report",                 # Title search, title insurance
        "Homeowners Insurance",
        "Closing Disclosure",
        "Loan Estimate",
        "Deed/Mortgage Note",
        "HOA Documentation",
        "Gift Letter",
        "Identity Verification",        # Driver's license, passport, etc.
        "Property Tax Statement",
        "Divorce Decree/Legal Judgment",
        "Bankruptcy Documentation",
        "Unknown Relevance"             # Documents that don't fit other categories
    ]
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required. Set it in .env file.")
        
        cls.INPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
