# This project was developed with assistance from AI tools.
"""
Reports view - view and download generated classification reports.
"""
import base64

import streamlit as st

from frontend.workflow import list_reports


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


def render_reports_view():
    """Render the reports viewing interface."""
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
