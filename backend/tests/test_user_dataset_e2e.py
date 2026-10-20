import os
import json
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.ingestion.discovery import discover_fields_from_bytes

USER_CSV_PATH = r"C:\Users\Lenovo\.gemini\antigravity\brain\7a2a4f2e-6a90-4db1-a4ac-1f0acc7d266e\.user_uploaded\media_1792488737972_e8a3e937.csv"
USER_ZIP_PATH = r"C:\Users\Lenovo\.gemini\antigravity\brain\7a2a4f2e-6a90-4db1-a4ac-1f0acc7d266e\.user_uploaded\media_1792488737972_74132f5c.zip"


@pytest.fixture
def client():
    return TestClient(app)


def test_user_csv_discovery_and_conflict_resolution():
    """Verify that field discovery on user's CSV cleanly disambiguates github_url vs github_id."""
    assert os.path.exists(USER_CSV_PATH), f"CSV file missing at {USER_CSV_PATH}"

    with open(USER_CSV_PATH, "rb") as f:
        csv_bytes = f.read()

    res = discover_fields_from_bytes(csv_bytes, "candidates.csv")
    suggested = res.suggested_mappings

    # github_url must win canonical github_url (exact name, 1.0 confidence)
    assert suggested.get("github_url") == "github_url"

    # github_id must be demoted and not present in suggested_mappings (no duplicate collision)
    assert "github_id" not in suggested

    # Ensure no canonical field is mapped more than once in suggested_mappings
    mapped_targets = list(suggested.values())
    assert len(mapped_targets) == len(set(mapped_targets)), "Duplicate canonical target found in suggestions!"


def test_user_csv_ingestion_and_warning_filter(client):
    """Verify that ingesting user's CSV with mapping eliminates phantom portfolio_url warnings."""
    assert os.path.exists(USER_CSV_PATH)

    with open(USER_CSV_PATH, "rb") as f:
        csv_bytes = f.read()

    discovery_res = discover_fields_from_bytes(csv_bytes, "candidates.csv")
    mapping = discovery_res.suggested_mappings

    with open(USER_CSV_PATH, "rb") as f_csv, open(USER_ZIP_PATH, "rb") as f_zip:
        files = {
            "file": ("candidates.csv", f_csv, "text/csv"),
            "resumes_archive": ("resumes.zip", f_zip, "application/zip"),
        }
        data = {
            "mapping": json.dumps(mapping)
        }
        resp = client.post("/api/ingestion/upload", files=files, data=data)

    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    body = resp.json()
    assert body["teams_count"] == 12
    assert body["members_count"] == 30

    # Verify ZERO portfolio_url warnings
    portfolio_warnings = [w for w in body.get("warnings", []) if w.get("field") == "portfolio_url"]
    assert len(portfolio_warnings) == 0, f"Found unexpected portfolio_url warnings: {portfolio_warnings}"


def test_user_dataset_e2e_pipeline(client):
    """Full End-to-End Pipeline on user data:
    1. Ingest with zip companion
    2. Extract signals (academic + resume + github)
    3. Evaluate eligibility
    4. Score with scoring model
    5. Rank Top-X
    """
    with open(USER_CSV_PATH, "rb") as f_csv, open(USER_ZIP_PATH, "rb") as f_zip:
        discovery_res = discover_fields_from_bytes(f_csv.read(), "candidates.csv")
        mapping = discovery_res.suggested_mappings
        f_csv.seek(0)

        files = {
            "file": ("candidates.csv", f_csv, "text/csv"),
            "resumes_archive": ("resumes.zip", f_zip, "application/zip"),
        }
        data = {"mapping": json.dumps(mapping)}
        upload_resp = client.post("/api/ingestion/upload", files=files, data=data)
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        dataset_id = upload_resp.json()["dataset_id"]

    # 1. Signal Extraction
    extract_resp = client.post(
        "/api/signals/extract",
        json={
            "dataset_id": dataset_id,
            "signal_keys": [
                "academic_cgpa",
                "academic_year",
                "normalized_cgpa_10_scale",
                "resume_experience_years",
                "resume_programming_languages",
                "github_public_repos",
            ],
        },
    )
    assert extract_resp.status_code == 200, f"Signal extraction failed: {extract_resp.text}"
    extraction_run_id = extract_resp.json()["run_id"]

    # 2. Eligibility Evaluation using default configuration
    rule_configs_resp = client.get("/api/rules/configs")
    assert rule_configs_resp.status_code == 200
    rule_configs = rule_configs_resp.json()
    assert len(rule_configs) > 0
    rule_config = rule_configs[0]

    elig_resp = client.post(
        "/api/rules/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": extraction_run_id,
            "config_id": rule_config["config_id"],
            "version": rule_config["version"],
        },
    )
    assert elig_resp.status_code == 200, f"Eligibility evaluation failed: {elig_resp.text}"
    elig_run_id = elig_resp.json()["run_id"]
    summary = elig_resp.json()["summary"]
    assert summary["total_teams"] == 12

    # 3. Scoring Evaluation using default scoring model
    scoring_configs_resp = client.get("/api/scoring/configs")
    assert scoring_configs_resp.status_code == 200
    scoring_configs = scoring_configs_resp.json()
    assert len(scoring_configs) > 0
    scoring_config = scoring_configs[0]

    scoring_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": extraction_run_id,
            "eligibility_run_id": elig_run_id,
            "config_id": scoring_config["config_id"],
            "version": scoring_config["version"],
        },
    )
    assert scoring_resp.status_code == 200, f"Scoring evaluation failed: {scoring_resp.text}"
    scoring_run_id = scoring_resp.json()["run_id"]

    # 4. Top-X Ranking
    rank_resp = client.post(
        "/api/ranking/evaluate",
        json={
            "dataset_id": dataset_id,
            "eligibility_run_id": elig_run_id,
            "scoring_run_id": scoring_run_id,
            "top_x": 5,
            "include_needs_review": False,
        },
    )
    assert rank_resp.status_code == 200, f"Ranking failed: {rank_resp.text}"
    rank_body = rank_resp.json()
    assert len(rank_body["selected_teams"]) <= 5
    assert rank_body["summary"]["requested_top_x"] == 5
    assert rank_body["summary"]["total_teams_evaluated"] == 12
