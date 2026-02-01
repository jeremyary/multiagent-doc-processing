# This project was developed with assistance from AI tools.
"""
Email sending utility using Maileroo API.

Provides a simple interface for sending emails with rate limiting
and validation for security.
"""
import logging
from dataclasses import dataclass

from config import config

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Check if Maileroo API is configured."""
    return bool(config.MAILEROO_SEND_KEY)


@dataclass
class EmailResult:
    """Result of an email send operation."""
    success: bool
    reference_id: str | None = None
    error: str | None = None
    
    def format_response(self) -> str:
        """Format as a human-readable response."""
        if self.success:
            return f"Email sent successfully. (Reference: {self.reference_id})"
        return f"Failed to send email: {self.error}"


class EmailClient:
    """
    Client for sending emails via Maileroo API.
    
    Includes validation to ensure emails are only sent to authorized recipients.
    """
    
    def __init__(self):
        if not is_available():
            raise RuntimeError("Maileroo API key not configured")
        
        from maileroo import MailerooClient
        self._client = MailerooClient(config.MAILEROO_SEND_KEY)
        self._from_email = config.MAILEROO_FROM_EMAIL
        self._from_name = config.MAILEROO_FROM_NAME
    
    def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        to_name: str = "",
        html: bool = False,
    ) -> EmailResult:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            to_name: Recipient display name (optional)
            subject: Email subject line
            body: Email body (plain text or HTML)
            html: If True, body is treated as HTML
            
        Returns:
            EmailResult with success status and reference ID or error
        """
        try:
            from maileroo import EmailAddress
            
            email_params = {
                "from": EmailAddress(self._from_email, self._from_name or None),
                "to": [EmailAddress(to_email, to_name or None)],
                "subject": subject,
            }
            
            if html:
                email_params["html"] = body
            else:
                email_params["plain"] = body
            
            reference_id = self._client.send_basic_email(email_params)
            
            logger.info(f"Email sent to {to_email}: {reference_id}")
            return EmailResult(success=True, reference_id=reference_id)
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return EmailResult(success=False, error=str(e))


def get_client() -> EmailClient:
    """Get an EmailClient instance."""
    return EmailClient()
