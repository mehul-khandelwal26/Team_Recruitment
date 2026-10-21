"""Tests verifying multi-tenant configuration isolation and preset immutability.

Verifies:
1. System presets ('basic', 'balanced', etc.) are read-only: cannot be PUT or DELETED (403 Forbidden).
2. Custom configs created by User A are strictly isolated: User B cannot GET, PUT, or DELETE them (404 Not Found).
3. Custom configs created by User A do not appear in User B's config listings.
"""

import pytest
from starlette.testclient import TestClient

from app.auth.jwt import create_access_token
from app.main import app
from app.schemas.auth import UserSchema
from app.storage import default_storage_factory, default_user_store


@pytest.fixture(autouse=True)
def enable_auth_for_tenant_tests(monkeypatch):
    """Enable authentication enforcement for this test module."""
    monkeypatch.setattr("app.auth.dependencies.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.rules.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.scoring.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.ranking.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.ingestion.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.signals.AUTH_ENABLED", True)
    monkeypatch.setattr("app.config.AUTH_ENABLED", True)
    default_storage_factory.configure(backend="memory")
    default_user_store.reset()
    yield
    default_user_store.reset()


@pytest.fixture
def alice_headers():
    alice = UserSchema(
        user_id="usr_alice_cfg_test",
        email="alice@test.org",
        name="Alice",
        is_active=True,
    )
    default_user_store.save(alice)
    token = create_access_token({"sub": "usr_alice_cfg_test", "email": "alice@test.org", "name": "Alice"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bob_headers():
    bob = UserSchema(
        user_id="usr_bob_cfg_test",
        email="bob@test.org",
        name="Bob",
        is_active=True,
    )
    default_user_store.save(bob)
    token = create_access_token({"sub": "usr_bob_cfg_test", "email": "bob@test.org", "name": "Bob"})
    return {"Authorization": f"Bearer {token}"}


def test_rule_config_system_preset_immutability(alice_headers):
    client = TestClient(app)

    # 1. System preset 'basic' is readable
    resp = client.get("/api/rules/configs/basic", headers=alice_headers)
    assert resp.status_code == 200

    # 2. System preset cannot be modified (403 Forbidden)
    resp_put = client.put(
        "/api/rules/configs/basic",
        json={"name": "Hacked Basic Preset"},
        headers=alice_headers,
    )
    assert resp_put.status_code == 403
    assert "System default" in resp_put.text

    # 3. System preset cannot be deleted (403 Forbidden)
    resp_del = client.delete("/api/rules/configs/basic", headers=alice_headers)
    assert resp_del.status_code == 403
    assert "System default" in resp_del.text


def test_rule_config_user_isolation(alice_headers, bob_headers):
    client = TestClient(app)

    # 1. Alice creates a custom rule configuration
    alice_cfg_payload = {
        "config_id": "cfg_alice_private_rules",
        "name": "Alice's Private Rules",
        "description": "Confidential rule set for Alice's workspace",
        "rules": [
            {
                "rule_id": "rule_team_size",
                "name": "Team Size Limits",
                "rule_type": "team_size_min",
                "scope": "team",
                "severity": "hard",
                "parameters": {"min_size": 2},
                "on_missing": "fail",
            }
        ],
    }
    create_resp = client.post("/api/rules/configs", json=alice_cfg_payload, headers=alice_headers)
    assert create_resp.status_code == 201

    # 2. Bob lists configurations — must NOT see Alice's private config
    bob_list = client.get("/api/rules/configs", headers=bob_headers).json()
    bob_config_ids = [c["config_id"] for c in bob_list]
    assert "cfg_alice_private_rules" not in bob_config_ids

    # 3. Bob attempts direct access to Alice's config — 404 Not Found
    get_resp = client.get("/api/rules/configs/cfg_alice_private_rules", headers=bob_headers)
    assert get_resp.status_code == 404

    # 4. Bob attempts to modify Alice's config — 404 Not Found
    put_resp = client.put(
        "/api/rules/configs/cfg_alice_private_rules",
        json={"name": "Bob's Malicious Overwrite"},
        headers=bob_headers,
    )
    assert put_resp.status_code == 404

    # 5. Bob attempts to delete Alice's config — 404 Not Found
    del_resp = client.delete("/api/rules/configs/cfg_alice_private_rules", headers=bob_headers)
    assert del_resp.status_code == 404

    # 6. Alice can successfully view and update her own config
    alice_get = client.get("/api/rules/configs/cfg_alice_private_rules", headers=alice_headers)
    assert alice_get.status_code == 200

    alice_put = client.put(
        "/api/rules/configs/cfg_alice_private_rules",
        json={"name": "Alice's Updated Rules"},
        headers=alice_headers,
    )
    assert alice_put.status_code == 200
    assert alice_put.json()["version"] == 2
    assert alice_put.json()["name"] == "Alice's Updated Rules"


def test_scoring_config_system_preset_immutability(alice_headers):
    client = TestClient(app)

    # 1. System preset 'balanced' is readable
    resp = client.get("/api/scoring/configs/balanced", headers=alice_headers)
    assert resp.status_code == 200

    # 2. System preset cannot be modified (403 Forbidden)
    resp_put = client.put(
        "/api/scoring/configs/balanced",
        json={"name": "Hacked Balanced Preset"},
        headers=alice_headers,
    )
    assert resp_put.status_code == 403
    assert "System default" in resp_put.text

    # 3. System preset cannot be deleted (403 Forbidden)
    resp_del = client.delete("/api/scoring/configs/balanced", headers=alice_headers)
    assert resp_del.status_code == 403
    assert "System default" in resp_del.text


def test_scoring_config_user_isolation(alice_headers, bob_headers):
    client = TestClient(app)

    # 1. Alice creates a custom scoring configuration
    alice_scoring_payload = {
        "config_id": "cfg_alice_private_scoring",
        "name": "Alice's Private Rubric",
        "description": "Confidential scoring rubric for Alice",
        "scale_max": 100.0,
        "criteria": [
            {
                "criterion_id": "crit_cgpa",
                "name": "Academic CGPA",
                "target_signal_key": "academic_cgpa",
                "criterion_type": "numeric_range",
                "weight": 50.0,
                "scope": "member",
                "normalization": {
                    "linear_range": {"min_value": 0.0, "max_value": 10.0}
                },
                "aggregation": "mean",
            }
        ],
    }
    create_resp = client.post("/api/scoring/configs", json=alice_scoring_payload, headers=alice_headers)
    assert create_resp.status_code == 201

    # 2. Bob lists configurations — must NOT see Alice's private scoring config
    bob_list = client.get("/api/scoring/configs", headers=bob_headers).json()
    bob_config_ids = [c["config_id"] for c in bob_list]
    assert "cfg_alice_private_scoring" not in bob_config_ids

    # 3. Bob attempts direct access to Alice's config — 404 Not Found
    get_resp = client.get("/api/scoring/configs/cfg_alice_private_scoring", headers=bob_headers)
    assert get_resp.status_code == 404

    # 4. Bob attempts to modify Alice's config — 404 Not Found
    put_resp = client.put(
        "/api/scoring/configs/cfg_alice_private_scoring",
        json={"name": "Bob's Malicious Overwrite"},
        headers=bob_headers,
    )
    assert put_resp.status_code == 404

    # 5. Bob attempts to delete Alice's config — 404 Not Found
    del_resp = client.delete("/api/scoring/configs/cfg_alice_private_scoring", headers=bob_headers)
    assert del_resp.status_code == 404

    # 6. Alice can successfully view and update her own config
    alice_get = client.get("/api/scoring/configs/cfg_alice_private_scoring", headers=alice_headers)
    assert alice_get.status_code == 200

    alice_put = client.put(
        "/api/scoring/configs/cfg_alice_private_scoring",
        json={"name": "Alice's Updated Rubric"},
        headers=alice_headers,
    )
    assert alice_put.status_code == 200
    assert alice_put.json()["version"] == 2
    assert alice_put.json()["name"] == "Alice's Updated Rubric"


def test_evaluation_using_foreign_private_config_rejected(alice_headers, bob_headers):
    client = TestClient(app)

    # Alice creates custom rule & scoring configs
    client.post(
        "/api/rules/configs",
        json={
            "config_id": "cfg_alice_eval_rules",
            "name": "Alice's Rules",
            "rules": [
                {
                    "rule_id": "rule_team_size",
                    "name": "Team Size Limits",
                    "rule_type": "team_size_min",
                    "scope": "team",
                    "severity": "hard",
                    "parameters": {"min_size": 2},
                    "on_missing": "fail",
                }
            ],
        },
        headers=alice_headers,
    )

    client.post(
        "/api/scoring/configs",
        json={
            "config_id": "cfg_alice_eval_scoring",
            "name": "Alice's Rubric",
            "scale_max": 100.0,
            "criteria": [
                {
                    "criterion_id": "crit_cgpa",
                    "name": "Academic CGPA",
                    "target_signal_key": "academic_cgpa",
                    "criterion_type": "numeric_range",
                    "weight": 50.0,
                    "scope": "member",
                    "normalization": {
                        "linear_range": {"min_value": 0.0, "max_value": 10.0}
                    },
                    "aggregation": "mean",
                }
            ],
        },
        headers=alice_headers,
    )

    # Bob attempts to evaluate eligibility using Alice's private rule config -> 404
    bob_eval_rules = client.post(
        "/api/rules/evaluate",
        json={
            "config_id": "cfg_alice_eval_rules",
            "teams": [{"team_id": "team_1", "team_name": "Team One", "members": []}],
        },
        headers=bob_headers,
    )
    assert bob_eval_rules.status_code == 404
    assert "not found" in bob_eval_rules.text.lower()

    # Bob attempts to evaluate scoring using Alice's private scoring config -> 404
    bob_eval_scoring = client.post(
        "/api/scoring/evaluate",
        json={
            "config_id": "cfg_alice_eval_scoring",
            "teams": [{"team_id": "team_1", "team_name": "Team One", "members": []}],
        },
        headers=bob_headers,
    )
    assert bob_eval_scoring.status_code == 404
    assert "not found" in bob_eval_scoring.text.lower()

