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
    
    # Single SQLite database for all app data (checkpoints, cache, user memory)
    APP_DATA_DB_PATH: str = _resolve_db_path("APP_DATA_DB_PATH", ".app_data.db", BASE_DIR)
    
    # ==========================================================================
    # RAG / Knowledge Base Settings
    # ==========================================================================
    KNOWLEDGE_BASE_DIR: Path = Path(os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge_base"))
    CHROMA_DB_PATH: str = _resolve_db_path("CHROMA_DB_PATH", ".chroma_db", BASE_DIR)
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "4"))
    
    # ==========================================================================
    # Chat Settings
    # ==========================================================================
    CHAT_TEMPERATURE: float = float(os.getenv("CHAT_TEMPERATURE", "0.7"))
    CHAT_MAX_HISTORY: int = int(os.getenv("CHAT_MAX_HISTORY", "50"))  # Max messages per session
    
    # ==========================================================================
    # User Memory Settings
    # ==========================================================================
    # Fact extraction settings
    MEMORY_EXTRACT_FACTS: bool = os.getenv("MEMORY_EXTRACT_FACTS", "true").lower() in ("true", "1", "yes")
    MEMORY_FACT_MIN_CONFIDENCE: float = float(os.getenv("MEMORY_FACT_MIN_CONFIDENCE", "0.7"))
    
    # Conversation memory settings
    MEMORY_STORE_CONVERSATIONS: bool = os.getenv("MEMORY_STORE_CONVERSATIONS", "true").lower() in ("true", "1", "yes")
    MEMORY_RECALL_TOP_K: int = int(os.getenv("MEMORY_RECALL_TOP_K", "3"))
    
    # ==========================================================================
    # BatchData.io API (Property Data)
    # ==========================================================================
    # If API key is not set, property lookup tools will be unavailable
    BATCHDATA_API_KEY: str = os.getenv("BATCHDATA_API_KEY", "")
    BATCHDATA_BASE_URL: str = os.getenv("BATCHDATA_BASE_URL", "https://api.batchdata.com/api/v1")
    
    # ==========================================================================
    # Brave Search API (Web Search)
    # ==========================================================================
    # If API key is not set, web search tool will be unavailable
    # Get an API key at: https://brave.com/search/api/
    BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
    BRAVE_SEARCH_BASE_URL: str = os.getenv("BRAVE_SEARCH_BASE_URL", "https://api.search.brave.com/res/v1")
    
    # ==========================================================================
    # FRED API (Federal Reserve Economic Data)
    # ==========================================================================
    # If API key is not set, economic data tool will be unavailable
    # Get an API key at: https://fred.stlouisfed.org/docs/api/api_key.html
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    FRED_BASE_URL: str = os.getenv("FRED_BASE_URL", "https://api.stlouisfed.org/fred")
    
    # ==========================================================================
    # Guardrails Settings (Defense in Depth)
    # ==========================================================================
    # Enable/disable guardrails (all disabled = pass-through mode)
    GUARDRAILS_ENABLED: bool = os.getenv("GUARDRAILS_ENABLED", "true").lower() in ("true", "1", "yes")
    
    # Input guardrails
    GUARDRAILS_SANITIZE_INPUT: bool = os.getenv("GUARDRAILS_SANITIZE_INPUT", "true").lower() in ("true", "1", "yes")
    GUARDRAILS_DETECT_PII: bool = os.getenv("GUARDRAILS_DETECT_PII", "true").lower() in ("true", "1", "yes")
    GUARDRAILS_MASK_PII: bool = os.getenv("GUARDRAILS_MASK_PII", "true").lower() in ("true", "1", "yes")
    GUARDRAILS_BLOCK_PII: bool = os.getenv("GUARDRAILS_BLOCK_PII", "false").lower() in ("true", "1", "yes")
    
    # Output guardrails
    GUARDRAILS_CHECK_OUTPUT: bool = os.getenv("GUARDRAILS_CHECK_OUTPUT", "true").lower() in ("true", "1", "yes")
    GUARDRAILS_MASK_OUTPUT_PII: bool = os.getenv("GUARDRAILS_MASK_OUTPUT_PII", "true").lower() in ("true", "1", "yes")
    
    # Intent evaluation (Layer 2 - LLM-based guard)
    GUARDRAILS_INTENT_CHECK: bool = os.getenv("GUARDRAILS_INTENT_CHECK", "true").lower() in ("true", "1", "yes")
    
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
        cls.KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
