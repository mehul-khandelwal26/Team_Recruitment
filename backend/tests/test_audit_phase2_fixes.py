"""Tests verifying Phase 2 fixes: provenance integrity, inactive config guards, duplicate mappings, and upload limits."""

from __future__ import annotations

import io
import json
import pytest
from fastapi.testclient import TestClient

from app.ingestion.parser import parse_csv, parse_json
from app.ingestion.store import default_dataset_store
from app.main import app
from app.rules.config_store import default_config_store
from app.scoring.config_store import default_scoring_config_store

client = TestClient(app)

SAMPLE_CSV = "team_id,team_name,member_id,name\nT1,Alpha,M1,Alice\n"


def test_scoring_missing_eligibility_run_returns_404():
    """Scoring evaluate with nonexistent eligibility_run_id returns HTTP 404."""
    resp = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": [{"team_id": "T1", "team_name": "Alpha", "members": [{"member_id": "M1", "name": "Alice"}]}],
            "config_id": "balanced",
            "eligibility_run_id": "nonexistent_elig_run_123",
        },
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_scoring_dataset_id_mismatch_returns_400():
    """Scoring evaluate with eligibility_run_id and mismatched dataset_id returns HTTP 400."""
    # 1. Upload dataset 1
    resp1 = client.post("/api/ingestion/upload", files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    ds1_id = resp1.json()["dataset_id"]

    # 2. Upload dataset 2
    resp2 = client.post("/api/ingestion/upload", files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    ds2_id = resp2.json()["dataset_id"]

    # 3. Evaluate eligibility on dataset 1
    elig_resp = client.post("/api/rules/evaluate", json={"dataset_id": ds1_id, "config_id": "basic"})
    elig_id = elig_resp.json()["run_id"]

    # 4. Attempt scoring evaluation referencing elig_id but passing ds2_id
    resp = client.post(
        "/api/scoring/evaluate",
        json={"dataset_id": ds2_id, "config_id": "balanced", "eligibility_run_id": elig_id},
    )
    assert resp.status_code == 400
    assert "dataset_id" in resp.json()["detail"].lower()


def test_ranking_dataset_id_mismatch_returns_400():
    """Ranking evaluate with scoring_run_id and mismatched dataset_id returns HTTP 400."""
    # Upload two datasets
    resp1 = client.post("/api/ingestion/upload", files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    ds1_id = resp1.json()["dataset_id"]

    resp2 = client.post("/api/ingestion/upload", files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    ds2_id = resp2.json()["dataset_id"]

    # Score dataset 1
    score_resp = client.post("/api/scoring/evaluate", json={"dataset_id": ds1_id, "config_id": "balanced"})
    score_id = score_resp.json()["run_id"]

    # Rank with mismatched dataset_id
    rank_resp = client.post("/api/ranking/evaluate", json={"top_x": 1, "scoring_run_id": score_id, "dataset_id": ds2_id})
    assert rank_resp.status_code == 400
    assert "dataset_id" in rank_resp.json()["detail"].lower()


def test_ranking_eligibility_run_dataset_id_mismatch_returns_400():
    """Ranking evaluate with eligibility_run_id and mismatched dataset_id returns HTTP 400."""
    resp1 = client.post("/api/ingestion/upload", files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    ds1_id = resp1.json()["dataset_id"]

    resp2 = client.post("/api/ingestion/upload", files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    ds2_id = resp2.json()["dataset_id"]

    elig_resp = client.post("/api/rules/evaluate", json={"dataset_id": ds1_id, "config_id": "basic"})
    elig_id = elig_resp.json()["run_id"]

    score_resp = client.post("/api/scoring/evaluate", json={"dataset_id": ds1_id, "config_id": "balanced", "eligibility_run_id": elig_id})
    score_id = score_resp.json()["run_id"]

    rank_resp = client.post(
        "/api/ranking/evaluate",
        json={"top_x": 1, "scoring_run_id": score_id, "eligibility_run_id": elig_id, "dataset_id": ds2_id},
    )
    assert rank_resp.status_code == 400
    assert "dataset_id" in rank_resp.json()["detail"].lower()


def test_ingestion_duplicate_dataset_id_returns_409():
    """Uploading a dataset with an already existing explicit dataset_id returns HTTP 409 Conflict."""
    target_id = "test_unique_dataset_id_409"
    resp1 = client.post(
        "/api/ingestion/upload",
        files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")},
        data={"dataset_id": target_id},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/api/ingestion/upload",
        files={"file": ("teams.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")},
        data={"dataset_id": target_id},
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


def test_ingestion_file_size_exceeds_10mb_returns_413():
    """Uploading a file exceeding 10MB returns HTTP 413 Payload Too Large."""
    oversized = b"a" * (10 * 1024 * 1024 + 1024)
    resp = client.post(
        "/api/ingestion/upload",
        files={"file": ("huge.csv", io.BytesIO(oversized), "text/csv")},
    )
    assert resp.status_code == 413
    assert "exceeds maximum size limit" in resp.json()["detail"].lower()


def test_parser_duplicate_non_structural_column_mapping_rejected():
    """Mapping two CSV columns to the same non-structural target field is rejected."""
    csv_data = "Col1,Col2,ID,Name\nhttps://github.com/a,https://github.com/b,M1,Alice\n"
    mapping = {
        "Col1": "github_url",
        "Col2": "github_url",
        "ID": "member_id",
        "Name": "name",
    }
    result = parse_csv(csv_data.encode("utf-8"), mapping=mapping)
    assert result.success is False
    assert any("multiple columns mapped to field 'github_url'" in e.message.lower() for e in result.errors)


def test_parser_json_duplicate_mapping_rejected():
    """Mapping two JSON keys to the same target field is rejected."""
    json_data = json.dumps([
        {"team_name": "Alpha", "members": [{"name": "Alice", "cpi": 8.5, "cgpa_alt": 8.5}]}
    ]).encode("utf-8")
    mapping = {
        "cpi": "cgpa",
        "cgpa_alt": "cgpa",
    }
    result = parse_json(json_data, mapping=mapping)
    assert result.success is False
    assert any("multiple fields mapped to field 'cgpa'" in e.message.lower() for e in result.errors)


def test_rules_inactive_configuration_rejected_400():
    """Evaluating eligibility against an inactive configuration returns HTTP 400."""
    cfg = default_config_store.get("basic")
    assert cfg is not None
    # Temporarily deactivate
    cfg_copy = cfg.model_copy(deep=True)
    cfg_copy.config_id = "test_inactive_rules_cfg"
    cfg_copy.is_active = False
    default_config_store.save(cfg_copy)

    resp = client.post(
        "/api/rules/evaluate",
        json={
            "teams": [{"team_id": "T1", "team_name": "Alpha", "members": [{"member_id": "M1", "name": "Alice"}]}],
            "config_id": "test_inactive_rules_cfg",
        },
    )
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()


def test_scoring_inactive_configuration_rejected_400():
    """Evaluating scoring against an inactive configuration returns HTTP 400."""
    cfg = default_scoring_config_store.get("balanced")
    assert cfg is not None
    cfg_copy = cfg.model_copy(deep=True)
    cfg_copy.config_id = "test_inactive_scoring_cfg"
    cfg_copy.is_active = False
    default_scoring_config_store.save(cfg_copy)

    resp = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": [{"team_id": "T1", "team_name": "Alpha", "members": [{"member_id": "M1", "name": "Alice"}]}],
            "config_id": "test_inactive_scoring_cfg",
        },
    )
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()


def test_ranking_inactive_scoring_configuration_rejected_400():
    """Evaluating ranking on the fly with an inactive scoring configuration returns HTTP 400."""
    cfg = default_scoring_config_store.get("balanced")
    assert cfg is not None
    cfg_copy = cfg.model_copy(deep=True)
    cfg_copy.config_id = "test_inactive_ranking_cfg"
    cfg_copy.is_active = False
    default_scoring_config_store.save(cfg_copy)

    resp = client.post(
        "/api/ranking/evaluate",
        json={
            "top_x": 1,
            "teams": [{"team_id": "T1", "team_name": "Alpha", "members": [{"member_id": "M1", "name": "Alice"}]}],
            "scoring_config_id": "test_inactive_ranking_cfg",
        },
    )
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()


def test_delete_scoring_configuration_success_and_soft_delete():
    """DELETE /api/scoring/configs/{config_id} marks config as inactive."""
    cfg = default_scoring_config_store.get("balanced")
    assert cfg is not None
    cfg_copy = cfg.model_copy(deep=True)
    cfg_copy.config_id = "to_delete_scoring_cfg"
    cfg_copy.is_active = True
    default_scoring_config_store.save(cfg_copy)

    resp = client.delete("/api/scoring/configs/to_delete_scoring_cfg")
    assert resp.status_code == 200
    assert "inactive" in resp.json()["message"].lower()

    latest_ids = [c.config_id for c in default_scoring_config_store.list_latest()]
    assert "to_delete_scoring_cfg" not in latest_ids

    deleted_cfg = default_scoring_config_store.get("to_delete_scoring_cfg")
    assert deleted_cfg is not None
    assert deleted_cfg.is_active is False

    resp_404 = client.delete("/api/scoring/configs/nonexistent_cfg_xyz")
    assert resp_404.status_code == 404


def test_delete_rule_configuration_success_and_soft_delete():
    """DELETE /api/rules/configs/{config_id} marks rule config as inactive."""
    cfg = default_config_store.get("basic")
    assert cfg is not None
    cfg_copy = cfg.model_copy(deep=True)
    cfg_copy.config_id = "to_delete_rule_cfg"
    cfg_copy.is_active = True
    default_config_store.save(cfg_copy)

    resp = client.delete("/api/rules/configs/to_delete_rule_cfg")
    assert resp.status_code == 200
    assert "inactive" in resp.json()["message"].lower()

    latest_ids = [c.config_id for c in default_config_store.list_latest()]
    assert "to_delete_rule_cfg" not in latest_ids

    deleted_cfg = default_config_store.get("to_delete_rule_cfg")
    assert deleted_cfg is not None
    assert deleted_cfg.is_active is False

    resp_404 = client.delete("/api/rules/configs/nonexistent_rule_xyz")
    assert resp_404.status_code == 404
