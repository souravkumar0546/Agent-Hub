"""SMTP — test-connection handler.

Opens a socket to the configured host:port, issues EHLO, optionally STARTTLS,
then AUTH LOGIN if credentials are set. Closes the connection without
actually sending mail. Any exception → disconnected with the error text.
"""

from __future__ import annotations

import smtplib
import socket
import ssl


_TIMEOUT = 8


def _as_bool(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def test_connection(config: dict, credentials: dict) -> tuple[bool, str | None]:
    host = (config.get("host") or "").strip()
    if not host:
        return False, "SMTP host is required"
    try:
        port = int(config.get("port") or 587)
    except (TypeError, ValueError):
        return False, "Port must be a number"

    use_tls = _as_bool(config.get("use_tls"), default=True)
    username = credentials.get("username") or ""
    password = credentials.get("password") or ""

    try:
        server = smtplib.SMTP(host, port, timeout=_TIMEOUT)
    except (OSError, socket.timeout, smtplib.SMTPException) as e:
        return False, f"Cannot connect to {host}:{port} — {e}"

    try:
        server.ehlo()
        if use_tls:
            try:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            except smtplib.SMTPException as e:
                return False, f"STARTTLS failed: {e}"
        if username or password:
            try:
                server.login(username, password)
            except smtplib.SMTPAuthenticationError as e:
                return False, f"Authentication failed: {e.smtp_code} {e.smtp_error.decode(errors='replace')[:200]}"
            except smtplib.SMTPException as e:
                return False, f"SMTP login error: {e}"
        return True, None
    finally:
        try:
            server.quit()
        except Exception:
            pass
