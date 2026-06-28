"""Supabase login-token verification for the brain (Goal C — step 1).

The brain identifies a signed-in user from a Supabase-issued JWT in the
``Authorization: Bearer <token>`` header. Anonymous (on-device) users send no
token and keep using their ``device-<uuid>`` id directly — verification only
kicks in when a token is present, so this change is non-breaking for the
existing anonymous flow.

Two project signing schemes are supported, chosen by which env var is set:

* ``SUPABASE_JWT_SECRET`` — legacy HS256 shared secret (Settings → API → JWT).
* ``SUPABASE_URL`` (or ``SUPABASE_JWKS_URL``) — asymmetric RS256/ES256 keys
  verified against the project's published JWKS.

If neither is set the brain is "auth-unconfigured": it cannot verify a token
(a token presented in that state is rejected), and per-account enforcement is
off so the anonymous flow keeps working exactly as before.
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from jwt import PyJWKClient

# Supabase access tokens carry this audience claim.
_AUDIENCE = "authenticated"

# A few seconds of leeway absorbs minor clock skew between Supabase and the host.
_LEEWAY_SECONDS = 10


class AuthError(Exception):
    """Raised when a presented token cannot be verified (bad/expired/unconfigured)."""


def _jwks_url() -> str:
    """The project's JWKS URL from explicit override or derived from SUPABASE_URL."""
    explicit = os.environ.get("SUPABASE_JWKS_URL", "").strip()
    if explicit:
        return explicit
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    return f"{base}/auth/v1/.well-known/jwks.json" if base else ""


def auth_configured() -> bool:
    """True when the brain has the material to verify a token (so it can enforce)."""
    return bool(os.environ.get("SUPABASE_JWT_SECRET", "").strip() or _jwks_url())


# PyJWKClient fetches + caches the project's public keys; build it once per URL.
_jwks_client: Optional[PyJWKClient] = None
_jwks_client_url: str = ""


def _get_jwks_client(url: str) -> PyJWKClient:
    global _jwks_client, _jwks_client_url
    if _jwks_client is None or _jwks_client_url != url:
        _jwks_client = PyJWKClient(url)
        _jwks_client_url = url
    return _jwks_client


def verify_token(token: str) -> str:
    """Verify a Supabase JWT and return its subject (the user id), or raise.

    Prefers the HS256 shared secret when configured; otherwise verifies against
    the project's asymmetric JWKS. Raises :class:`AuthError` on any failure,
    including the brain being auth-unconfigured.
    """
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    try:
        if secret:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=_AUDIENCE,
                leeway=_LEEWAY_SECONDS,
            )
        else:
            url = _jwks_url()
            if not url:
                raise AuthError(
                    "auth not configured: set SUPABASE_JWT_SECRET or SUPABASE_URL"
                )
            signing_key = _get_jwks_client(url).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=_AUDIENCE,
                leeway=_LEEWAY_SECONDS,
            )
    except AuthError:
        raise
    except Exception as exc:  # jwt.InvalidTokenError and JWKS fetch/parse errors
        raise AuthError(f"invalid token: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise AuthError("token has no subject")
    return str(sub)
