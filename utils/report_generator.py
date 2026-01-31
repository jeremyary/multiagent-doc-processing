# This project was developed with assistance from AI tools.
from pathlib import Path
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER
from models import ClassifiedDocument, WorkflowState, WorkflowError
from config import config


def _get_styles():
    """Get configured paragraph styles for the report."""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a365d')
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#2c5282')
    ))
    
    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=5,
        textColor=colors.HexColor('#4a5568')
    ))
    
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=5,
        spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name='SmallText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray
    ))
    
    return styles


def _create_summary_table(classification_summary: dict, styles) -> Table:
    """Create a summary table of document categories."""
    data = [['Category', 'Count', 'Avg Confidence']]
    
    for category, info in sorted(classification_summary.items()):
        data.append([
            category,
            str(info['count']),
            f"{info['avg_confidence']:.0%}"
        ])
    
    total_docs = sum(info['count'] for info in classification_summary.values())
    data.append(['TOTAL', str(total_docs), '-'])
    
    table = Table(data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    
    return table


def _create_document_details(classified_docs: list[ClassifiedDocument], styles) -> list:
    """Create detailed sections for each document."""
    elements = []
    by_category: dict[str, list[ClassifiedDocument]] = {}
    for doc in classified_docs:
        if doc.category not in by_category:
            by_category[doc.category] = []
        by_category[doc.category].append(doc)
    
    for category in sorted(by_category.keys()):
        docs = by_category[category]
        
        elements.append(Paragraph(f"Category: {category}", styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        for doc in docs:
            header_text = doc.document.file_name
            if doc.human_reviewed:
                header_text += " [Human Reviewed]"
            elements.append(Paragraph(header_text, styles['SubHeader']))
            
            meta_text = f"Pages: {doc.document.page_count} | Confidence: {doc.confidence:.0%}"
            elements.append(Paragraph(meta_text, styles['SmallText']))
            elements.append(Spacer(1, 5))
            
            if doc.human_reviewed and doc.original_category:
                elements.append(Paragraph(
                    f"<b>Human Review:</b> Reclassified from '{doc.original_category}' to '{doc.category}'",
                    styles['CustomBody']
                ))
            
            if doc.document.summary:
                elements.append(Paragraph(
                    f"<b>Summary:</b> {doc.document.summary}",
                    styles['CustomBody']
                ))
            
            if doc.document.key_entities:
                entities_text = ", ".join(doc.document.key_entities[:10])
                if len(doc.document.key_entities) > 10:
                    entities_text += f" (+{len(doc.document.key_entities) - 10} more)"
                elements.append(Paragraph(
                    f"<b>Key Entities:</b> {entities_text}",
                    styles['CustomBody']
                ))
            
            if doc.reasoning:
                elements.append(Paragraph(
                    f"<b>Classification Rationale:</b> {doc.reasoning}",
                    styles['CustomBody']
                ))
            
            elements.append(Spacer(1, 15))
        
        elements.append(Spacer(1, 10))
    
    return elements


def generate_report(
    classified_docs: list[ClassifiedDocument],
    classification_summary: dict,
    output_path: Path,
    owner_id: str | None = None,
    thread_id: str | None = None
) -> str:
    """
    Generate a PDF report from classified documents.
    
    Args:
        classified_docs: List of classified documents
        classification_summary: Summary dict with category counts
        output_path: Directory to save the report
        owner_id: Optional owner identifier for access control
        thread_id: Optional thread ID for traceability
    
    Returns:
        Path to the generated report file
    """
    from utils.report_store import get_report_store
    
    styles = _get_styles()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"report_{timestamp}.pdf"
    report_path = output_path / report_filename
    
    doc = SimpleDocTemplate(
        str(report_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    elements = []
    elements.append(Paragraph("Document Analysis Report", styles['CustomTitle']))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        styles['SmallText']
    ))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Executive Summary", styles['SectionHeader']))
    total_docs = len(classified_docs)
    total_pages = sum(d.document.page_count for d in classified_docs)
    categories_found = len(classification_summary)
    human_reviewed_count = sum(1 for d in classified_docs if d.human_reviewed)
    
    summary_text = f"""
    This report summarizes the analysis of <b>{total_docs} PDF documents</b> 
    containing a total of <b>{total_pages} pages</b>. 
    The documents have been classified into <b>{categories_found} categories</b>.
    """
    elements.append(Paragraph(summary_text, styles['CustomBody']))
    
    if human_reviewed_count > 0:
        review_text = f"<b>{human_reviewed_count} document(s)</b> were manually reviewed and classified by a human reviewer."
        elements.append(Paragraph(review_text, styles['CustomBody']))
    
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Classification Summary", styles['SectionHeader']))
    elements.append(Spacer(1, 10))
    elements.append(_create_summary_table(classification_summary, styles))
    elements.append(Spacer(1, 30))
    elements.append(PageBreak())
    elements.append(Paragraph("Detailed Document Analysis", styles['CustomTitle']))
    elements.append(Spacer(1, 20))
    elements.extend(_create_document_details(classified_docs, styles))
    doc.build(elements)
    
    # Build detailed classification summary for storage
    detailed_summary = {}
    for doc_item in classified_docs:
        cat = doc_item.category
        if cat not in detailed_summary:
            detailed_summary[cat] = {
                "count": 0,
                "documents": []
            }
        detailed_summary[cat]["count"] += 1
        detailed_summary[cat]["documents"].append({
            "name": doc_item.document.file_name,
            "confidence": doc_item.confidence,
            "human_reviewed": doc_item.human_reviewed,
        })
    
    # Register report metadata for access control
    store = get_report_store()
    store.register_report(
        filename=report_filename,
        owner_id=owner_id,
        thread_id=thread_id,
        document_count=len(classified_docs),
        classification_summary=detailed_summary
    )
    
    return str(report_path)


def generate_report_from_state(state: WorkflowState) -> dict:
    """
    Generate report from workflow state. Used directly as a LangGraph node.
    
    Args:
        state: Current workflow state
    
    Returns:
        Dict with report results to merge into state
    """
    print("\n" + "="*60)
    print("STEP 3: Report Generation")
    print("="*60)
    print("[Report Generator] Starting report generation...")
    
    classified_docs = state.get("classified_documents", [])
    classification_summary = state.get("classification_summary", {})
    owner_id = state.get("owner_id")
    
    if not classified_docs:
        print("[Report Generator] No classified documents to report on")
        return {
            "report_path": "",
            "report_generated": False,
            "messages": ["No documents to include in report"]
        }
    
    try:
        output_dir = config.OUTPUT_REPORT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = generate_report(
            classified_docs,
            classification_summary,
            output_dir,
            owner_id=owner_id
        )
        
        print(f"[Report Generator] Report generated: {report_path}")
        
        return {
            "report_path": report_path,
            "report_generated": True,
            "messages": [f"Report generated successfully: {report_path}"]
        }
        
    except PermissionError as e:
        error = WorkflowError(
            code="REPORT_PERMISSION_DENIED",
            message=f"Permission denied writing report: {e}",
            severity="critical",
            recoverable=False,
            node="report_generator",
            details={"output_dir": str(config.OUTPUT_REPORT_DIR)},
        )
        print(f"[Report Generator] [CRITICAL] {error.message}")
        
        return {
            "report_path": "",
            "report_generated": False,
            "workflow_errors": [error],
            "messages": [error.message]
        }
        
    except Exception as e:
        error = WorkflowError(
            code="REPORT_GENERATION_FAILED",
            message=f"Failed to generate report: {str(e)}",
            severity="error",
            recoverable=True,
            node="report_generator",
            details={"error_type": type(e).__name__},
        )
        print(f"[Report Generator] [ERROR] {error.message}")
        
        return {
            "report_path": "",
            "report_generated": False,
            "workflow_errors": [error],
            "messages": [error.message]
        }
