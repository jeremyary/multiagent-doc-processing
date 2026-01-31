# This project was developed with assistance from AI tools.
"""
Human-in-the-loop review for documents with unknown relevance.
"""
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from config import config as app_config
from models import ClassifiedDocument, WorkflowState


def review_unknown_documents(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Review documents classified as 'Unknown Relevance' using LangGraph interrupt.
    
    This function pauses the workflow and returns review data to the caller.
    The caller handles the UI/CLI interaction and resumes with human decisions.
    
    Args:
        state: Current workflow state
        config: RunnableConfig containing thread_id and other settings
        
    Returns:
        Updated state with reclassified documents
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    
    classified_docs = state.get("classified_documents", [])
    unknown_docs = [doc for doc in classified_docs if doc.category == "Unknown Relevance"]
    
    if not unknown_docs:
        return {"messages": ["No documents require manual review"]}
    
    # Prepare review data for the caller (UI/CLI)
    categories = [cat for cat in app_config.DOCUMENT_CATEGORIES if cat != "Unknown Relevance"]
    
    review_requests = []
    for doc in unknown_docs:
        review_requests.append({
            "file_name": doc.document.file_name,
            "page_count": doc.document.page_count,
            "summary": doc.document.summary[:300] + "..." if len(doc.document.summary or "") > 300 else doc.document.summary,
            "key_entities": doc.document.key_entities[:8],
            "ai_reasoning": doc.reasoning,
        })
    
    # Interrupt and wait for human input
    # The caller receives this data and must resume with Command(resume=decisions)
    human_decisions = interrupt({
        "type": "human_review",
        "message": f"{len(unknown_docs)} document(s) require manual classification",
        "thread_id": thread_id,
        "categories": categories,
        "documents": review_requests,
    })
    
    # When resumed, human_decisions contains the user's choices
    # Expected format: {filename: category_or_none, ...}
    return apply_human_decisions(classified_docs, human_decisions, categories)


def apply_human_decisions(
    classified_docs: list[ClassifiedDocument],
    decisions: dict[str, str | None],
    categories: list[str]
) -> dict:
    """
    Apply human review decisions to classified documents.
    
    Args:
        classified_docs: All classified documents
        decisions: Dict mapping filename to chosen category (or None to skip)
        categories: Valid category list
        
    Returns:
        Updated state dict
    """
    updated_docs = []
    reclassified_count = 0
    
    for doc in classified_docs:
        if doc.category != "Unknown Relevance":
            updated_docs.append(doc)
            continue
        
        decision = decisions.get(doc.document.file_name)
        
        if decision is None or decision == "skip":
            # Keep original classification
            updated_docs.append(doc)
        elif decision == "confirm_unknown":
            # Human confirmed it's irrelevant
            updated_doc = ClassifiedDocument(
                document=doc.document,
                category="Unknown Relevance",
                confidence=1.0,
                sub_categories=doc.sub_categories,
                reasoning="Confirmed as irrelevant to mortgage process by human reviewer",
                human_reviewed=True,
                original_category="Unknown Relevance"
            )
            updated_docs.append(updated_doc)
        elif decision in categories:
            # Human reclassified to a specific category
            updated_doc = ClassifiedDocument(
                document=doc.document,
                category=decision,
                confidence=1.0,
                sub_categories=doc.sub_categories,
                reasoning="Manually reclassified by human reviewer",
                human_reviewed=True,
                original_category="Unknown Relevance"
            )
            updated_docs.append(updated_doc)
            reclassified_count += 1
        else:
            # Invalid decision, keep original
            updated_docs.append(doc)
    
    # Rebuild classification summary
    new_summary = {}
    for doc in updated_docs:
        cat = doc.category
        if cat not in new_summary:
            new_summary[cat] = {"count": 0, "total_confidence": 0.0}
        new_summary[cat]["count"] += 1
        new_summary[cat]["total_confidence"] += doc.confidence
    
    for cat in new_summary:
        count = new_summary[cat]["count"]
        new_summary[cat]["avg_confidence"] = new_summary[cat]["total_confidence"] / count if count > 0 else 0
        del new_summary[cat]["total_confidence"]
    
    return {
        "classified_documents": updated_docs,
        "classification_summary": new_summary,
        "messages": [f"Human review complete: {reclassified_count} documents reclassified"]
    }


def collect_human_review_cli(interrupt_data: dict) -> dict[str, str | None]:
    """
    CLI interface to collect human review decisions.
    
    This function is called by main.py when an interrupt is detected.
    
    Args:
        interrupt_data: The data passed to interrupt() containing documents to review
        
    Returns:
        Dict mapping filename to chosen category (or None/skip/confirm_unknown)
    """
    print("\n" + "="*60)
    print("HUMAN REVIEW: Unknown Relevance Documents")
    print("="*60)
    
    thread_id = interrupt_data.get("thread_id")
    documents = interrupt_data.get("documents", [])
    categories = interrupt_data.get("categories", [])
    
    print(f"\n{len(documents)} document(s) require manual classification.\n")
    
    print("Available categories:")
    for i, cat in enumerate(categories, 1):
        print(f"  {i:2}. {cat}")
    print(f"  {len(categories) + 1:2}. Confirm as Unknown Relevance (irrelevant to mortgage)")
    print(f"   0. Skip this document (keep current classification)")
    print()
    
    decisions: dict[str, str | None] = {}
    
    for doc_info in documents:
        print("-" * 50)
        print(f"Document: {doc_info['file_name']}")
        print(f"Pages: {doc_info['page_count']}")
        if doc_info.get('summary'):
            print(f"Summary: {doc_info['summary']}")
        if doc_info.get('key_entities'):
            entities = ", ".join(doc_info['key_entities'])
            print(f"Key Entities: {entities}")
        if doc_info.get('ai_reasoning'):
            print(f"AI Reasoning: {doc_info['ai_reasoning']}")
        print()
        
        while True:
            try:
                choice = input(f"Select category (1-{len(categories) + 1}, or 0 to skip): ").strip()
                
                if not choice:
                    continue
                    
                choice_num = int(choice)
                
                if choice_num == 0:
                    decisions[doc_info['file_name']] = "skip"
                    print("  -> Skipped (keeping Unknown Relevance)\n")
                    break
                elif 1 <= choice_num <= len(categories):
                    new_category = categories[choice_num - 1]
                    decisions[doc_info['file_name']] = new_category
                    print(f"  -> Reclassified as: {new_category}\n")
                    break
                elif choice_num == len(categories) + 1:
                    decisions[doc_info['file_name']] = "confirm_unknown"
                    print("  -> Confirmed as Unknown Relevance\n")
                    break
                else:
                    print(f"  Invalid choice. Please enter 0-{len(categories) + 1}")
            except ValueError:
                print(f"  Invalid input. Please enter a number 0-{len(categories) + 1}")
            except KeyboardInterrupt:
                print(f"\n\n  Review interrupted. Resume with: --thread-id {thread_id}")
                raise  # Re-raise to propagate up and preserve checkpoint state
    
    print("="*60)
    reclassified = sum(1 for d in decisions.values() if d not in (None, "skip", "confirm_unknown"))
    print(f"Review complete. {reclassified} document(s) reclassified.")
    print("="*60)
    
    return decisions
