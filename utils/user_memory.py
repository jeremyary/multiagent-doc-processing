# This project was developed with assistance from AI tools.
"""
User memory system for persistent context across chat sessions.

Two memory types:
1. UserFactsStore: Structured facts about the user (stored in shared SQLite DB)
2. ConversationMemory: Vector-based storage for semantic search (stored in ChromaDB)
"""
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from config import config

logger = logging.getLogger(__name__)


# =============================================================================
# USER FACTS STORE (SQLite - shared database)
# =============================================================================

class UserFactsStore:
    """
    SQLite-backed storage for structured user facts.
    
    Facts are key-value pairs that persist across sessions and provide
    personalized context to the chat agent. Uses the shared app database.
    """
    
    def __init__(self, db_path: str | None = None):
        """
        Initialize the facts store.
        
        Args:
            db_path: Path to SQLite database. Defaults to shared app database.
        """
        self.db_path = db_path or config.APP_DATA_DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source_thread_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, fact_type)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_facts_user_id 
                ON user_facts(user_id)
            """)
            conn.commit()
        finally:
            conn.close()
    
    def set_fact(
        self,
        user_id: str,
        fact_type: str,
        fact_value: str,
        confidence: float = 1.0,
        source_thread_id: str | None = None
    ):
        """Store or update a fact for a user."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO user_facts (user_id, fact_type, fact_value, confidence, 
                                        source_thread_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, fact_type) DO UPDATE SET
                    fact_value = excluded.fact_value,
                    confidence = excluded.confidence,
                    source_thread_id = excluded.source_thread_id,
                    updated_at = excluded.updated_at
            """, (user_id, fact_type, fact_value, confidence, source_thread_id, now, now))
            conn.commit()
            logger.debug(f"Stored fact for {user_id}: {fact_type}={fact_value}")
        finally:
            conn.close()
    
    def get_facts(self, user_id: str) -> dict[str, Any]:
        """Get all facts for a user."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT fact_type, fact_value, confidence, updated_at
                FROM user_facts
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
            
            facts = {}
            for row in cursor.fetchall():
                facts[row[0]] = {
                    "value": row[1],
                    "confidence": row[2],
                    "updated_at": row[3]
                }
            return facts
        finally:
            conn.close()
    
    def get_facts_summary(self, user_id: str) -> str:
        """Get a formatted summary of user facts for inclusion in prompts."""
        facts = self.get_facts(user_id)
        if not facts:
            return ""
        
        lines = ["Known information about this user:"]
        for fact_type, details in facts.items():
            label = fact_type.replace("_", " ").title()
            lines.append(f"- {label}: {details['value']}")
        
        return "\n".join(lines)
    
    def delete_fact(self, user_id: str, fact_type: str):
        """Delete a specific fact for a user."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM user_facts WHERE user_id = ? AND fact_type = ?",
                (user_id, fact_type)
            )
            conn.commit()
        finally:
            conn.close()
    
    def clear_user(self, user_id: str) -> int:
        """Clear all facts for a user."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM user_facts WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    
    def clear_all(self) -> int:
        """Clear all facts for all users."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM user_facts")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    
    def get_stats(self) -> dict:
        """Get statistics about stored facts."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_facts")
            user_count = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM user_facts")
            fact_count = cursor.fetchone()[0]
            return {"users": user_count, "facts": fact_count}
        finally:
            conn.close()


# =============================================================================
# CONVERSATION MEMORY (ChromaDB - vector store)
# =============================================================================

