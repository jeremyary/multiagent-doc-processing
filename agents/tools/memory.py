# This project was developed with assistance from AI tools.
"""User memory tools - conversation recall and stored facts."""
import logging

from langchain_core.tools import tool

from config import config
from prompts import TOOL_GET_USER_FACTS, TOOL_RECALL_CONVERSATIONS

from . import ToolContext

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create user memory tools."""
    
    @tool(description=TOOL_RECALL_CONVERSATIONS)
    def recall_past_conversations(query: str) -> str:
        """Search past conversations with this user."""
        memory = context.get_conversation_memory()
        if memory is None:
            return "Conversation memory is not available."
        
        user_id = context.get_user_id()
        if not user_id:
            return "Unable to identify user for memory search."
        
        try:
            result = memory.search_formatted(
                user_id=user_id,
                query=query,
                k=config.MEMORY_RECALL_TOP_K,
                exclude_thread=context.get_thread_id()
            )
            return result
        except Exception as e:
            logger.warning(f"Conversation memory search failed: {e}")
            return "Failed to search conversation memory."
    
    @tool(description=TOOL_GET_USER_FACTS)
    def get_my_stored_facts() -> str:
        """Retrieve facts stored about the current user."""
        user_id = context.get_user_id()
        if not user_id:
            return "Unable to identify user."
        
        facts_store = context.get_facts_store()
        if facts_store is None:
            return "User memory is not available."
        
        try:
            facts = facts_store.get_facts(user_id)
            if not facts:
                return "No facts stored about you yet. As we chat, I'll remember important details you share."
            
            lines = [f"Here's what I remember about you ({len(facts)} facts):"]
            for fact_type, details in facts.items():
                label = fact_type.replace("_", " ").title()
                lines.append(f"- {label}: {details['value']}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to retrieve user facts: {e}")
            return "Failed to retrieve stored facts."
    
    return [recall_past_conversations, get_my_stored_facts]
