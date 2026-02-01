# This project was developed with assistance from AI tools.
"""
Session state management for the Streamlit frontend.
"""
from datetime import datetime
from pathlib import Path

import streamlit as st

from agents import get_chat_agent
from frontend.auth import get_current_user, get_user_thread_prefix, get_user_upload_dir
from orchestrator import create_orchestrator


def get_orchestrator(force_new: bool = False):
    """
    Get or create orchestrator.
    
    Args:
        force_new: Force creation of a new orchestrator (useful for refreshing DB state)
    """
    if force_new or "orchestrator" not in st.session_state:
        st.session_state.orchestrator = create_orchestrator(checkpointing=True)
    return st.session_state.orchestrator


def init_session_state():
    """Initialize session state variables for authenticated users."""
    user = get_current_user()
    user_prefix = get_user_thread_prefix()
    
    # Clear anonymous chat messages when entering authenticated state
    if "anon_messages" in st.session_state:
        del st.session_state.anon_messages
    
    if "chat_thread_id" not in st.session_state:
        st.session_state.chat_thread_id = f"{user_prefix}chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chat_agent" not in st.session_state:
        st.session_state.chat_agent = get_chat_agent()
    
    if "workflow_status" not in st.session_state:
        st.session_state.workflow_status = None
    
    if "workflow_result" not in st.session_state:
        st.session_state.workflow_result = None
    
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    
    if "active_review" not in st.session_state:
        st.session_state.active_review = None
    
    if "review_decisions" not in st.session_state:
        st.session_state.review_decisions = {}
    
    # Default view mode - borrowers can't access reviews
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "chat"
    
    # Redirect borrowers away from review tab
    if user and not user.can_review_documents() and st.session_state.view_mode == "review":
        st.session_state.view_mode = "chat"
    
    if "upload_dir" not in st.session_state:
        st.session_state.upload_dir = None
    
    if "selected_report" not in st.session_state:
        st.session_state.selected_report = None


def create_upload_directory() -> Path:
    """Create a unique directory for this upload batch, scoped to user."""
    user_dir = get_user_upload_dir()
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    upload_dir = Path("uploads") / user_dir / f"batch-{timestamp}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_uploaded_file(uploaded_file, upload_dir: Path) -> Path:
    """Save an uploaded file to the specified upload directory."""
    file_path = upload_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def clear_workflow_state():
    """Clear workflow-related session state."""
    st.session_state.workflow_status = None
    st.session_state.workflow_result = None
    st.session_state.uploaded_files = []
    st.session_state.upload_dir = None


def start_new_chat_session():
    """Start a new chat session."""
    user_prefix = get_user_thread_prefix()
    st.session_state.chat_thread_id = f"{user_prefix}chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.session_state.messages = []