class ConversationMemory:
    """
    Vector-based storage for past conversation turns.
    
    Enables semantic search over past conversations to recall
    specific discussions when relevant. Uses ChromaDB.
    """
    
    COLLECTION_NAME = "conversation_memory"
    
    def __init__(self, persist_directory: str | None = None):
        """Initialize conversation memory."""
        self.persist_directory = persist_directory or config.CHROMA_DB_PATH
        self._collection = None
        self._embeddings = None
    
    @property
    def embeddings(self):
        """Lazy initialization of embeddings model."""
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name=config.RAG_EMBEDDING_MODEL,
                model_kwargs={'device': 'cpu'},
            )
        return self._embeddings
    
    @property
    def collection(self):
        """Lazy initialization of ChromaDB collection."""
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            self._collection = client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "Chat conversation memory for semantic recall"}
            )
        return self._collection
    
    def store_exchange(
        self,
        user_id: str,
        thread_id: str,
        user_message: str,
        assistant_response: str,
        timestamp: str | None = None
    ):
        """Store a conversation exchange for later retrieval."""
        timestamp = timestamp or datetime.now().isoformat()
        
        combined_text = f"User: {user_message}\nAssistant: {assistant_response}"
        embedding = self.embeddings.embed_query(combined_text)
        doc_id = f"{user_id}_{thread_id}_{timestamp}"
        
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[combined_text],
            metadatas=[{
                "user_id": user_id,
                "thread_id": thread_id,
                "user_message": user_message[:500],
                "timestamp": timestamp,
            }]
        )
        logger.debug(f"Stored conversation exchange for {user_id} in thread {thread_id}")
    
    def search(
        self,
        user_id: str,
        query: str,
        k: int = 5,
        include_current_thread: str | None = None
    ) -> list[dict]:
        """Search for relevant past conversations."""
        if self.collection.count() == 0:
            return []
        
        query_embedding = self.embeddings.embed_query(query)
        where_filter = {"user_id": user_id}
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k * 2,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        exchanges = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            
            if include_current_thread and metadata["thread_id"] == include_current_thread:
                continue
            
            exchanges.append({
                "content": doc,
                "thread_id": metadata["thread_id"],
                "timestamp": metadata["timestamp"],
                "relevance_score": 1 - distance,
            })
            
            if len(exchanges) >= k:
                break
        
        return exchanges
    
    def search_formatted(
        self,
        user_id: str,
        query: str,
        k: int = 3,
        exclude_thread: str | None = None
    ) -> str:
        """Search and return formatted results for inclusion in prompts."""
        exchanges = self.search(user_id, query, k, exclude_thread)
        
        if not exchanges:
            return "No relevant past conversations found."
        
        lines = [f"Found {len(exchanges)} relevant past conversation(s):"]
        for ex in exchanges:
            timestamp = ex["timestamp"][:10]
            lines.append(f"\n--- Past conversation ({timestamp}) ---")
            lines.append(ex["content"])
        
        return "\n".join(lines)
    
    def get_user_history_count(self, user_id: str) -> int:
        """Get the number of stored exchanges for a user."""
        try:
            results = self.collection.get(
                where={"user_id": user_id},
                include=[]
            )
            return len(results["ids"])
        except Exception:
            return 0
    
    def clear_user(self, user_id: str) -> int:
        """Clear all conversation memory for a user."""
        try:
            results = self.collection.get(
                where={"user_id": user_id},
                include=[]
            )
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                return len(results["ids"])
            return 0
        except Exception as e:
            logger.error(f"Error clearing user memory: {e}")
            return 0
    
    def clear_all(self) -> int:
        """Clear all conversation memory."""
        try:
            count = self.collection.count()
            if count > 0:
                results = self.collection.get(include=[])
                self.collection.delete(ids=results["ids"])
            return count
        except Exception as e:
            logger.error(f"Error clearing all memory: {e}")
            return 0


# =============================================================================
# FACT EXTRACTION
# =============================================================================

def extract_facts_from_exchange(
    llm,
    user_message: str,
    assistant_response: str,
    existing_facts: dict[str, Any]
) -> list[dict]:
    """
    Use LLM to extract facts from a conversation exchange.
    
    The LLM decides what facts are important to remember - no predefined
    categories. It creates appropriate fact_type labels dynamically.
    """
    from prompts import FACT_EXTRACTION_PROMPT
    
    existing_facts_str = "None yet."
    if existing_facts:
        lines = [f"- {ft}: {d['value']}" for ft, d in existing_facts.items()]
        existing_facts_str = "\n".join(lines)
    
    prompt = FACT_EXTRACTION_PROMPT.format(
        existing_facts=existing_facts_str,
        user_message=user_message,
        assistant_response=assistant_response
    )
    
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        facts = json.loads(content.strip())
        
        if isinstance(facts, list):
            return [
                f for f in facts
                if isinstance(f, dict) and "fact_type" in f and "fact_value" in f
            ]
        return []
        
    except Exception as e:
        logger.warning(f"Failed to extract facts: {e}")
        return []


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_facts_store: UserFactsStore | None = None
_conversation_memory: ConversationMemory | None = None


def get_facts_store() -> UserFactsStore:
    """Get or create the singleton facts store instance."""
    global _facts_store
    if _facts_store is None:
        _facts_store = UserFactsStore()
    return _facts_store


def get_conversation_memory() -> ConversationMemory:
    """Get or create the singleton conversation memory instance."""
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory
