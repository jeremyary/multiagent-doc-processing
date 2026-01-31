# This project was developed with assistance from AI tools.
"""
Streamlit-based chat UI for mortgage document assistance.

Run with: streamlit run frontend/app.py
"""
import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import get_chat_agent
from orchestrator import create_orchestrator
from config import config
from frontend.auth import (
    render_login, render_logout, render_user_info,
    get_current_user, get_user_thread_prefix, get_user_upload_dir
)

# Page configuration
st.set_page_config(
    page_title="Mortgage Document Assistant",
    page_icon="page_facing_up",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .main-header {
        font-size: 1.8rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #1f2937;
    }
    .sub-header {
        font-size: 0.9rem;
        color: #6b7280;
        margin-bottom: 1.5rem;
    }
    .session-info {
        font-size: 0.8rem;
        color: #9ca3af;
        padding: 0.5rem;
        background: #f3f4f6;
        border-radius: 0.25rem;
        margin-bottom: 1rem;
    }
    .workflow-status {
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .status-running {
        background: #fef3c7;
        border-left: 4px solid #f59e0b;
    }
    .status-complete {
        background: #d1fae5;
        border-left: 4px solid #10b981;
    }
    .status-error {
        background: #fee2e2;
        border-left: 4px solid #ef4444;
    }
    .status-review {
        background: #e0e7ff;
        border-left: 4px solid #6366f1;
    }
    .doc-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .doc-title {
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }
    .doc-detail {
        font-size: 0.85rem;
        color: #4b5563;
        margin-bottom: 0.25rem;
    }
    /* Sidebar tab buttons - smaller font, no wrap */
    section[data-testid="stSidebar"] .stButton button {
        font-size: 0.75rem;
        white-space: nowrap;
        padding: 0.4rem 0.5rem;
    }
    /* Report info box */
    .report-info {
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


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
    """Initialize session state variables."""
    user = get_current_user()
    user_prefix = get_user_thread_prefix()
    
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
        session_id=owner_id,  # Ties to same LangFuse session as chat
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
            # Create display name from metadata
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
            # Legacy file - show to admins or if no user filter
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
    
    # Sort by modification time
    reports.sort(key=lambda r: r["modified"], reverse=True)
    return reports


def render_sidebar():
    """Render the sidebar with session management and document processing."""
    user = get_current_user()
    
    with st.sidebar:
        # User info and logout
        render_user_info()
        render_logout()
        st.divider()
        
        # View mode toggle - tabs depend on user role
        can_review = user and user.can_review_documents()
        
        if can_review:
            # Admin: show all 3 tabs
            col1, col2, col3 = st.columns(3)
        else:
            # Borrower: only Chat and Reports
            col1, col2 = st.columns(2)
            col3 = None
        
        with col1:
            if st.button("Chat", use_container_width=True, 
                        type="primary" if st.session_state.view_mode == "chat" else "secondary"):
                st.session_state.view_mode = "chat"
                st.rerun()
        
        if can_review:
            with col2:
                orchestrator = get_orchestrator(force_new=True)
                pending_count = len(orchestrator.list_pending_reviews())
                btn_label = f"Reviews ({pending_count})" if pending_count > 0 else "Reviews"
                if st.button(btn_label, use_container_width=True,
                            type="primary" if st.session_state.view_mode == "review" else "secondary"):
                    st.session_state.view_mode = "review"
                    st.rerun()
            reports_col = col3
        else:
            reports_col = col2
        
        with reports_col:
            reports = list_reports()
            report_count = len(reports)
            btn_label = f"Reports ({report_count})" if report_count > 0 else "Reports"
            if st.button(btn_label, use_container_width=True,
                        type="primary" if st.session_state.view_mode == "reports" else "secondary"):
                st.session_state.view_mode = "reports"
                st.rerun()
        
        st.divider()
        
        if st.session_state.view_mode == "chat":
            render_chat_sidebar()
        elif st.session_state.view_mode == "review":
            render_review_sidebar()
        else:
            render_reports_sidebar()


def render_chat_sidebar():
    """Render chat-related sidebar content."""
    st.markdown("### Chat Sessions")
    
    st.markdown(
        f'<div class="session-info">Thread: {st.session_state.chat_thread_id}</div>',
        unsafe_allow_html=True
    )
    
    if st.button("New Chat Session", use_container_width=True):
        user_prefix = get_user_thread_prefix()
        st.session_state.chat_thread_id = f"{user_prefix}chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        st.session_state.messages = []
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
            for session_id in sessions[-10:]:
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
                # Create a unique directory for this upload batch
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
        st.divider()
        st.markdown("### Workflow Status")
        
        if st.session_state.workflow_status == "running":
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
        
        elif st.session_state.workflow_status == "complete":
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
                st.session_state.workflow_status = None
                st.session_state.workflow_result = None
                st.session_state.uploaded_files = []
                st.session_state.upload_dir = None
                st.rerun()
        
        elif st.session_state.workflow_status == "review":
            st.markdown(
                '<div class="workflow-status status-review">Awaiting human review</div>',
                unsafe_allow_html=True
            )
            st.info("Switch to Reviews tab to classify documents.")
            
            if st.button("Clear Status", use_container_width=True):
                st.session_state.workflow_status = None
                st.session_state.workflow_result = None
                st.session_state.uploaded_files = []
                st.session_state.upload_dir = None
                st.rerun()
        
        elif st.session_state.workflow_status == "error":
            st.markdown(
                '<div class="workflow-status status-error">Processing failed</div>',
                unsafe_allow_html=True
            )
            
            result = st.session_state.workflow_result
            if result and "error" in result:
                st.error(result["error"])
            
            if st.button("Clear Status", use_container_width=True):
                st.session_state.workflow_status = None
                st.session_state.workflow_result = None
                st.session_state.uploaded_files = []
                st.session_state.upload_dir = None
                st.rerun()


def render_review_sidebar():
    """Render review-related sidebar content."""
    st.markdown("### Pending Reviews")
    
    # Force fresh orchestrator to get latest checkpoint data
    orchestrator = get_orchestrator(force_new=True)
    pending = orchestrator.list_pending_reviews()
    
    if not pending:
        st.info("No workflows awaiting review")
        return
    
    for review in pending:
        thread_id = review["thread_id"]
        doc_count = len(review["documents"])
        
        is_active = st.session_state.active_review == thread_id
        btn_type = "primary" if is_active else "secondary"
        
        if st.button(f"{thread_id} ({doc_count} docs)", key=f"review_{thread_id}", 
                    use_container_width=True, type=btn_type):
            st.session_state.active_review = thread_id
            st.session_state.review_decisions = {}
            st.rerun()


def render_reports_sidebar():
    """Render reports-related sidebar content."""
    st.markdown("### Generated Reports")
    
    reports = list_reports()
    
    if not reports:
        st.info("No reports generated yet")
        return
    
    for report in reports[:20]:  # Show last 20 reports
        is_selected = st.session_state.get("selected_report") == report["name"]
        btn_type = "primary" if is_selected else "secondary"
        
        # Use display name for cleaner UI
        display = report.get("display_name", report["name"])
        
        if st.button(display, key=f"report_{report['name']}", 
                    use_container_width=True, type=btn_type):
            st.session_state.selected_report = report["name"]
            st.rerun()


def render_chat():
    """Render the main chat interface."""
    st.markdown('<div class="main-header">Mortgage Document Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Ask questions about mortgage documents, requirements, and the loan process</div>',
        unsafe_allow_html=True
    )
    
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
    
    if prompt := st.chat_input("Ask about mortgage documents..."):
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


def render_review_panel():
    """Render the human review interface."""
    st.markdown('<div class="main-header">Human Review</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Classify documents that could not be automatically categorized</div>',
        unsafe_allow_html=True
    )
    
    if not st.session_state.active_review:
        st.info("Select a pending review from the sidebar to begin.")
        return
    
    orchestrator = get_orchestrator()
    pending = orchestrator.list_pending_reviews()
    
    # Find the active review
    active = None
    for review in pending:
        if review["thread_id"] == st.session_state.active_review:
            active = review
            break
    
    if not active:
        st.warning("Selected review is no longer pending.")
        st.session_state.active_review = None
        return
    
    documents = active["documents"]
    categories = active["categories"]
    
    st.markdown(f"**Thread:** `{active['thread_id']}`")
    st.markdown(f"**Documents to review:** {len(documents)}")
    
    st.divider()
    
    # Build category options
    category_options = ["-- Select Category --"] + categories + ["Confirm as Unknown (Irrelevant)", "Skip (Keep Current)"]
    
    # Display each document with classification dropdown
    for i, doc in enumerate(documents):
        st.markdown(f"""
        <div class="doc-card">
            <div class="doc-title">{doc['file_name']}</div>
            <div class="doc-detail"><strong>Pages:</strong> {doc.get('page_count', 'N/A')}</div>
            <div class="doc-detail"><strong>Summary:</strong> {doc.get('summary', 'No summary available')}</div>
            <div class="doc-detail"><strong>Key Entities:</strong> {', '.join(doc.get('key_entities', []) or ['None detected'])}</div>
            <div class="doc-detail"><strong>AI Reasoning:</strong> {doc.get('ai_reasoning', 'N/A')}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Get current selection
        current = st.session_state.review_decisions.get(doc['file_name'], "-- Select Category --")
        try:
            default_index = category_options.index(current)
        except ValueError:
            default_index = 0
        
        selection = st.selectbox(
            f"Category for {doc['file_name']}",
            options=category_options,
            index=default_index,
            key=f"cat_{i}_{doc['file_name']}",
            label_visibility="collapsed"
        )
        
        # Store decision
        if selection != "-- Select Category --":
            if selection == "Confirm as Unknown (Irrelevant)":
                st.session_state.review_decisions[doc['file_name']] = "confirm_unknown"
            elif selection == "Skip (Keep Current)":
                st.session_state.review_decisions[doc['file_name']] = "skip"
            else:
                st.session_state.review_decisions[doc['file_name']] = selection
        elif doc['file_name'] in st.session_state.review_decisions:
            del st.session_state.review_decisions[doc['file_name']]
        
        st.markdown("---")
    
    # Summary and submit
    reviewed = len(st.session_state.review_decisions)
    total = len(documents)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**Reviewed:** {reviewed} / {total}")
    
    with col2:
        if st.button("Submit Review", type="primary", use_container_width=True, 
                    disabled=(reviewed < total)):
            with st.spinner("Resuming workflow..."):
                try:
                    result = orchestrator.resume_with_decisions(
                        st.session_state.active_review,
                        st.session_state.review_decisions
                    )
                    
                    if "__interrupt__" in result:
                        st.warning("Additional review required")
                    elif result.get("report_generated"):
                        st.success("Workflow completed!")
                        report_path = result.get("report_path", "")
                        if report_path and Path(report_path).exists():
                            pdf_bytes = Path(report_path).read_bytes()
                            st.download_button(
                                label="Download Report",
                                data=pdf_bytes,
                                file_name=Path(report_path).name,
                                mime="application/pdf",
                                use_container_width=True
                            )
                    
                    # Clear review state
                    st.session_state.active_review = None
                    st.session_state.review_decisions = {}
                    st.session_state.workflow_status = None
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Failed to resume workflow: {e}")
    
    if reviewed < total:
        st.caption("Please classify all documents before submitting.")


def render_reports_panel():
    """Render the reports viewing interface."""
    import base64
    
    st.markdown('<div class="main-header">Document Reports</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">View and download generated classification reports</div>',
        unsafe_allow_html=True
    )
    
    reports = list_reports()
    
    if not reports:
        st.info("No reports have been generated yet. Process some documents to create a report.")
        return
    
    # Auto-select most recent report if none selected
    selected_report = st.session_state.get("selected_report")
    if not selected_report:
        selected_report = reports[0]["name"]
        st.session_state.selected_report = selected_report
    
    # Find the selected report
    report = next((r for r in reports if r["name"] == selected_report), None)
    
    if not report:
        # Fallback to most recent if selected not found
        report = reports[0]
        st.session_state.selected_report = report["name"]
    
    # Report info bar
    display = report.get("display_name", report["name"])
    doc_count = report.get("document_count", 0)
    owner = report.get("owner_id") or "cli"
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{display}**")
        st.caption(f"Owner: {owner} | Documents: {doc_count}")
    with col2:
        size_str = f"{report['size_kb']:.0f} KB" if report['size_kb'] < 1024 else f"{report['size_kb']/1024:.1f} MB"
        st.caption(f"Size: {size_str}")
    
    # Read PDF once for both download and preview
    pdf_bytes = report["path"].read_bytes()
    
    # Download button
    st.download_button(
        label="Download Report",
        data=pdf_bytes,
        file_name=report["name"],
        mime="application/pdf",
    )
    
    st.divider()
    
    # PDF preview using iframe
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf" style="border: 1px solid #e5e7eb; border-radius: 0.5rem;"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)


def main():
    """Main application entry point."""
    # Validate config first
    try:
        config.validate()
    except ValueError as e:
        st.error(f"Configuration Error: {e}")
        st.info("Please ensure OPENAI_API_KEY is set in your .env file")
        return
    
    # Authentication gate
    if not render_login():
        st.markdown("---")
        st.markdown("**Demo Credentials:**")
        st.markdown("- Admin: `admin` / `admin123`")
        st.markdown("- Borrower: `borrower` / `borrower123`")
        return
    
    # User is authenticated - initialize and render app
    init_session_state()
    render_sidebar()
    
    user = get_current_user()
    
    if st.session_state.view_mode == "chat":
        render_chat()
    elif st.session_state.view_mode == "review":
        # Double-check permission (shouldn't reach here for borrowers)
        if user and user.can_review_documents():
            render_review_panel()
        else:
            st.error("You don't have permission to access document reviews.")
            st.session_state.view_mode = "chat"
            st.rerun()
    else:
        render_reports_panel()


if __name__ == "__main__":
    main()
