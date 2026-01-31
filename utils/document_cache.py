# This project was developed with assistance from AI tools.
"""
SQLite-based cache for document extraction and classification results.

Uses SHA256 content hashes for O(1) lookups.
"""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import config
from models import ClassifiedDocument, ExtractedDocument


class DocumentCache:
    """
    SQLite-based cache for document extraction and classification results.
    
    Cache keys are SHA256 hashes of file contents, making lookups O(1) after
    the initial hash computation.
    """
    
    def __init__(self, cache_path: str | Path = ".document_cache.db"):
        """
        Initialize the document cache.
        
        Args:
            cache_path: Path to the SQLite database file
        """
        self.cache_path = Path(cache_path)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_cache (
                    content_hash TEXT PRIMARY KEY,
                    file_name TEXT,
                    extraction_data TEXT,
                    classification_data TEXT,
                    created_at TEXT,
                    last_accessed TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_name 
                ON document_cache(file_name)
            """)
            conn.commit()
    
    @staticmethod
    def compute_hash(file_path: str | Path) -> str:
        """
        Compute SHA256 hash of file contents.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hex-encoded SHA256 hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def get_extraction(self, content_hash: str) -> Optional[ExtractedDocument]:
        """
        Retrieve cached extraction results.
        
        Note: Only returns data if BOTH extraction AND classification are cached.
        Args:
            content_hash: SHA256 hash of the document
            
        Returns:
            ExtractedDocument if cached, None otherwise
        """
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute(
                """SELECT extraction_data, classification_data 
                   FROM document_cache WHERE content_hash = ?""",
                (content_hash,)
            )
            row = cursor.fetchone()
            
            if row and row[0] and row[1]:
                conn.execute(
                    "UPDATE document_cache SET last_accessed = ? WHERE content_hash = ?",
                    (datetime.now().isoformat(), content_hash)
                )
                conn.commit()
                
                data = json.loads(row[0])
                return ExtractedDocument(**data)
        
        return None
    
    def get_classification(self, content_hash: str) -> Optional[ClassifiedDocument]:
        """
        Retrieve cached classification results.
        
        Args:
            content_hash: SHA256 hash of the document
            
        Returns:
            ClassifiedDocument if cached, None otherwise
        """
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute(
                "SELECT classification_data FROM document_cache WHERE content_hash = ?",
                (content_hash,)
            )
            row = cursor.fetchone()
            
            if row and row[0]:
                conn.execute(
                    "UPDATE document_cache SET last_accessed = ? WHERE content_hash = ?",
                    (datetime.now().isoformat(), content_hash)
                )
                conn.commit()
                
                data = json.loads(row[0])
                if "document" in data:
                    data["document"] = ExtractedDocument(**data["document"])
                return ClassifiedDocument(**data)
        
        return None
    
    def store_extraction(
        self, 
        content_hash: str, 
        file_name: str,
        extraction: ExtractedDocument
    ) -> None:
        """
        Store extraction results in cache.
        
        Args:
            content_hash: SHA256 hash of the document
            file_name: Original filename (for reference)
            extraction: Extraction results to cache
        """
        now = datetime.now().isoformat()
        cache_data = {
            "file_path": extraction.file_path,
            "file_name": extraction.file_name,
            "page_count": extraction.page_count,
            "raw_text": "",
            "summary": extraction.summary,
            "key_entities": extraction.key_entities,
            "metadata": extraction.metadata,
        }
        
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                INSERT INTO document_cache (content_hash, file_name, extraction_data, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(content_hash) DO UPDATE SET
                    extraction_data = excluded.extraction_data,
                    last_accessed = excluded.last_accessed
            """, (content_hash, file_name, json.dumps(cache_data), now, now))
            conn.commit()
    
    def store_classification(
        self, 
        content_hash: str,
        classification: ClassifiedDocument
    ) -> None:
        """
        Store classification results in cache.
        
        Args:
            content_hash: SHA256 hash of the document
            classification: Classification results to cache
        """
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute("""
                UPDATE document_cache 
                SET classification_data = ?, last_accessed = ?
                WHERE content_hash = ?
            """, (classification.model_dump_json(), now, content_hash))
            conn.commit()
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM document_cache")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM document_cache WHERE extraction_data IS NOT NULL"
            )
            with_extraction = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM document_cache WHERE classification_data IS NOT NULL"
            )
            with_classification = cursor.fetchone()[0]
        
        return {
            "total_documents": total,
            "with_extraction": with_extraction,
            "with_classification": with_classification
        }
    
    def clear(self) -> int:
        """
        Clear all cached data.
        
        Returns:
            Number of entries cleared
        """
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM document_cache")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM document_cache")
            conn.commit()
        return count


# Global cache instance (uses shared app database)
document_cache = DocumentCache(config.APP_DATA_DB_PATH)
