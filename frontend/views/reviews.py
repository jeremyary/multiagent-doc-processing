# This project was developed with assistance from AI tools.
"""
Reviews view - human review interface for document classification.
"""
from pathlib import Path

import streamlit as st

from frontend.components import render_document_card
from frontend.state import get_orchestrator


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


def render_review_view():
    """Render the human review interface."""
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
        render_document_card(doc)
        
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
            _submit_review(orchestrator)
    
    if reviewed < total:
        st.caption("Please classify all documents before submitting.")


def _submit_review(orchestrator):
    """Submit the review decisions and resume workflow."""
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
