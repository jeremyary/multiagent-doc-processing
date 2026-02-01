# This project was developed with assistance from AI tools.
"""
Workflow and report management for the Streamlit frontend.
"""
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import config
from frontend.auth import get_current_user, get_user_thread_prefix
from frontend.state import get_orchestrator


def run_workflow(upload_dir: Path) -> dict:
    """
    Run the document processing workflow on uploaded files.
    
    Args:
        upload_dir: Directory containing the uploaded PDF files
        
    Returns:
        Workflow result state
    """
    orchestrator = get_orchestrator()
    user = get_current_user()
    user_prefix = get_user_thread_prefix()
    thread_id = f"{user_prefix}ui-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    owner_id = user.username if user else None
    
    # Store thread_id so we can filter reports later
    st.session_state.current_workflow_thread = thread_id
    
    result, _ = orchestrator.run(
        input_directory=str(upload_dir),
        thread_id=thread_id,
        session_id=owner_id,
        use_cache=True,
        interrupt_handler=None,
        owner_id=owner_id
    )
    
    return result


def list_reports(filter_by_user: bool = True) -> list[dict]:
    """
    List available reports using the report store for access control.
    
    Args:
        filter_by_user: If True, borrowers only see their own reports.
                        Admins see all reports regardless.
    """
    from utils.report_store import get_report_store
    
    output_dir = config.OUTPUT_REPORT_DIR
    if not output_dir.exists():
        return []
    
    user = get_current_user()
    can_see_all = user and user.can_view_all_reports()
    username = user.username if user else None
    
    # Sync store with filesystem (removes orphaned entries)
    store = get_report_store()
    store.sync_with_filesystem(output_dir)
    
    # Get reports from store with proper filtering
    if filter_by_user and not can_see_all and username:
        db_reports = store.get_reports(owner_id=username)
    else:
        db_reports = store.get_reports()
    
    # Build list with file info
    reports = []
    for report in db_reports:
        file_path = output_dir / report["filename"]
        if file_path.exists():
            stat = file_path.stat()
            owner = report.get("owner_id") or "cli"
            doc_count = report.get("document_count", 0)
            created = report.get("created_at", "")[:10]
            display_name = f"{created} - {doc_count} docs ({owner})"
            
            reports.append({
                "name": report["filename"],
                "display_name": display_name,
                "path": file_path,
                "size_kb": stat.st_size / 1024,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "owner_id": report.get("owner_id"),
                "document_count": doc_count,
            })
    
    # Also include legacy files not in the store (for backward compatibility)
    stored_filenames = {r["filename"] for r in db_reports}
    for pdf_file in output_dir.glob("*.pdf"):
        if pdf_file.name not in stored_filenames:
            if can_see_all or not filter_by_user:
                stat = pdf_file.stat()
                reports.append({
                    "name": pdf_file.name,
                    "display_name": pdf_file.stem,
                    "path": pdf_file,
                    "size_kb": stat.st_size / 1024,
                    "modified": datetime.fromtimestamp(stat.st_mtime),
                    "owner_id": None,
                    "document_count": 0,
                })
    
    # Sort by modification time (newest first)
    reports.sort(key=lambda r: r["modified"], reverse=True)
    return reports
