# This project was developed with assistance from AI tools.
"""
RAG (Retrieval-Augmented Generation) utilities for the mortgage assistant.

Uses ChromaDB for vector storage and HuggingFace embeddings.
"""
import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import config

logger = logging.getLogger(__name__)


class RAGManager:
    """Manages the RAG knowledge base - ingestion and retrieval."""
    
    def __init__(
        self, 
        persist_directory: str | Path | None = None,
        embedding_model: str | None = None,
        collection_name: str = "mortgage_regulations"
    ):
        """
        Initialize the RAG manager.
        
        Args:
            persist_directory: Directory to persist ChromaDB data (default: from config)
            embedding_model: HuggingFace model for embeddings (default: from config)
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = Path(persist_directory or config.CHROMA_DB_PATH)
        self.embedding_model = embedding_model or config.RAG_EMBEDDING_MODEL
        self.collection_name = collection_name
        
        # Initialize embeddings
        logger.info(f"Loading embedding model: {self.embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model,
            model_kwargs={'device': 'cpu'},  # Use CPU for embeddings
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Text splitter for chunking documents (config-driven)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.RAG_CHUNK_SIZE,
            chunk_overlap=config.RAG_CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        self._vectorstore: Chroma | None = None
    
    @property
    def vectorstore(self) -> Chroma:
        """Lazy initialization of the vector store."""
        if self._vectorstore is None:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self._vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(self.persist_directory)
            )
        return self._vectorstore
    
    def ingest_pdf(self, pdf_path: str | Path) -> int:
        """
        Ingest a single PDF into the knowledge base.
        
        Uses shared PDF extraction utility with OCR fallback for image-based PDFs.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Number of chunks created
        """
        from utils.pdf import extract_text_from_pdf
        
        pdf_path = Path(pdf_path)
        print(f"  Processing: {pdf_path.name}")
        
        # Use shared PDF extraction utility
        extraction = extract_text_from_pdf(pdf_path)
        
        if extraction.ocr_used:
            confidence = extraction.ocr_confidence or 0
            print(f"    OCR used (confidence: {confidence:.0%})")
        
        if extraction.is_empty:
            print(f"    Warning: No text extracted from {pdf_path.name}")
            return 0
        
        # Split into chunks
        chunks = self.text_splitter.split_text(extraction.text)
        
        # Create documents with metadata
        documents = [
            Document(
                page_content=chunk,
                metadata={
                    "source": pdf_path.name,
                    "chunk_index": i,
                    "ocr_used": extraction.ocr_used,
                }
            )
            for i, chunk in enumerate(chunks)
        ]
        
        # Add to vector store
        self.vectorstore.add_documents(documents)
        
        ocr_tag = " (via OCR)" if extraction.ocr_used else ""
        print(f"    Created {len(documents)} chunks{ocr_tag}")
        return len(documents)
    
    def ingest_directory(self, directory: str | Path | None = None) -> dict:
        """
        Ingest all PDFs from a directory into the knowledge base.
        
        Args:
            directory: Path to directory containing PDFs (defaults to config.KNOWLEDGE_BASE_DIR)
            
        Returns:
            Summary dict with counts
        """
        directory = Path(directory or config.KNOWLEDGE_BASE_DIR)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        pdf_files = list(directory.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {directory}")
            return {"files": 0, "chunks": 0}
        
        print(f"Ingesting {len(pdf_files)} PDF files from {directory}")
        print("=" * 60)
        
        total_chunks = 0
        successful_files = 0
        
        for pdf_path in pdf_files:
            try:
                chunks = self.ingest_pdf(pdf_path)
                total_chunks += chunks
                successful_files += 1
            except Exception as e:
                print(f"    Error processing {pdf_path.name}: {e}")
        
        print("=" * 60)
        print(f"Ingestion complete: {successful_files} files, {total_chunks} chunks")
        
        return {
            "files": successful_files,
            "chunks": total_chunks,
            "failed": len(pdf_files) - successful_files
        }
    
    def retrieve(
        self, 
        query: str, 
        k: int | None = None,
        max_distance: float = 2.0
    ) -> list[Document]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: The search query
            k: Number of documents to retrieve (default: config.RAG_TOP_K)
            max_distance: Maximum distance score (lower is more similar, typically 0-2)
            
        Returns:
            List of relevant documents
        """
        k = k or config.RAG_TOP_K
        if not self.has_documents():
            return []
        
        # Use similarity search with scores
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        
        # Filter by distance threshold (lower distance = more relevant)
        filtered_docs = []
        for doc, distance in results:
            if distance <= max_distance:
                doc.metadata["distance_score"] = distance
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def retrieve_with_context(self, query: str, k: int | None = None) -> str:
        """
        Retrieve relevant documents and format as context string.
        
        Args:
            query: The search query
            k: Number of documents to retrieve (default: config.RAG_TOP_K)
            
        Returns:
            Formatted context string for LLM prompt
        """
        docs = self.retrieve(query, k=k or config.RAG_TOP_K)
        
        if not docs:
            return ""
        
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Unknown")
            distance = doc.metadata.get("distance_score", 0)
            # Convert distance to a relevance indicator (lower distance = higher relevance)
            relevance = max(0, 1 - distance/2)  # Normalize to 0-1 range
            context_parts.append(
                f"[Source {i}: {source} (relevance: {relevance:.0%})]\n{doc.page_content}"
            )
        
        return "\n\n---\n\n".join(context_parts)
    
    def has_documents(self) -> bool:
        """Check if the knowledge base has any documents."""
        try:
            count = self.vectorstore._collection.count()
            return count > 0
        except Exception as e:
            logger.debug(f"Error checking knowledge base: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        try:
            count = self.vectorstore._collection.count()
            return {
                "total_chunks": count,
                "persist_directory": str(self.persist_directory),
                "collection_name": self.collection_name,
                "embedding_model": self.embedding_model,
                "chunk_size": config.RAG_CHUNK_SIZE,
                "chunk_overlap": config.RAG_CHUNK_OVERLAP,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear(self) -> int:
        """
        Clear all documents from the knowledge base.
        
        Returns:
            Number of documents deleted
        """
        try:
            count = self.vectorstore._collection.count()
            # Delete collection and recreate
            self.vectorstore._client.delete_collection(self.collection_name)
            self._vectorstore = None  # Force re-initialization
            print(f"Cleared {count} chunks from knowledge base")
            return count
        except Exception as e:
            print(f"Error clearing knowledge base: {e}")
            return 0


# Singleton instance
_rag_manager: RAGManager | None = None


def get_rag_manager() -> RAGManager:
    """Get or create the singleton RAG manager."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager()
    return _rag_manager
