import json
import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_custom_signal_mapping_and_pipeline_execution(client):
    """Test Phase 3:
    1. Upload CSV where 'candidate_skills' is mapped as 'custom:skills'.
    2. Extract signals including 'custom:skills'.
    3. Evaluate eligibility using signal_contains targeting 'custom:skills'.
    4. Evaluate scoring model targeting 'custom:skills' with categorical rubric.
    5. Evaluate Top-X ranking.
    """
    csv_content = (
        "team_name,name,email,candidate_skills\n"
        "Alpha Squad,Alice,alice@example.com,Python; FastAPI; PostgreSQL\n"
        "Alpha Squad,Bob,bob@example.com,React; TypeScript\n"
        "Beta Devs,Charlie,charlie@example.com,Java; Spring Boot\n"
        "Beta Devs,David,david@example.com,Python; Docker\n"
    )

    mapping = {
        "candidate_skills": "custom:skills",
        "team_name": "team_name",
        "name": "name",
        "email": "email",
    }

    files = {
        "file": ("test_custom.csv", csv_content.encode("utf-8"), "text/csv"),
    }
    data = {
        "mapping": json.dumps(mapping)
    }

    # 1. Ingest
    upload_resp = client.post("/api/ingestion/upload", files=files, data=data)
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    body = upload_resp.json()
    assert body["teams_count"] == 2
    assert body["members_count"] == 4
    dataset_id = body["dataset_id"]

    # 2. Extract signals
    extract_resp = client.post(
        "/api/signals/extract",
        json={
            "dataset_id": dataset_id,
            "signal_keys": ["custom:skills"],
        },
    )
    assert extract_resp.status_code == 200, f"Extraction failed: {extract_resp.text}"
    extract_body = extract_resp.json()
    extraction_run_id = extract_body["run_id"]

    # Verify custom signal was extracted
    member_signals = extract_body["teams"][0]["member_results"][0]["signals"]
    custom_sig = next((s for s in member_signals if s["signal_key"] == "custom:skills"), None)
    assert custom_sig is not None, "custom:skills was not found in extracted member signals"
    assert custom_sig["status"].lower() == "extracted"
    assert "Python" in custom_sig["value"]

    # 3. Create eligibility rule targeting custom:skills
    rule_config_payload = {
        "config_id": "custom_skills_rule_config",
        "name": "Custom Skills Eligibility",
        "description": "Requires at least one team member to possess Python in custom:skills.",
        "rules": [
            {
                "rule_id": "r_has_python",
                "name": "Has Python Skill",
                "rule_type": "signal_contains",
                "severity": "hard",
                "scope": "member",
                "on_missing": "fail",
                "member_selection": "any_member",
                "parameters": {
                    "signal_key": "custom:skills",
                    "expected_value": "Python",
                },
            }
        ],
    }
    create_rule_resp = client.post("/api/rules/configs", json=rule_config_payload)
    assert create_rule_resp.status_code in (200, 201), f"Failed to create rule config: {create_rule_resp.text}"

    # Evaluate eligibility
    elig_eval_resp = client.post(
        "/api/rules/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": extraction_run_id,
            "config_id": "custom_skills_rule_config",
            "version": 1,
        },
    )
    assert elig_eval_resp.status_code == 200, f"Eligibility evaluation failed: {elig_eval_resp.text}"
    elig_eval_body = elig_eval_resp.json()
    assert elig_eval_body["summary"]["eligible_count"] == 2  # Both teams have at least one Python member

    # 4. Create scoring model targeting custom:skills
    scoring_payload = {
        "config_id": "custom_skills_scoring_config",
        "name": "Custom Skills Scoring Rubric",
        "description": "Scores custom:skills based on tech stack relevance.",
        "scale_max": 100.0,
        "criteria": [
            {
                "criterion_id": "crit_custom_skills",
                "name": "Skills Evaluation",
                "description": "Scores candidate skills.",
                "target_signal_key": "custom:skills",
                "criterion_type": "categorical",
                "weight": 10.0,
                "is_enabled": True,
                "normalization": {
                    "categorical_mapping": {
                        "category_scores": {
                            "Python; FastAPI; PostgreSQL": 1.0,
                            "React; TypeScript": 0.8,
                            "Java; Spring Boot": 0.7,
                            "Python; Docker": 0.9,
                        },
                        "default_score": 0.5,
                        "case_sensitive": False,
                    }
                },
                "aggregation": "mean",
                "missing_data_policy": "exclude_and_renormalize",
            }
        ],
    }
    create_scoring_resp = client.post("/api/scoring/configs", json=scoring_payload)
    assert create_scoring_resp.status_code in (200, 201), f"Failed to create scoring config: {create_scoring_resp.text}"

    # Evaluate scoring
    scoring_eval_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": extraction_run_id,
            "eligibility_run_id": elig_eval_body["run_id"],
            "config_id": "custom_skills_scoring_config",
            "version": 1,
        },
    )
    assert scoring_eval_resp.status_code == 200, f"Scoring evaluation failed: {scoring_eval_resp.text}"
    scoring_eval_body = scoring_eval_resp.json()
    assert len(scoring_eval_body["teams"]) == 2
    assert scoring_eval_body["summary"]["calculated_teams"] == 2

    # 5. Top-X Ranking
    rank_resp = client.post(
        "/api/ranking/evaluate",
        json={
            "dataset_id": dataset_id,
            "eligibility_run_id": elig_eval_body["run_id"],
            "scoring_run_id": scoring_eval_body["run_id"],
            "top_x": 1,
            "include_needs_review": False,
        },
    )
    assert rank_resp.status_code == 200, f"Ranking failed: {rank_resp.text}"
    rank_body = rank_resp.json()
    assert len(rank_body["selected_teams"]) == 1
    assert rank_body["summary"]["total_teams_evaluated"] == 2
