# This project was developed with assistance from AI tools.
"""
Shared UI components for the Streamlit frontend.
"""
from pathlib import Path

import streamlit as st

from frontend.auth import get_authenticator, get_current_user


def render_logo():
    """Render the application logo in the sidebar."""
    logo_path = Path(__file__).parent / "mort-logo.png"
    if logo_path.exists():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(str(logo_path), width=300)
        st.markdown("")  # Spacing


def render_top_bar(title: str, subtitle: str = ""):
    """Render the top bar with page title on left, user info and logout on right."""
    user = get_current_user()
    if not user:
        return
    
    col1, col2, col3 = st.columns([6, 2, 1])
    
    with col1:
        st.markdown(f'<div class="main-header">{title}</div>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="sub-header">{subtitle}</div>', unsafe_allow_html=True)
    
    with col2:
        role_display = "Admin" if user.is_admin else "Borrower"
        st.markdown(
            f"<div style='text-align: right; padding-top: 0.25rem; color: #9ca3af; font-size: 0.9rem;'>"
            f"<strong>{user.name}</strong> ({role_display})"
            f"</div>",
            unsafe_allow_html=True
        )
    
    with col3:
        authenticator = get_authenticator()
        authenticator.logout(button_name="Logout", location="main")


def render_workflow_status(status: str, css_class: str, message: str):
    """Render a workflow status indicator."""
    st.markdown(
        f'<div class="workflow-status {css_class}">{message}</div>',
        unsafe_allow_html=True
    )


def render_document_card(doc: dict):
    """Render a document card for review display."""
    st.markdown(f"""
    <div class="doc-card">
        <div class="doc-title">{doc['file_name']}</div>
        <div class="doc-detail"><strong>Pages:</strong> {doc.get('page_count', 'N/A')}</div>
        <div class="doc-detail"><strong>Summary:</strong> {doc.get('summary', 'No summary available')}</div>
        <div class="doc-detail"><strong>Key Entities:</strong> {', '.join(doc.get('key_entities', []) or ['None detected'])}</div>
        <div class="doc-detail"><strong>AI Reasoning:</strong> {doc.get('ai_reasoning', 'N/A')}</div>
    </div>
    """, unsafe_allow_html=True)
