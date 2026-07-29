"""Pure helpers for validating and building Supabase signup requests."""

from typing import Any, Dict, Optional


def normalize_email(email: str) -> str:
    """Return a consistently formatted email address."""
    return email.strip().lower()


def validate_signup(email: str, password: str, password_confirmation: str) -> Optional[str]:
    """Return a user-facing validation error, or None when signup data is valid."""
    normalized_email = normalize_email(email)
    if not normalized_email or "@" not in normalized_email:
        return "Enter a valid email address."
    if len(password) < 8:
        return "Use at least 8 characters for your password."
    if password != password_confirmation:
        return "Passwords do not match."
    return None


def build_signup_credentials(
    email: str,
    password: str,
    display_name: str = "",
    email_redirect_to: str = "",
) -> Dict[str, Any]:
    """Build credentials accepted by supabase-py's auth.sign_up method."""
    options: Dict[str, Any] = {}
    normalized_name = display_name.strip()
    if normalized_name:
        options["data"] = {"full_name": normalized_name}
    if email_redirect_to:
        options["email_redirect_to"] = email_redirect_to

    credentials: Dict[str, Any] = {
        "email": normalize_email(email),
        "password": password,
    }
    if options:
        credentials["options"] = options
    return credentials
