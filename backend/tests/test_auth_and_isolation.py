import os
import sys
import pytest
import sqlite3
import tempfile

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.core.auth import (
    create_access_token,
    verify_access_token,
    get_current_principal
)
from app.core.dataset_registry import DatasetRegistry
from app.agent.state import TerminalStatus
from app.agent.nodes import validate_scope_node


@pytest.fixture
def client():
    return TestClient(app)


def test_token_creation_and_verification():
    """Verify standard HS256 JWT creation and claims decoding."""
    token = create_access_token(principal_id="user_alice", role="analyst", expires_in_seconds=3600)
    claims = verify_access_token(token)
    assert claims["sub"] == "user_alice"
    assert claims["role"] == "analyst"
    assert "exp" in claims
    assert "iat" in claims


def test_tampered_token_rejected():
    """Verify that any modification to payload or signature causes 401."""
    token = create_access_token(principal_id="user_alice", role="analyst")
    parts = token.split(".")
    # Tamper with the signature
    tampered_token = f"{parts[0]}.{parts[1]}.tampered_sig"
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(tampered_token)
    assert exc_info.value.status_code == 401
    assert "Invalid token signature" in exc_info.value.detail


def test_expired_token_rejected():
    """Verify that an expired token is rejected with 401."""
    # Create token expired 10 seconds ago
    token = create_access_token(principal_id="user_alice", role="analyst", expires_in_seconds=-10)
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_auth_token_endpoint(client):
    """Test POST /auth/token issues valid tokens."""
    resp = client.post("/auth/token", json={"principal_id": "test_engineer", "role": "admin"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["principal_id"] == "test_engineer"

    # Verify that the issued token is cryptographically valid
    claims = verify_access_token(data["access_token"])
    assert claims["sub"] == "test_engineer"
    assert claims["role"] == "admin"


def test_auth_token_endpoint_rejects_empty(client):
    """Test POST /auth/token rejects empty principal_id."""
    resp = client.post("/auth/token", json={"principal_id": "   "})
    assert resp.status_code == 400


def test_raw_header_spoofing_prevented(client):
    """
    Critical security test:
    Verify that an attacker providing a valid token for 'attacker_bob'
    CANNOT impersonate 'victim_alice' by passing 'x-principal-id: victim_alice'.
    The identity boundary must derive principal strictly from verified token claims.
    """
    token_bob = create_access_token(principal_id="attacker_bob")

    class MockRequest:
        headers = {
            "Authorization": f"Bearer {token_bob}",
            "x-principal-id": "victim_alice"  # Spoofed header
        }

    derived_principal = get_current_principal(MockRequest)
    assert derived_principal == "attacker_bob"
    assert derived_principal != "victim_alice"


def test_tampered_token_in_request_rejected(client):
    """Verify that an invalid Bearer token passed to API endpoints causes 401."""
    resp = client.post(
        "/query",
        json={"question": "What is the total revenue?", "dataset_id": "default"},
        headers={"Authorization": "Bearer invalid.jwt.token"}
    )
    assert resp.status_code == 401


def test_cross_tenant_dataset_isolation():
    """
    Verify cross-tenant dataset isolation:
    - User A registers dataset 'ds_secret_a'.
    - User B (with token for User B) attempts to access 'ds_secret_a'.
    - Access MUST be rejected at scope validation (REJECTED status).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_db = os.path.join(tmpdir, "test_registry.db")
        data_db = os.path.join(tmpdir, "test_data.db")

        # Create dummy database table for Alice
        conn = sqlite3.connect(data_db)
        conn.execute("CREATE TABLE data_ds_secret_a (id INT, salary INT)")
        conn.execute("INSERT INTO data_ds_secret_a VALUES (1, 100000)")
        conn.commit()
        conn.close()

        registry = DatasetRegistry(db_path=reg_db)
        registry.register_dataset(
            dataset_id="ds_secret_a",
            principal_id="alice",
            filename="salaries.csv",
            table_name="data_ds_secret_a",
            db_path=data_db,
            row_count=1,
            column_types={"numeric": ["id", "salary"]}
        )

        # 1. Alice queries her own dataset -> registry returns metadata
        alice_ds = registry.get_dataset("ds_secret_a", principal_id="alice")
        assert alice_ds is not None
        assert alice_ds["table_name"] == "data_ds_secret_a"

        # 2. Bob queries Alice's dataset -> registry returns None (isolated)
        bob_ds = registry.get_dataset("ds_secret_a", principal_id="bob")
        assert bob_ds is None

        # 3. Test through validate_scope_node with mocked registry
        import app.agent.nodes as nodes
        orig_registry = nodes.default_registry
        try:
            nodes.default_registry = registry

            # Bob attempts to run turn on Alice's dataset
            bob_state = {
                "dataset_id": "ds_secret_a",
                "principal_id": "bob",  # Derived from Bob's token
                "execution_events": []
            }
            res = validate_scope_node(bob_state)
            assert res["terminal_status"] == TerminalStatus.REJECTED.value
            assert "Unauthorized or nonexistent dataset" in res["error"]
        finally:
            nodes.default_registry = orig_registry
