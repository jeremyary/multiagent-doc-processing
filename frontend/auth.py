# This project was developed with assistance from AI tools.
"""
Authentication utilities for the Streamlit application.

Provides role-based access control with two personas:
- borrower: Can chat, upload documents, view own reports
- admin: Full access including document reviews
"""
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import yaml
import streamlit as st
import streamlit_authenticator as stauth


class Role(str, Enum):
    """User roles with their permissions."""
    ADMIN = "admin"
    BORROWER = "borrower"


@dataclass
class User:
    """Authenticated user information."""
    username: str
    name: str
    role: Role
    email: str = ""
    
    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN
    
    @property
    def is_borrower(self) -> bool:
        return self.role == Role.BORROWER
    
    def can_review_documents(self) -> bool:
        """Check if user can perform document reviews."""
        return self.is_admin
    
    def can_view_all_reports(self) -> bool:
        """Check if user can view all reports (not just their own)."""
        return self.is_admin
    
    def can_view_knowledge_stats(self) -> bool:
        """Check if user can view knowledge base statistics."""
        return self.is_admin


def load_auth_config() -> dict:
    """Load authentication configuration from YAML file."""
    config_path = Path(__file__).parent.parent / "config" / "users.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Authentication config not found: {config_path}\n"
            "Create config/users.yaml with user credentials."
        )
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_authenticator() -> stauth.Authenticate:
    """
    Get or create the authenticator instance.
    
    Returns:
        Configured Authenticate instance
    """
    if "authenticator" not in st.session_state:
        config = load_auth_config()
        st.session_state.authenticator = stauth.Authenticate(
            credentials=config["credentials"],
            cookie_name=config["cookie"]["name"],
            cookie_key=config["cookie"]["key"],
            cookie_expiry_days=config["cookie"]["expiry_days"],
            pre_authorized=config.get("pre_authorized", {}).get("emails", []),
        )
    return st.session_state.authenticator


def get_current_user() -> User | None:
    """
    Get the currently authenticated user.
    
    Returns:
        User object if authenticated, None otherwise
    """
    if not st.session_state.get("authentication_status"):
        return None
    
    username = st.session_state.get("username")
    name = st.session_state.get("name")
    
    if not username:
        return None
    
    # Get role from config
    config = load_auth_config()
    user_config = config["credentials"]["usernames"].get(username, {})
    role_str = user_config.get("role", "borrower")
    
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.BORROWER
    
    email = user_config.get("email", "")
    
    return User(username=username, name=name, role=role, email=email)


def require_auth(func):
    """
    Decorator to require authentication for a function.
    
    Usage:
        @require_auth
        def my_protected_function():
            ...
    """
    def wrapper(*args, **kwargs):
        if not st.session_state.get("authentication_status"):
            st.warning("Please log in to access this feature.")
            return None
        return func(*args, **kwargs)
    return wrapper


def require_role(required_role: Role):
    """
    Decorator to require a specific role.
    
    Usage:
        @require_role(Role.ADMIN)
        def admin_only_function():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                st.warning("Please log in to access this feature.")
                return None
            if user.role != required_role and user.role != Role.ADMIN:
                st.error("You don't have permission to access this feature.")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


def render_login() -> bool:
    """
    Render the login form.
    
    Returns:
        True if user is authenticated, False otherwise
    """
    authenticator = get_authenticator()
    
    # Render login widget
    authenticator.login(location="main")
    
    if st.session_state.get("authentication_status"):
        return True
    elif st.session_state.get("authentication_status") is False:
        st.error("Username or password is incorrect")
    
    return False


def render_logout():
    """Render logout button in sidebar."""
    authenticator = get_authenticator()
    authenticator.logout(location="sidebar")


def render_user_info():
    """Render current user info in sidebar."""
    user = get_current_user()
    if user:
        role_display = "Administrator" if user.is_admin else "Borrower"
        st.sidebar.markdown(f"**{user.name}** ({role_display})")


def get_user_thread_prefix() -> str:
    """
    Get the thread ID prefix for the current user.
    
    Returns:
        Prefix string like 'admin-' or 'borrower-'
    """
    user = get_current_user()
    if user:
        return f"{user.username}-"
    return ""


def get_user_upload_dir() -> str:
    """
    Get the upload directory prefix for the current user.
    
    Returns:
        Directory prefix like 'admin/' or 'borrower/'
    """
    user = get_current_user()
    if user:
        return user.username
    return "anonymous"
