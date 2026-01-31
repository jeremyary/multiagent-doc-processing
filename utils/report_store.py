# This project was developed with assistance from AI tools.
"""
Report metadata storage for tracking generated reports.

Stores ownership and metadata separately from filenames, enabling
cleaner filenames while maintaining proper access control.
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)


class ReportStore:
    """SQLite-backed storage for report metadata."""
    
    def __init__(self, db_path: str | None = None):
        """Initialize the report store."""
        self.db_path = db_path or config.APP_DATA_DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,
                    owner_id TEXT,
                    thread_id TEXT,
                    document_count INTEGER,
                    classification_summary TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_owner 
                ON reports(owner_id)
            """)
            
            # Migration: add classification_summary column if it doesn't exist
            cursor = conn.execute("PRAGMA table_info(reports)")
            columns = [row[1] for row in cursor.fetchall()]
            if "classification_summary" not in columns:
                conn.execute("ALTER TABLE reports ADD COLUMN classification_summary TEXT")
            
            conn.commit()
        finally:
            conn.close()
    
    def register_report(
        self,
        filename: str,
        owner_id: str | None = None,
        thread_id: str | None = None,
        document_count: int = 0,
        classification_summary: dict | None = None
    ) -> int:
        """
        Register a new report.
        
        Args:
            filename: The report filename (without path)
            owner_id: User who generated the report
            thread_id: Workflow thread that generated it
            document_count: Number of documents in the report
            classification_summary: Dict with category counts and document names
            
        Returns:
            Report ID
        """
        import json
        now = datetime.now().isoformat()
        summary_json = json.dumps(classification_summary) if classification_summary else None
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                INSERT INTO reports (filename, owner_id, thread_id, document_count, classification_summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (filename, owner_id, thread_id, document_count, summary_json, now))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_reports(self, owner_id: str | None = None) -> list[dict]:
        """
        Get reports, optionally filtered by owner.
        
        Args:
            owner_id: If provided, only return reports for this owner.
                      If None, return all reports.
        """
        import json
        conn = sqlite3.connect(self.db_path)
        try:
            if owner_id:
                cursor = conn.execute("""
                    SELECT id, filename, owner_id, thread_id, document_count, classification_summary, created_at
                    FROM reports
                    WHERE owner_id = ? OR owner_id IS NULL
                    ORDER BY created_at DESC
                """, (owner_id,))
            else:
                cursor = conn.execute("""
                    SELECT id, filename, owner_id, thread_id, document_count, classification_summary, created_at
                    FROM reports
                    ORDER BY created_at DESC
                """)
            
            reports = []
            for row in cursor.fetchall():
                summary = json.loads(row[5]) if row[5] else None
                reports.append({
                    "id": row[0],
                    "filename": row[1],
                    "owner_id": row[2],
                    "thread_id": row[3],
                    "document_count": row[4],
                    "classification_summary": summary,
                    "created_at": row[6],
                })
            return reports
        finally:
            conn.close()
    
    def get_report_by_filename(self, filename: str) -> dict | None:
        """Get report metadata by filename."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT id, filename, owner_id, thread_id, document_count, created_at
                FROM reports
                WHERE filename = ?
            """, (filename,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "filename": row[1],
                    "owner_id": row[2],
                    "thread_id": row[3],
                    "document_count": row[4],
                    "created_at": row[5],
                }
            return None
        finally:
            conn.close()
    
    def get_report_by_id(self, report_id: int, owner_id: str | None = None) -> dict | None:
        """
        Get report metadata by ID with optional owner verification.
        
        Args:
            report_id: The report's database ID
            owner_id: If provided, verify the report belongs to this owner
            
        Returns:
            Report dict if found (and owned by user if owner_id provided), None otherwise
        """
        import json
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT id, filename, owner_id, thread_id, document_count, classification_summary, created_at
                FROM reports
                WHERE id = ?
            """, (report_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            report = {
                "id": row[0],
                "filename": row[1],
                "owner_id": row[2],
                "thread_id": row[3],
                "document_count": row[4],
                "classification_summary": json.loads(row[5]) if row[5] else None,
                "created_at": row[6],
            }
            
            # Verify ownership if requested
            if owner_id and report["owner_id"] != owner_id:
                return None
            
            return report
        finally:
            conn.close()
    
    def delete_report(self, filename: str):
        """Delete report metadata (does not delete the file)."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM reports WHERE filename = ?", (filename,))
            conn.commit()
        finally:
            conn.close()
    
    def sync_with_filesystem(self, report_dir: Path):
        """
        Sync database with actual files on disk.
        Removes entries for files that no longer exist.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT filename FROM reports")
            db_files = {row[0] for row in cursor.fetchall()}
            
            actual_files = {f.name for f in report_dir.glob("*.pdf")} if report_dir.exists() else set()
            
            # Remove DB entries for files that don't exist
            missing = db_files - actual_files
            for filename in missing:
                conn.execute("DELETE FROM reports WHERE filename = ?", (filename,))
                logger.debug(f"Removed orphaned report entry: {filename}")
            
            conn.commit()
            return len(missing)
        finally:
            conn.close()


# Singleton instance
_report_store: ReportStore | None = None


def get_report_store() -> ReportStore:
    """Get or create the singleton report store instance."""
    global _report_store
    if _report_store is None:
        _report_store = ReportStore()
    return _report_store
