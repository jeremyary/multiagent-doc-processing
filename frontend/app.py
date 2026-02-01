# This project was developed with assistance from AI tools.
"""
Streamlit-based chat UI for mortgage document assistance.

Run with: streamlit run frontend/app.py
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from config import config
from frontend.auth import get_current_user
from frontend.components import render_logo, render_top_bar
from frontend.state import get_orchestrator, init_session_state
from frontend.views import (
    render_chat_sidebar,
    render_chat_view,
    render_landing_page,
    render_reports_sidebar,
    render_reports_view,
    render_review_sidebar,
    render_review_view,
)
from frontend.workflow import list_reports

# Page configuration
st.set_page_config(
    page_title="Mortgage Assistant",
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
        color: #3973b5;
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
    /* Landing page styles */
    .stMetric {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #bae6fd;
    }
    .stMetric label {
        color: #0369a1 !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #0c4a6e !important;
        font-weight: 700;
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


def render_sidebar():
    """Render the sidebar with navigation and context-specific content."""
    user = get_current_user()
    
    with st.sidebar:
        render_logo()
        st.divider()
        
        # View mode toggle - tabs depend on user role
        can_review = user and user.can_review_documents()
        
        if can_review:
            col1, col2, col3 = st.columns(3)
        else:
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
        
        # Render view-specific sidebar content
        if st.session_state.view_mode == "chat":
            render_chat_sidebar()
        elif st.session_state.view_mode == "review":
            render_review_sidebar()
        else:
            render_reports_sidebar()


def main():
    """Main application entry point."""
    # Validate config first
    try:
        config.validate()
    except ValueError as e:
        st.error(f"Configuration Error: {e}")
        st.info("Please ensure OPENAI_API_KEY is set in your .env file")
        return
    
    # Check authentication status
    user = get_current_user()
    
    if not user:
        # Show landing page with calculator and login
        render_landing_page()
        
        # Check if user just logged in
        if st.session_state.get("authentication_status"):
            # Clear anonymous chat when logging in
            if "anon_messages" in st.session_state:
                del st.session_state.anon_messages
            st.rerun()
        return
    
    # User is authenticated - initialize and render app
    init_session_state()
    render_sidebar()
    
    if st.session_state.view_mode == "chat":
        render_top_bar("Hi, I'm your Mortgage Assistant!", "Ask me about mortgage regulations, requirements, or the loan process.")
        render_chat_view()
    elif st.session_state.view_mode == "review":
        if user.can_review_documents():
            render_top_bar("Human Review", "Classify documents that could not be automatically categorized")
            render_review_view()
        else:
            st.error("You don't have permission to access document reviews.")
            st.session_state.view_mode = "chat"
            st.rerun()
    else:
        render_top_bar("Document Reports", "View and download generated classification reports")
        render_reports_view()


if __name__ == "__main__":
    main()
