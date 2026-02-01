# This project was developed with assistance from AI tools.
"""
Email tools for the chat agent.

Provides a draft-and-confirm workflow:
1. Agent calls draft_email to prepare an email
2. User sees a preview and "Send" button in the UI
3. User confirms to actually send
"""
import logging

from langchain_core.tools import tool

from agents.tools import ToolContext
from config import config
from prompts import TOOL_DRAFT_EMAIL

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create email-related tools."""
    
    @tool(description=TOOL_DRAFT_EMAIL)
    def draft_email(subject: str, body: str) -> str:
        """Draft an email for user confirmation."""
        user_email = context.get_user_email()
        user_id = context.get_user_id()
        
        if not user_email:
            return "Unable to send email: No email address on file for your account."
        
        # Check rate limit
        email_count = context.get_email_count()
        if email_count >= config.EMAIL_MAX_PER_SESSION:
            return f"Email limit reached ({config.EMAIL_MAX_PER_SESSION} per session). Please try again in a new session."
        
        # Store pending email for user confirmation
        pending_email = {
            "to": user_email,
            "subject": subject,
            "body": body,
            "user_id": user_id,
        }
        context.set_pending_email(pending_email)
        
        # Return preview for the user
        preview = f"""I've drafted an email for you:

**To:** {user_email}
**Subject:** {subject}

---
{body}
---

Please click the **Send Email** button below to send this email, or continue chatting if you'd like changes."""
        
        return preview
    
    return [draft_email]
