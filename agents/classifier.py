# This project was developed with assistance from AI tools.
"""
Document Classifier agent for mortgage document categorization.
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from .base import BaseAgent
from config import config as app_config
from models import (
    ClassificationResult,
    ClassifiedDocument,
    ExtractedDocument,
    WorkflowError,
    WorkflowState,
)
from prompts import CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_USER_PROMPT
from utils.document_cache import document_cache


class ClassifierAgent(BaseAgent):
    """Agent responsible for classifying documents into categories."""
    
    def __init__(self):
        super().__init__(name="Classifier")
        
        categories_list = "\n".join(f"- {cat}" for cat in app_config.DOCUMENT_CATEGORIES)
        system_prompt = CLASSIFICATION_SYSTEM_PROMPT.format(categories_list=categories_list)
        
        user_prompt = CLASSIFICATION_USER_PROMPT.format(
            sample_chars=app_config.CLASSIFICATION_SAMPLE_CHARS,
            summary="{summary}",
            entities="{entities}",
            sample_text="{sample_text}"
        )
        
        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt)
        ])
        self.classification_chain = self.classification_prompt | self.llm.with_structured_output(ClassificationResult)
    
    def classify_document(self, doc: ExtractedDocument, config: RunnableConfig) -> ClassifiedDocument:
        """Classify a single document."""
        entities_str = ", ".join(doc.key_entities) if doc.key_entities else "None identified"
        max_sample = app_config.CLASSIFICATION_SAMPLE_CHARS
        sample_text = doc.raw_text[:max_sample] if len(doc.raw_text) > max_sample else doc.raw_text
        
        result: ClassificationResult = self.classification_chain.invoke(
            {
                "summary": doc.summary or "No summary available",
                "entities": entities_str,
                "sample_text": sample_text
            },
            config=config
        )
        
        category = result.category
        if category not in app_config.DOCUMENT_CATEGORIES:
            category = "Unknown Relevance"
        
        return ClassifiedDocument(
            document=doc,
            category=category,
            confidence=result.confidence,
            sub_categories=result.sub_categories,
            reasoning=result.reasoning
        )
    
    def build_classification_summary(self, classified_docs: list[ClassifiedDocument]) -> dict:
        """Build a summary of classifications by category."""
        summary: dict = {}
        
        for doc in classified_docs:
            category = doc.category
            if category not in summary:
                summary[category] = {
                    "count": 0,
                    "documents": [],
                    "total_confidence": 0.0
                }
            
            summary[category]["count"] += 1
            summary[category]["documents"].append(doc.document.file_name)
            summary[category]["total_confidence"] += doc.confidence
        
        for category in summary:
            count = summary[category]["count"]
            summary[category]["avg_confidence"] = round(
                summary[category]["total_confidence"] / count, 2
            )
            del summary[category]["total_confidence"]
        
        return summary
    
    def run(self, state: WorkflowState, config: RunnableConfig) -> dict:
        """Classify all extracted documents."""
        print("\n" + "="*60)
        print("STEP 2: Document Classification")
        print("="*60)
        self.log("Starting document classification...")
        
        extracted_docs = state.get("extracted_documents", [])
        
        if not extracted_docs:
            self.log("No documents to classify")
            return {
                "classified_documents": [],
                "classification_summary": {},
                "messages": ["No documents available for classification"]
            }
        
        self.log(f"Classifying {len(extracted_docs)} documents")
        
        classified_docs: list[ClassifiedDocument] = []
        errors: list[WorkflowError] = []
        cache_hits = 0
        use_cache = state.get("use_cache", True)
        
        for doc in extracted_docs:
            self.log(f"Classifying: {doc.file_name}")
            
            try:
                content_hash = doc.metadata.get("content_hash")
                
                if content_hash and use_cache:
                    cached_classification = document_cache.get_classification(content_hash)
                    if cached_classification:
                        cached_classification.document = doc
                        classified_docs.append(cached_classification)
                        cache_hits += 1
                        self.log(f"  [CACHE HIT] {cached_classification.category} (confidence: {cached_classification.confidence:.2f})")
                        continue
                
                classified = self.classify_document(doc, config)
                classified_docs.append(classified)
                
                if content_hash and use_cache:
                    document_cache.store_classification(content_hash, classified)
                
                self.log(f"  Category: {classified.category} (confidence: {classified.confidence:.2f})")
                
            except Exception as e:
                errors.append(WorkflowError(
                    code="CLASSIFICATION_UNEXPECTED_ERROR",
                    message=str(e),
                    severity="error",
                    recoverable=False,
                    node="classifier",
                    document=doc.file_name,
                    details={"error_type": type(e).__name__},
                ))
                self.log(f"  [ERROR] {e}")
                classified_docs.append(ClassifiedDocument(
                    document=doc,
                    category="Unknown Relevance",
                    confidence=0.0,
                    sub_categories=[],
                    reasoning=f"Classification error: {str(e)}"
                ))
        
        classification_summary = self.build_classification_summary(classified_docs)
        
        self.log(f"Classification complete: {len(classified_docs)} classified, {cache_hits} from cache")
        self.log(f"Categories found: {list(classification_summary.keys())}")
        
        return {
            "classified_documents": classified_docs,
            "classification_summary": classification_summary,
            "workflow_errors": errors,
            "messages": [f"Classified {len(classified_docs)} documents into {len(classification_summary)} categories"]
        }
