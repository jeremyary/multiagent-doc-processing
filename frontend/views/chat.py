# This project was developed with assistance from AI tools.
"""
Chat view - authenticated chat interface with document processing.
"""
from datetime import datetime
from pathlib import Path

import streamlit as st

from frontend.auth import get_current_user, get_user_thread_prefix
from frontend.components import render_logo
from frontend.state import (
    clear_workflow_state,
    create_upload_directory,
    save_uploaded_file,
    start_new_chat_session,
)
from frontend.workflow import list_reports, run_workflow


def render_chat_sidebar():
    """Render chat-related sidebar content."""
    st.markdown("### Chat Sessions")
    
    st.markdown(
        f'<div class="session-info">Thread: {st.session_state.chat_thread_id}</div>',
        unsafe_allow_html=True
    )
    
    if st.button("New Chat Session", use_container_width=True):
        start_new_chat_session()
        st.rerun()
    
    with st.expander("Previous Sessions", expanded=False):
        user = get_current_user()
        # Admins see all sessions, borrowers only see their own
        if user and user.is_admin:
            sessions = st.session_state.chat_agent.list_sessions(user_prefix=None)
        else:
            user_prefix = get_user_thread_prefix()
            sessions = st.session_state.chat_agent.list_sessions(user_prefix=user_prefix)
        
        if sessions:
            # Sort newest-to-oldest (thread IDs contain timestamps)
            sessions_sorted = sorted(sessions, reverse=True)
            for session_id in sessions_sorted[:10]:
                if session_id != st.session_state.chat_thread_id:
                    if st.button(f"{session_id}", key=f"load_{session_id}", use_container_width=True):
                        st.session_state.chat_thread_id = session_id
                        history = st.session_state.chat_agent.get_history(session_id)
                        st.session_state.messages = history
                        st.rerun()
        else:
            st.caption("No previous sessions")
    
    st.divider()
    
    # Document Processing Section
    render_document_upload_section()


def render_document_upload_section():
    """Render the document upload and processing section in sidebar."""
    st.markdown("### Document Processing")
    
    uploaded_files = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload mortgage documents for classification"
    )
    
    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) selected")
        
        for f in uploaded_files:
            st.text(f"• {f.name}")
        
        if st.button("Process Documents", type="primary", use_container_width=True):
            with st.spinner("Saving files..."):
                upload_dir = create_upload_directory()
                st.session_state.upload_dir = upload_dir
                
                saved_files = []
                for uploaded_file in uploaded_files:
                    file_path = save_uploaded_file(uploaded_file, upload_dir)
                    saved_files.append(file_path.name)
                st.session_state.uploaded_files = saved_files
            
            st.session_state.workflow_status = "running"
            st.rerun()
    
    # Show workflow status
    if st.session_state.workflow_status:
        render_workflow_status_section()


def render_workflow_status_section():
    """Render workflow status in sidebar."""
    st.divider()
    st.markdown("### Workflow Status")
    
    status = st.session_state.workflow_status
    
    if status == "running":
        st.markdown(
            '<div class="workflow-status status-running">Processing documents...</div>',
            unsafe_allow_html=True
        )
        
        try:
            result = run_workflow(st.session_state.upload_dir)
            st.session_state.workflow_result = result
            
            if "__interrupt__" in result:
                st.session_state.workflow_status = "review"
            elif result.get("report_generated"):
                st.session_state.workflow_status = "complete"
            else:
                st.session_state.workflow_status = "error"
            
            st.rerun()
            
        except Exception as e:
            st.session_state.workflow_status = "error"
            st.session_state.workflow_result = {"error": str(e)}
            st.rerun()
    
    elif status == "complete":
        st.markdown(
            '<div class="workflow-status status-complete">Processing complete!</div>',
            unsafe_allow_html=True
        )
        
        result = st.session_state.workflow_result
        if result:
            docs_processed = len(result.get("extracted_documents", []))
            report_path = result.get("report_path", "")
            
            st.success(f"Processed {docs_processed} documents")
            
            if report_path and Path(report_path).exists():
                pdf_bytes = Path(report_path).read_bytes()
                st.download_button(
                    label="Download Report",
                    data=pdf_bytes,
                    file_name=Path(report_path).name,
                    mime="application/pdf",
                    use_container_width=True
                )
            
            summary = result.get("classification_summary", {})
            if summary:
                with st.expander("Classification Summary"):
                    summary_html = "<div style='font-size: 0.75rem; line-height: 1.4;'>"
                    for cat, info in sorted(summary.items()):
                        summary_html += f"<div>• {cat}: {info['count']} ({info['avg_confidence']:.0%})</div>"
                    summary_html += "</div>"
                    st.markdown(summary_html, unsafe_allow_html=True)
        
        if st.button("Clear Status", use_container_width=True):
            clear_workflow_state()
            st.rerun()
    
    elif status == "review":
        st.markdown(
            '<div class="workflow-status status-review">Awaiting human review</div>',
            unsafe_allow_html=True
        )
        st.info("Switch to Reviews tab to classify documents.")
        
        if st.button("Clear Status", use_container_width=True):
            clear_workflow_state()
            st.rerun()
    
    elif status == "error":
        st.markdown(
            '<div class="workflow-status status-error">Processing failed</div>',
            unsafe_allow_html=True
        )
        
        result = st.session_state.workflow_result
        if result and "error" in result:
            st.error(result["error"])
        
        if st.button("Clear Status", use_container_width=True):
            clear_workflow_state()
            st.rerun()


def render_chat_view():
    """Render the main chat interface."""
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Render download button if message has one attached
            if message["role"] == "assistant" and "download" in message:
                download = message["download"]
                filepath = Path(download["filepath"])
                if filepath.exists():
                    st.download_button(
                        label=f"Download {download['filename']}",
                        data=filepath.read_bytes(),
                        file_name=download["filename"],
                        mime="application/pdf",
                        key=f"history_download_{idx}",
                        type="primary",
                    )
    
    if prompt := st.chat_input("Ask your questions here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.chat_agent.chat(
                    message=prompt,
                    thread_id=st.session_state.chat_thread_id
                )
            st.markdown(response)
            
            # Check for pending download triggered by the agent
            pending_download = st.session_state.chat_agent.get_pending_download()
            if pending_download:
                filepath = Path(pending_download["filepath"])
                if filepath.exists():
                    st.download_button(
                        label=f"Download {pending_download['filename']}",
                        data=filepath.read_bytes(),
                        file_name=pending_download["filename"],
                        mime="application/pdf",
                        key=f"agent_download_{len(st.session_state.messages)}",
                        type="primary",
                    )
                    # Store download info in the message for re-rendering
                    response_with_download = {
                        "content": response,
                        "download": pending_download,
                    }
                    st.session_state.messages.append({"role": "assistant", **response_with_download})
                else:
                    st.error("Report file not found.")
                    st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                st.session_state.messages.append({"role": "assistant", "content": response})
