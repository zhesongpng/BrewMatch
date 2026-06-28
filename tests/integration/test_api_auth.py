"""Auth-gate tests for the Brain API (Goal C — step 1).

Exercises the identity gate that protects per-user endpoints once Supabase auth
is configured:

  * anonymous "device-" ids stay open (no token needed),
  * real account ids require a valid, matching Supabase token,
  * a token for a different user, an expired token, or a garbage token is rejected.

Tokens are minted locally with the HS256 shared-secret scheme (the legacy
Supabase signing mode), signed with a test secret injected via monkeypatch so it
never leaks to the anonymous-mode suite in test_api_endpoints.py.
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone

import jwt
import pytest

# Force SQLite before importing the app (same guard as test_api_endpoints.py).
os.environ["DATABASE_URL"] = ""
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from fastapi.testclient import TestClient  # noqa: E402

import src.app.db as db  # noqa: E402
from api.main import app  # noqa: E402

_TEST_SECRET = "test-supabase-jwt-secret-at-least-32-bytes!"
_ACCOUNT = "11111111-2222-3333-4444-555555555555"  # a Supabase-style account id


def _make_token(sub: str, *, secret: str = _TEST_SECRET, exp_delta: int = 3600,
                aud: str = "authenticated") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "aud": aud,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_delta)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(scope="module")
def client():
    tmpdb = os.path.join(tempfile.mkdtemp(), "test_auth.db")
    db.get_db_path = lambda: tmpdb
    # Reset the process-global "schema created" flag so this module's DB gets
    # its tables even if another test module initialised first (see the same
    # note in test_api_endpoints.py).
    db._db_initialized = False
    assert db.active_backend() == "sqlite", "test must not hit production"
    with TestClient(app) as c:
        yield c


@pytest.fixture
def configured(monkeypatch):
    """Turn on per-account enforcement for one test, restored at teardown."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_SECRET)


def test_anonymous_device_id_served_without_token(client, configured):
    # Even with auth configured, a "device-" id needs no token (anonymous data).
    r = client.get("/stats/device-abc123")
    assert r.status_code == 200
    assert r.json()["total_brews"] == 0


def test_account_id_without_token_requires_signin(client, configured):
    r = client.get(f"/stats/{_ACCOUNT}")
    assert r.status_code == 401


def test_account_id_with_valid_token_served(client, configured):
    token = _make_token(_ACCOUNT)
    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_token_for_a_different_user_is_forbidden(client, configured):
    token = _make_token("99999999-0000-0000-0000-000000000000")
    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_expired_token_rejected(client, configured):
    token = _make_token(_ACCOUNT, exp_delta=-60)
    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_garbage_token_rejected(client, configured):
    r = client.get(
        f"/stats/{_ACCOUNT}", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert r.status_code == 401


def test_token_signed_with_wrong_secret_rejected(client, configured):
    token = _make_token(_ACCOUNT, secret="some-other-secret-not-the-real-one!!")
    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_malformed_authorization_header_rejected(client, configured):
    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": "Basic xyz"})
    assert r.status_code == 401


def test_write_path_also_gated(client, configured):
    """A write (create bag) to an account id must also require the token."""
    body = {
        "roaster": "Onyx", "name": "Guji", "bag_size_g": 250,
        "origin_country": "Ethiopia", "process": "washed", "roast_level": "light",
        "flavor_clusters": ["Floral"],
    }
    # No token → 401.
    assert client.post(f"/bags/{_ACCOUNT}", json=body).status_code == 401
    # Valid token → created.
    token = _make_token(_ACCOUNT)
    ok = client.post(
        f"/bags/{_ACCOUNT}", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert ok.status_code == 200


def _es256_token(private_key, sub: str = _ACCOUNT) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        private_key,
        algorithm="ES256",
    )


def test_asymmetric_jwks_path_verifies(client, monkeypatch):
    """The asymmetric (project signing-key) path verifies an ES256 token."""
    from cryptography.hazmat.primitives.asymmetric import ec

    import api.auth as auth_mod

    private_key = ec.generate_private_key(ec.SECP256R1())
    token = _es256_token(private_key)

    # JWKS mode: no shared secret, a project URL, and a stubbed key client that
    # returns the matching public key (stands in for the live JWKS fetch).
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")

    class _FakeKey:
        def __init__(self, key):
            self.key = key

    class _FakeClient:
        def get_signing_key_from_jwt(self, _token):
            return _FakeKey(private_key.public_key())

    monkeypatch.setattr(auth_mod, "_get_jwks_client", lambda url: _FakeClient())

    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_asymmetric_wrong_key_rejected(client, monkeypatch):
    """A token signed by a different key fails JWKS verification."""
    from cryptography.hazmat.primitives.asymmetric import ec

    import api.auth as auth_mod

    signing_key = ec.generate_private_key(ec.SECP256R1())
    other_key = ec.generate_private_key(ec.SECP256R1())
    token = _es256_token(signing_key)

    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")

    class _FakeKey:
        def __init__(self, key):
            self.key = key

    class _FakeClient:
        def get_signing_key_from_jwt(self, _token):
            return _FakeKey(other_key.public_key())  # wrong public key

    monkeypatch.setattr(auth_mod, "_get_jwks_client", lambda url: _FakeClient())

    r = client.get(f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_present_token_rejected_when_unconfigured(client):
    """A token presented while the brain is auth-unconfigured can't be trusted."""
    # No `configured` fixture here → SUPABASE_JWT_SECRET unset.
    token = _make_token(_ACCOUNT)
    r = client.get(
        f"/stats/{_ACCOUNT}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401
