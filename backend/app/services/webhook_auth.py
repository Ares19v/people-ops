"""Authentication for inbound Langfuse webhooks (prompt events, remote experiments, alerts).

Langfuse signs each delivery with

    x-langfuse-signature: t=<unix timestamp>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>

(https://langfuse.com/docs/prompt-management/features/webhooks-slack-integrations). Scripts and
tunnels that cannot sign can instead send the shared secret itself, or a plain HMAC of the body,
in `x-webhook-secret` / `Authorization`. Every credential header present is tried, so a valid
secret is never masked by an unrelated header that fails verification.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Iterable, Optional

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _parse_signature_header(header: str) -> Optional[tuple[str, list[str]]]:
    """Parse `t=<ts>,v1=<sig>[,v1=<sig>]` (also accepts `s=` as the signature key). None if not that format."""
    timestamp: Optional[str] = None
    signatures: list[str] = []
    for part in header.split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            return None
        if key == "t":
            timestamp = value
        elif key in ("v1", "s"):
            signatures.append(value)
    if timestamp is None or not signatures:
        return None
    return timestamp, signatures


def verify_langfuse_signature(
    raw_body: bytes,
    header: str,
    secret: str,
    tolerance_seconds: Optional[int] = None,
    now: Optional[float] = None,
) -> bool:
    """Verify a Langfuse `t=...,v1=...` signature, rejecting stale timestamps (replay protection)."""
    parsed = _parse_signature_header(header)
    if parsed is None or not secret:
        return False
    timestamp, signatures = parsed
    try:
        ts_value = float(timestamp)
    except ValueError:
        return False

    tolerance = settings.LANGFUSE_WEBHOOK_TOLERANCE_SECONDS if tolerance_seconds is None else tolerance_seconds
    if tolerance and abs((now if now is not None else time.time()) - ts_value) > tolerance:
        logger.warning("Rejected Langfuse webhook: timestamp outside the %ss tolerance", tolerance)
        return False

    expected = _hmac_hex(secret, f"{timestamp}.".encode("utf-8") + raw_body)
    return any(hmac.compare_digest(sig.lower(), expected) for sig in signatures)


def verify_shared_secret(raw_body: bytes, token: str, secret: str) -> bool:
    """Accept the shared secret itself, or a hex HMAC-SHA256 of the raw body (optionally `sha256=`/`Bearer ` prefixed)."""
    if not token or not secret:
        return False
    candidate = token.strip()
    for prefix in ("sha256=", "Bearer ", "bearer "):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    if hmac.compare_digest(candidate, secret):
        return True
    return hmac.compare_digest(candidate.lower(), _hmac_hex(secret, raw_body))


def verify_webhook_credentials(raw_body: bytes, credentials: Iterable[Optional[str]], secret: Optional[str] = None) -> bool:
    """True if ANY supplied credential verifies against the configured webhook secret."""
    secret = secret if secret is not None else settings.LANGFUSE_WEBHOOK_SECRET
    for credential in credentials:
        if not credential:
            continue
        if _parse_signature_header(credential) is not None:
            if verify_langfuse_signature(raw_body, credential, secret):
                return True
        elif verify_shared_secret(raw_body, credential, secret):
            return True
    return False


async def require_langfuse_webhook(request: Request) -> bytes:
    """FastAPI dependency: authenticate the request and return its raw body (cached by Starlette)."""
    raw_body = await request.body()
    headers = request.headers
    credentials = (
        headers.get("x-langfuse-signature"),
        headers.get("x-hub-signature-256"),
        headers.get("x-webhook-secret"),
        headers.get("authorization"),
    )
    if not verify_webhook_credentials(raw_body, credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid Langfuse webhook signature or secret.",
        )
    return raw_body
