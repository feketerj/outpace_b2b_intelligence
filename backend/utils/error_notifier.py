"""
Error Notifier - Email alerts for production errors.

Zero dependencies beyond stdlib. No subscriptions. No Slack.
Just SMTP to whatever email you already check.

Env vars (all optional - silent if not set):
    ERROR_EMAIL_TO      - Where to send alerts (your email)
    ERROR_EMAIL_FROM    - Sender address
    SMTP_HOST           - SMTP server (e.g., smtp.gmail.com)
    SMTP_PORT           - SMTP port (default: 587)
    SMTP_USER           - SMTP username
    SMTP_PASS           - SMTP password (use app password for Gmail)
    ENVIRONMENT         - Included in subject line (e.g., "production")
"""

import smtplib
import ssl
import traceback
import os
import logging
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """Check if error notification is configured."""
    required = ["ERROR_EMAIL_TO", "ERROR_EMAIL_FROM", "SMTP_HOST", "SMTP_USER", "SMTP_PASS"]
    return all(os.getenv(var) for var in required)


def notify_error(
    exc: Exception,
    context: Optional[dict] = None,
    request_info: Optional[dict] = None
) -> bool:
    """
    Email yourself when shit breaks.

    Returns True if email sent, False if skipped (not configured or failed).
    Never raises - we don't want error notification to cause more errors.
    """
    if not is_configured():
        logger.debug("[error_notifier] Not configured, skipping notification")
        return False

    try:
        env = os.getenv("ENVIRONMENT", "unknown")
        exc_type = type(exc).__name__
        exc_msg = str(exc)[:100]  # Truncate for subject line

        # Build email
        msg = EmailMessage()
        msg["Subject"] = f"[{env.upper()}] {exc_type}: {exc_msg}"
        msg["From"] = os.getenv("ERROR_EMAIL_FROM")
        msg["To"] = os.getenv("ERROR_EMAIL_TO")

        # Build body
        body_parts = [
            f"PRODUCTION ERROR ALERT",
            f"=" * 50,
            f"",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Environment: {env}",
            f"",
            f"Exception Type: {exc_type}",
            f"Exception Message: {str(exc)}",
            f"",
        ]

        if request_info:
            body_parts.extend([
                f"Request Info:",
                f"  Method: {request_info.get('method', 'N/A')}",
                f"  Path: {request_info.get('path', 'N/A')}",
                f"  Trace ID: {request_info.get('trace_id', 'N/A')}",
                f"  User: {request_info.get('user', 'N/A')}",
                f"  Tenant: {request_info.get('tenant_id', 'N/A')}",
                f"",
            ])

        if context:
            body_parts.extend([
                f"Additional Context:",
                *[f"  {k}: {v}" for k, v in context.items()],
                f"",
            ])

        body_parts.extend([
            f"Traceback:",
            f"-" * 50,
            traceback.format_exc(),
        ])

        msg.set_content("\n".join(body_parts))

        # Send email
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")

        context_ssl = ssl.create_default_context()

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context_ssl)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"[error_notifier] Alert sent for {exc_type}")
        return True

    except Exception as notify_exc:
        # Log but don't raise - notification failure shouldn't break the app
        logger.error(f"[error_notifier] Failed to send alert: {notify_exc}")
        return False


def notify_critical(message: str, context: Optional[dict] = None) -> bool:
    """
    Send a critical alert that's not tied to an exception.

    Use for things like:
    - Tenant isolation violation detected
    - Rate limit exceeded by suspicious amount
    - Database corruption detected
    """
    if not is_configured():
        return False

    try:
        env = os.getenv("ENVIRONMENT", "unknown")

        msg = EmailMessage()
        msg["Subject"] = f"[{env.upper()}] CRITICAL: {message[:50]}"
        msg["From"] = os.getenv("ERROR_EMAIL_FROM")
        msg["To"] = os.getenv("ERROR_EMAIL_TO")

        body_parts = [
            f"CRITICAL ALERT",
            f"=" * 50,
            f"",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Environment: {env}",
            f"",
            f"Message: {message}",
            f"",
        ]

        if context:
            body_parts.extend([
                f"Context:",
                *[f"  {k}: {v}" for k, v in context.items()],
            ])

        msg.set_content("\n".join(body_parts))

        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")

        context_ssl = ssl.create_default_context()

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context_ssl)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"[error_notifier] Critical alert sent: {message[:50]}")
        return True

    except Exception as notify_exc:
        logger.error(f"[error_notifier] Failed to send critical alert: {notify_exc}")
        return False
