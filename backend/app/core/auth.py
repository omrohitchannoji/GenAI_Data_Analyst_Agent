import os
import time
import json
import hmac
import jwt
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from jwt import ExpiredSignatureError, InvalidSignatureError, InvalidTokenError

# ============================================================
# AUTHENTICATION CONFIGURATION & FAIL-CLOSED ENFORCEMENT
# ============================================================
DEFAULT_TOKEN_EXPIRY_SECONDS = 86400  # 24 hours

def get_configured_users() -> Dict[str, Dict[str, str]]:
    raw = os.environ.get("AUTH_USERS_JSON")
    if not raw or not raw.strip():
        raise HTTPException(status_code=503, detail="Authentication users are not configured on this server.")
    try:
        users = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AUTH_USERS_JSON must contain a valid JSON user map.")
    if not isinstance(users, dict):
        raise HTTPException(status_code=500, detail="AUTH_USERS_JSON must contain a JSON object.")
    for username, user in users.items():
        if not isinstance(username, str) or not username.strip() or not isinstance(user, dict):
            raise HTTPException(status_code=500, detail="AUTH_USERS_JSON contains an invalid user entry.")
        if not isinstance(user.get("password"), str) or not user["password"]:
            raise HTTPException(status_code=500, detail="Each configured user must have a password.")
        if user.get("role") not in {"admin", "analyst"}:
            raise HTTPException(status_code=500, detail="Each configured user must have an allowed role.")
    return users

def get_auth_secret_key() -> str:
    """
    Retrieves the cryptographic signing secret from the environment.
    Strictly FAILS CLOSED if AUTH_SECRET_KEY is absent.
    Prevents hardcoded fallback secrets from being used in production.
    """
    secret = os.environ.get("AUTH_SECRET_KEY")
    if not secret or not secret.strip():
        raise HTTPException(
            status_code=500,
            detail="Server security misconfiguration: AUTH_SECRET_KEY environment variable is required and cannot be empty."
        )
    return secret.strip()

def authenticate_credentials(username: str, password: str) -> Dict[str, str]:
    """
    Authenticates user credentials against the server-side directory.
    Derives principal_id and role strictly on the server; callers cannot mint arbitrary identities.
    """
    users = get_configured_users()
    user_info = users.get(username.strip())
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    expected_password = user_info.get("password", "")
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_password.encode("utf-8"), password.strip().encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    return {
        "principal_id": username.strip(),
        "role": user_info.get("role", "analyst")
    }

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
    secret = secret_key or get_auth_secret_key()
    now = int(time.time())
    payload = {
        "sub": principal_id,
        "role": role,
        "iat": now,
        "exp": now + expires_in_seconds
    }

    return jwt.encode(payload, secret, algorithm="HS256")

def verify_access_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies the cryptographic signature and expiration of an access token.
    Returns decoded claims dictionary.
    Raises HTTPException(401) on invalid signature, malformed structure, or expiration.
    """
    secret = secret_key or get_auth_secret_key()
    try:
        claims = jwt.decode(
            token.strip(),
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "role", "iat", "exp"]},
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired.")
    except InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Invalid token signature. Authentication failed.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    return claims

def get_current_principal(request: Optional[Request]) -> str:
    """
    FastAPI identity boundary: derives principal_id strictly from cryptographically
    verified token claims.
    
    Security Guarantees:
    - NEVER trusts unverified client headers like 'x-principal-id'.
    - If an Authorization Bearer token is provided, validates signature & returns claims['sub'].
    - If token is invalid or tampered, raises HTTP 401 Unauthorized.
    - If no Authorization header is provided and ALLOW_DEMO_ANONYMOUS=true, falls back to 'demo_user'
      which is explicitly documented and bounded as a shared, unisolated demo session.
    - If ALLOW_DEMO_ANONYMOUS=false, raises HTTP 401 Unauthorized.
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

    # Explicit shared public demo mode fallback
    allow_demo = os.environ.get("ALLOW_DEMO_ANONYMOUS", "true").lower() == "true"
    if allow_demo:
        return "demo_user"

    raise HTTPException(status_code=401, detail="Authentication required. Provide a valid Bearer token.")
