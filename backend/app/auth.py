"""
Demo-grade authentication. READ THIS BEFORE "PRODUCTION":

- Single hard-coded demo user (demo / demo1234). No registration, no
  password hashing, no rate limiting, no refresh tokens.
- JWT signed with a constant dev secret, 8-hour expiry.
- This exists ONLY so the portfolio demo has a login page like a real
  product. It is NOT production-grade auth. Do not put real user data
  behind it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# --- demo credentials (public demo, change nothing secret here) ---
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"
DEV_SECRET = "demo-only-not-a-secret-change-in-production"
ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 8

_bearer = HTTPBearer(auto_error=False)


def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
        "demo": True,
    }
    return jwt.encode(payload, DEV_SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, DEV_SECRET, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Log in again (demo/demo1234).",
        )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token>. Log in at /api/auth/login.",
        )
    return verify_token(creds.credentials)
