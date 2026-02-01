# This project was developed with assistance from AI tools.
"""Knowledge base search tool."""
import logging

from langchain_core.tools import tool

from config import config
from prompts import TOOL_SEARCH_KNOWLEDGE_BASE

from . import ToolContext

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create knowledge base tools."""
    
    @tool(description=TOOL_SEARCH_KNOWLEDGE_BASE)
    def search_knowledge_base(query: str) -> str:
        """Search the mortgage regulations knowledge base."""
        rag = context.get_rag_manager()
        if rag is None:
            return "Knowledge base is not available. Answering from general knowledge."
        
        try:
            if not rag.has_documents():
                return "Knowledge base is empty. Answering from general knowledge."
            
            result = rag.retrieve_with_context(query, k=config.RAG_TOP_K)
            if not result:
                return "No relevant information found in the knowledge base."
            return result
        except Exception as e:
            logger.warning(f"Knowledge base search failed: {e}")
            return "Knowledge base search failed. Answering from general knowledge."
    
    return [search_knowledge_base]
