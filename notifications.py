"""
Privacy-safe error notifications. No CSV data or PII is sent.
"""
import os
from typing import Optional

# Resend: https://resend.com — set RESEND_API_KEY and ALERT_EMAIL
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL")
RENDER_LOGS_BASE_URL = os.environ.get("RENDER_LOGS_BASE_URL", "")


def send_processing_error_alert(
    session_id: str,
    error_summary: str,
    timestamp: str,
) -> bool:
    """
    Send an email alert on processing failure. Returns True if sent, False if skipped (no key/email).
    error_summary must be sanitized (no PII, no raw CSV data).
    """
    if not RESEND_API_KEY or not ALERT_EMAIL:
        return False

    logs_link = ""
    if RENDER_LOGS_BASE_URL:
        logs_link = f"\n\nView logs: {RENDER_LOGS_BASE_URL.rstrip('/')}?t={timestamp}"

    body = (
        f"CSV processing failed.\n\n"
        f"Session ID: {session_id}\n"
        f"Error: {error_summary}\n"
        f"Time: {timestamp}"
        f"{logs_link}\n"
    )

    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send(
            {
                "from": os.environ.get("RESEND_FROM", "onboarding@resend.dev"),
                "to": [ALERT_EMAIL],
                "subject": f"[Merchant Auditor] Processing error — Session {session_id}",
                "text": body,
            }
        )
        return True
    except Exception:
        return False
