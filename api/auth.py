"""
KAIROS Backend Authentication Middleware — Firebase JWT Token Verification.

Provides:
  - get_current_user dependency injection to secure API routes.
  - Graceful fallback to simulated users if Firebase is unconfigured or a mock token is passed.
"""

from __future__ import annotations

import os
import json
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth, credentials
from config import config

# ── Firebase Admin SDK Initialisation ─────────────────────────────────────────

firebase_enabled = False


def _build_credential():
    """Resolve a Firebase Admin credential from (in order):
      1. FIREBASE_SERVICE_ACCOUNT  — full service-account JSON (HF secret / env)
      2. GOOGLE_APPLICATION_CREDENTIALS or ./firebase-service-account.json file
      3. None → Application Default Credentials (local gcloud / GCP metadata)
    """
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_json:
        return credentials.Certificate(json.loads(sa_json))

    for path in (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        "firebase-service-account.json",
    ):
        if path and os.path.exists(path):
            return credentials.Certificate(path)

    return None  # falls through to ApplicationDefault()


try:
    # Check if Firebase app is already initialized
    if not firebase_admin._apps:
        cred = _build_credential()
        if cred is not None:
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
    firebase_enabled = True
    print("🔥 KAIROS Auth: Firebase Admin SDK initialised successfully.")
except Exception as e:
    is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING") == "true" or os.environ.get("TESTING") == "True"
    if not config.DEBUG and not is_testing:
        raise RuntimeError(f"Firebase Admin SDK failed to initialize in production mode: {e}")
    print(f"⚠️ KAIROS Auth Warning: Firebase Admin failed to initialise: {e}")
    print("⚠️ KAIROS Auth: Running backend in Simulation Fallback Mode.")

# ── Models ────────────────────────────────────────────────────────────────────

from pydantic import BaseModel

class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    is_anonymous: bool = False

# ── Token Verification Helper ──────────────────────────────────────────────────

def verify_token(token: str) -> UserProfile:
    """
    Verifies a Firebase ID token.
    Supports simulated fallback tokens for local demo mode.
    """
    # 1. Handle Simulated Fallback Tokens
    if token.startswith("simulated-") or token.startswith("sim-"):
        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING") == "true" or os.environ.get("TESTING") == "True"
        if not config.DEBUG and not is_testing:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Simulated fallback tokens are not allowed in production mode.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if "google" in token:
            google_id = token.split("sim-google-uid-")[-1] if "sim-google-uid-" in token else (token.split("-")[-1] if "-" in token else "8123")
            return UserProfile(
                uid=f"sim-google-uid-{google_id}",
                email="baljot@company.com",
                name="Baljot Chohan",
                is_anonymous=False
            )
        else:
            # Anonymous Guest
            guest_id = token.split("sim-guest-uid-")[-1] if "sim-guest-uid-" in token else (token.split("-")[-1] if "-" in token else "9999")
            return UserProfile(
                uid=f"sim-guest-uid-{guest_id}",
                email=None,
                name="Guest User",
                is_anonymous=True
            )

    # 2. Check if Firebase is configured
    if not firebase_enabled:
        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING") == "true" or os.environ.get("TESTING") == "True"
        if not config.DEBUG and not is_testing:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Firebase configuration is missing in production mode.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # If real client token is sent but Firebase backend is unconfigured,
        # fallback to a mock user to prevent blocking development.
        print(f"⚠️ KAIROS Auth: Unconfigured Firebase Admin. Creating mock user for token: {token[:10]}...")
        return UserProfile(
            uid=f"mock-fallback-uid-{token[:8]}",
            email="developer@company.com",
            name="Developer Fallback",
            is_anonymous=False
        )

    # 3. Real Firebase Verification
    try:
        decoded_token = auth.verify_id_token(token)
        
        # Determine if anonymous sign-in was used
        provider = decoded_token.get("firebase", {}).get("sign_in_provider")
        is_anonymous = (provider == "anonymous")
        
        return UserProfile(
            uid=decoded_token.get("uid"),
            email=decoded_token.get("email"),
            name=decoded_token.get("name"),
            is_anonymous=is_anonymous
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase Token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ── FastAPI Dependency Injection ──────────────────────────────────────────────

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserProfile:
    """FastAPI Dependency Injection to authenticate routes."""
    if not credentials:
        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("TESTING") == "true" or os.environ.get("TESTING") == "True"
        # In production or if Firebase is enabled, authentication credentials are required.
        if firebase_enabled or (not config.DEBUG and not is_testing):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            # simulation mode default - generate unique random ID per request
            import uuid
            rand_id = uuid.uuid4().hex[:8]
            return UserProfile(
                uid=f"sim-guest-uid-{rand_id}",
                email=None,
                name="Guest User",
                is_anonymous=True
            )
            
    token = credentials.credentials
    return verify_token(token)
