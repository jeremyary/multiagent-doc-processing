# This project was developed with assistance from AI tools.
from models import ClassifiedDocument, WorkflowState
from config import config


def review_unknown_documents(state: WorkflowState) -> dict:
    """
    Review documents classified as 'Unknown Relevance' and allow human reclassification.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with reclassified documents
    """
    classified_docs = state.get("classified_documents", [])
    unknown_docs = [doc for doc in classified_docs if doc.category == "Unknown Relevance"]
    
    if not unknown_docs:
        return {"messages": ["No documents require manual review"]}
    
    print("\n" + "="*60)
    print("HUMAN REVIEW: Unknown Relevance Documents")
    print("="*60)
    print(f"\n{len(unknown_docs)} document(s) require manual classification.\n")
    
    categories = [cat for cat in config.DOCUMENT_CATEGORIES if cat != "Unknown Relevance"]
    
    print("Available categories:")
    for i, cat in enumerate(categories, 1):
        print(f"  {i:2}. {cat}")
    print(f"  {len(categories) + 1:2}. Confirm as Unknown Relevance (irrelevant to mortgage)")
    print(f"   0. Skip this document (keep current classification)")
    print()
    
    updated_docs = []
    reclassified_count = 0
    
    for doc in classified_docs:
        if doc.category != "Unknown Relevance":
            updated_docs.append(doc)
            continue
        
        print("-" * 50)
        print(f"Document: {doc.document.file_name}")
        print(f"Pages: {doc.document.page_count}")
        if doc.document.summary:
            summary = doc.document.summary
            if len(summary) > 300:
                summary = summary[:300] + "..."
            print(f"Summary: {summary}")
        if doc.document.key_entities:
            entities = ", ".join(doc.document.key_entities[:8])
            if len(doc.document.key_entities) > 8:
                entities += f" (+{len(doc.document.key_entities) - 8} more)"
            print(f"Key Entities: {entities}")
        if doc.reasoning:
            print(f"AI Reasoning: {doc.reasoning}")
        print()
        
        while True:
            try:
                choice = input(f"Select category (1-{len(categories) + 1}, or 0 to skip): ").strip()
                
                if not choice:
                    continue
                    
                choice_num = int(choice)
                
                if choice_num == 0:
                    updated_docs.append(doc)
                    print("  -> Skipped (keeping Unknown Relevance)\n")
                    break
                elif 1 <= choice_num <= len(categories):
                    new_category = categories[choice_num - 1]
                    updated_doc = ClassifiedDocument(
                        document=doc.document,
                        category=new_category,
                        confidence=1.0,  # Human classification = 100% confidence
                        sub_categories=doc.sub_categories,
                        reasoning=f"Manually reclassified by human reviewer",
                        human_reviewed=True,
                        original_category="Unknown Relevance"
                    )
                    updated_docs.append(updated_doc)
                    reclassified_count += 1
                    print(f"  -> Reclassified as: {new_category}\n")
                    break
                elif choice_num == len(categories) + 1:
                    updated_doc = ClassifiedDocument(
                        document=doc.document,
                        category="Unknown Relevance",
                        confidence=1.0,  # Human confirmed = 100% confidence
                        sub_categories=doc.sub_categories,
                        reasoning="Confirmed as irrelevant to mortgage process by human reviewer",
                        human_reviewed=True,
                        original_category="Unknown Relevance"
                    )
                    updated_docs.append(updated_doc)
                    print("  -> Confirmed as Unknown Relevance\n")
                    break
                else:
                    print(f"  Invalid choice. Please enter 0-{len(categories) + 1}")
            except ValueError:
                print(f"  Invalid input. Please enter a number 0-{len(categories) + 1}")
            except KeyboardInterrupt:
                print("\n\n  Review interrupted. Keeping remaining documents as-is.")
                remaining_idx = classified_docs.index(doc)
                for remaining_doc in classified_docs[remaining_idx:]:
                    if remaining_doc not in updated_docs:
                        updated_docs.append(remaining_doc)
                break
    
    new_summary = {}
    for doc in updated_docs:
        cat = doc.category
        if cat not in new_summary:
            new_summary[cat] = {"count": 0, "total_confidence": 0.0, "avg_confidence": 0.0}
        new_summary[cat]["count"] += 1
        new_summary[cat]["total_confidence"] += doc.confidence
    
    for cat in new_summary:
        count = new_summary[cat]["count"]
        new_summary[cat]["avg_confidence"] = new_summary[cat]["total_confidence"] / count if count > 0 else 0
        del new_summary[cat]["total_confidence"]
    
    print("="*60)
    print(f"Review complete. {reclassified_count} document(s) reclassified.")
    print("="*60)
    
    return {
        "classified_documents": updated_docs,
        "classification_summary": new_summary,
        "messages": [f"Human review complete: {reclassified_count} documents reclassified"]
    }
