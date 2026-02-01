# This project was developed with assistance from AI tools.
"""Document and report tools - access user's processed documents and reports."""
import logging
from pathlib import Path

from langchain_core.tools import tool

from config import config
from prompts import TOOL_GET_MY_DOCUMENTS, TOOL_GET_MY_REPORTS, TOOL_PREPARE_DOWNLOAD

from . import ToolContext

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create document and report tools."""
    
    @tool(description=TOOL_GET_MY_REPORTS)
    def get_my_reports() -> str:
        """List the user's document analysis reports."""
        user_id = context.get_user_id()
        if not user_id:
            return "Unable to identify user."
        
        try:
            from utils.report_store import get_report_store
            store = get_report_store()
            reports = store.get_reports(owner_id=user_id)
            
            if not reports:
                return "You don't have any reports yet. Upload and process documents to generate a report."
            
            lines = [f"You have {len(reports)} report(s):\n"]
            
            for r in reports[:5]:
                date = r["created_at"][:10]
                doc_count = r.get("document_count", 0)
                lines.append(f"Report from {date} ({doc_count} documents):")
                
                summary = r.get("classification_summary")
                if summary:
                    for category, data in sorted(summary.items()):
                        count = data.get("count", 0)
                        docs = data.get("documents", [])
                        lines.append(f"  {category}: {count} document(s)")
                        for doc in docs[:3]:
                            conf = doc.get("confidence", 0)
                            reviewed = " [human reviewed]" if doc.get("human_reviewed") else ""
                            lines.append(f"    - {doc['name']} ({conf:.0%}){reviewed}")
                        if len(docs) > 3:
                            lines.append(f"    ... and {len(docs) - 3} more")
                else:
                    lines.append("  (No classification details available)")
                lines.append("")
            
            if len(reports) > 5:
                lines.append(f"... and {len(reports) - 5} older report(s)")
            
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to retrieve reports: {e}")
            return "Failed to retrieve report information."
    
    @tool(description=TOOL_GET_MY_DOCUMENTS)
    def get_my_documents() -> str:
        """List the user's processed documents."""
        user_id = context.get_user_id()
        if not user_id:
            return "Unable to identify user."
        
        try:
            from utils.document_cache import DocumentCache
            
            cache = DocumentCache()
            
            uploads_dir = Path("uploads") / user_id
            if not uploads_dir.exists():
                return "You haven't uploaded any documents yet."
            
            unique_docs = {}
            batch_dirs = sorted(uploads_dir.glob("batch-*"), reverse=True)
            
            for batch_dir in batch_dirs:
                for pdf in batch_dir.glob("*.pdf"):
                    if pdf.name in unique_docs:
                        continue
                    
                    try:
                        content_hash = cache.compute_hash(pdf)
                        classified = cache.get_classification(content_hash)
                        if classified:
                            unique_docs[pdf.name] = {
                                "name": pdf.name,
                                "category": classified.category,
                                "confidence": classified.confidence,
                            }
                        else:
                            unique_docs[pdf.name] = {
                                "name": pdf.name,
                                "category": "Not yet classified",
                                "confidence": 0,
                            }
                    except Exception:
                        unique_docs[pdf.name] = {
                            "name": pdf.name,
                            "category": "Unknown",
                            "confidence": 0,
                        }
            
            documents = list(unique_docs.values())
            
            if not documents:
                return "No documents found in your upload history."
            
            by_category = {}
            for doc in documents:
                cat = doc["category"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(doc["name"])
            
            lines = [f"You have {len(documents)} unique document(s) on file:"]
            for category, files in sorted(by_category.items()):
                lines.append(f"\n{category} ({len(files)}):")
                for f in sorted(files):
                    conf = next((d["confidence"] for d in documents if d["name"] == f), 0)
                    if conf > 0:
                        lines.append(f"  - {f} ({conf:.0%} confidence)")
                    else:
                        lines.append(f"  - {f}")
            
            lines.append(f"\nDocuments from {len(batch_dirs)} upload session(s).")
            
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to retrieve documents: {e}")
            return "Failed to retrieve document information."
    
    @tool(description=TOOL_PREPARE_DOWNLOAD)
    def prepare_report_download(report_id: int | None = None, confirmed: bool = False) -> str:
        """Prepare a report for download."""
        user_id = context.get_user_id()
        if not user_id:
            return "Unable to identify user."
        
        try:
            from utils.report_store import get_report_store
            
            store = get_report_store()
            
            if report_id is None:
                reports = store.get_reports(owner_id=user_id)
                if not reports:
                    return "You don't have any reports to download."
                report = reports[0]
                report_id = report["id"]
            else:
                report = store.get_report_by_id(report_id, owner_id=user_id)
                if not report:
                    return "Report not found or you don't have access to it."
            
            report_path = config.OUTPUT_REPORT_DIR / report["filename"]
            if not report_path.exists():
                return "The report file is no longer available."
            
            if not confirmed:
                date = report["created_at"][:10]
                doc_count = report.get("document_count", 0)
                
                details = [
                    f"I found this report ready for download:",
                    f"",
                    f"  Report ID: {report_id}",
                    f"  Date: {date}",
                    f"  Documents: {doc_count}",
                    f"  Filename: {report['filename']}",
                    f"",
                    f"Would you like me to prepare this report for download?",
                ]
                return "\n".join(details)
            else:
                context.set_pending_download({
                    "report_id": report_id,
                    "filename": report["filename"],
                    "filepath": str(report_path),
                })
                return f"Your report '{report['filename']}' is ready. A download button will appear below."
        
        except Exception as e:
            logger.warning(f"Failed to prepare download: {e}")
            return "Failed to prepare report for download."
    
    return [get_my_reports, get_my_documents, prepare_report_download]
