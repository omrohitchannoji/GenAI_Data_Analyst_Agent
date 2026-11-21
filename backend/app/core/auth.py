import os
import time
import json
import hmac
import base64
import hashlib
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException

# Secret key used for cryptographic token signing (configurable via environment)
AUTH_SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "agentic-analyst-signed-token-secret-key-2026")
DEFAULT_TOKEN_EXPIRY_SECONDS = 86400  # 24 hours

def _base64url_encode(data: bytes) -> str:
    """Encodes bytes into URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _base64url_decode(data: str) -> bytes:
    """Decodes URL-safe base64 string with appropriate padding."""
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def create_access_token(
    principal_id: str,
    role: str = "analyst",
    expires_in_seconds: int = DEFAULT_TOKEN_EXPIRY_SECONDS,
    secret_key: Optional[str] = None
) -> str:
    """
    Creates a signed HMAC-SHA256 bearer token encoding principal_id in 'sub'.
    Returns standard JWT format: base64url(header).base64url(payload).base64url(signature)
    """
    secret = (secret_key or AUTH_SECRET_KEY).encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": principal_id,
        "role": role,
        "iat": now,
        "exp": now + expires_in_seconds
    }

    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_access_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies the cryptographic signature and expiration of an access token.
    Returns decoded claims dictionary.
    Raises HTTPException(401) on invalid signature, malformed structure, or expiration.
    """
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Malformed authentication token.")

    header_b64, payload_b64, sig_b64 = parts
    secret = (secret_key or AUTH_SECRET_KEY).encode("utf-8")
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    try:
        provided_sig = _base64url_decode(sig_b64)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token encoding.")

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature. Authentication failed.")

    try:
        payload_bytes = _base64url_decode(payload_b64)
        claims = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token claims payload.")

    exp = claims.get("exp")
    if exp and time.time() > exp:
        raise HTTPException(status_code=401, detail="Authentication token has expired.")

    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Token missing subject principal ('sub').")

    return claims

def get_current_principal(request: Optional[Request]) -> str:
    """
    FastAPI identity boundary: derives principal_id strictly from cryptographically
    verified token claims.
    
    Security Guarantee:
    - NEVER trusts unverified client headers like 'x-principal-id'.
    - If an Authorization Bearer token is provided, validates signature & returns claims['sub'].
    - If token is invalid or tampered, raises HTTP 401 Unauthorized.
    - If no Authorization header is provided, falls back to 'demo_user' for local/public demo mode.
    """
    if request is None:
        return "demo_user"

    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")

    if auth_header:
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization header must use Bearer scheme.")
        token = auth_header[7:].strip()
        claims = verify_access_token(token)
        return str(claims["sub"])

    # Fallback to demo_user when no token is supplied (for public Streamlit demo)
    allow_demo = os.environ.get("ALLOW_DEMO_ANONYMOUS", "true").lower() == "true"
    if allow_demo:
        return "demo_user"

    raise HTTPException(status_code=401, detail="Authentication required. Provide a valid Bearer token.")
