"""Integration tests verifying the 4 Phase 5 integration fixes.

Covers:
- FIX 1: POST /api/scoring/evaluate with eligibility_run_id (no HTTP 500 crash).
- FIX 2: Manual overrides merged into scoring results via get_effective_run.
- FIX 3: Ingestion cross-team colliding member_id disambiguation for CSV and JSON.
- FIX 4: Signal extraction flattening and end-to-end chaining through rules and scoring.
"""

from __future__ import annotations

import json
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.ingestion.parser import parse_csv, parse_json
from app.main import app
from app.rules.config_store import default_config_store
from app.rules.store import default_override_store, default_run_store
from app.scoring.config_store import default_scoring_config_store
from app.scoring.store import default_scoring_run_store
from app.signals.flatten import flatten_extraction_signals
from app.signals.schemas import (
    ExtractedSignal,
    ExtractionRunResponse,
    MemberExtractionResult,
    SignalEvidence,
    SignalStatus,
    TeamExtractionResult,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_stores():
    """Ensure clean store state before and after each test."""
    default_config_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    default_scoring_config_store.reset()
    default_scoring_run_store.reset()
    yield
    default_config_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    default_scoring_config_store.reset()
    default_scoring_run_store.reset()


# ---------------------------------------------------------------------------
# FIX 1: Scoring with eligibility_run_id does not crash with HTTP 500
# ---------------------------------------------------------------------------


def test_fix1_scoring_with_eligibility_run_id():
    """Verify that POST /api/scoring/evaluate succeeds (200) with eligibility_run_id."""
    team_data = {
        "team_id": "team_alpha",
        "team_name": "Team Alpha",
        "members": [
            {
                "member_id": "m1",
                "name": "Alice",
                "email": "alice@example.com",
                "github_url": "https://github.com/alice",
            },
            {
                "member_id": "m2",
                "name": "Bob",
                "email": "bob@example.com",
                "github_url": "https://github.com/bob",
            },
        ],
    }

    # 1. Run eligibility evaluation
    elig_resp = client.post(
        "/api/rules/evaluate",
        json={
            "teams": [team_data],
            "config_id": "basic",
        },
    )
    assert elig_resp.status_code == 200, elig_resp.text
    elig_data = elig_resp.json()
    elig_run_id = elig_data["run_id"]
    expected_status = elig_data["teams"][0]["status"]

    # 2. Score using eligibility_run_id
    score_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": [team_data],
            "config_id": "balanced",
            "eligibility_run_id": elig_run_id,
        },
    )
    assert score_resp.status_code == 200, score_resp.text
    score_data = score_resp.json()
    assert len(score_data["teams"]) == 1
    team_result = score_data["teams"][0]
    assert team_result["team_id"] == "team_alpha"
    assert team_result["eligibility_status"] == expected_status
    # Check that reasons were joined into summary
    assert team_result["eligibility_summary"] is not None or expected_status == "eligible"


# ---------------------------------------------------------------------------
# FIX 2: Manual overrides are applied to scoring results
# ---------------------------------------------------------------------------


def test_fix2_manual_overrides_applied_to_scoring():
    """Verify that manual overrides applied to an eligibility run are reflected in scoring."""
    team_data = {
        "team_id": "team_beta",
        "team_name": "Team Beta",
        "members": [
            {
                "member_id": "m1",
                "name": "Charlie",
                "email": "charlie@example.com",
            },
            {
                "member_id": "m2",
                "name": "Dana",
                "email": "dana@example.com",
            },
        ],
    }

    # 1. Run eligibility evaluation
    elig_resp = client.post(
        "/api/rules/evaluate",
        json={
            "teams": [team_data],
            "config_id": "basic",
        },
    )
    assert elig_resp.status_code == 200
    elig_run_id = elig_resp.json()["run_id"]

    # 2. Apply manual override to disqualify team_beta
    override_resp = client.post(
        f"/api/rules/runs/{elig_run_id}/teams/team_beta/override",
        json={
            "override_status": "INELIGIBLE",
            "reason": "Disqualified due to code of conduct violation.",
            "overridden_by": "lead_judge",
        },
    )
    assert override_resp.status_code == 200, override_resp.text

    # 3. Evaluate scoring with eligibility_run_id
    score_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": [team_data],
            "config_id": "balanced",
            "eligibility_run_id": elig_run_id,
        },
    )
    assert score_resp.status_code == 200, score_resp.text
    score_data = score_resp.json()
    scored_team = score_data["teams"][0]

    # Verify overridden status and justification reason
    assert scored_team["eligibility_status"] in ("ineligible", "INELIGIBLE")
    assert scored_team["eligibility_summary"] is not None
    assert "Disqualified due to code of conduct violation." in scored_team["eligibility_summary"]
    assert "lead_judge" in scored_team["eligibility_summary"]


# ---------------------------------------------------------------------------
# FIX 3: Cross-team colliding member IDs disambiguation (CSV and JSON)
# ---------------------------------------------------------------------------


def test_fix3_ingestion_duplicate_member_id_disambiguation():
    """Verify cross-team colliding member IDs are disambiguated with warnings and preserved raw_data."""
    # --- Part A: CSV Ingestion ---
    csv_content = (
        "team_name,member_id,name,email\n"
        "Team Red,1,Alice,alice@red.com\n"
        "Team Red,2,Bob,bob@red.com\n"
        "Team Blue,1,Charlie,charlie@blue.com\n"
        "Team Blue,2,Dana,dana@blue.com\n"
        "Team Blue,3,UniqueEvan,evan@blue.com\n"
    )
    csv_resp = parse_csv(csv_content.encode("utf-8"))
    assert csv_resp.success is True
    assert csv_resp.teams_count == 2

    team_red = next(t for t in csv_resp.teams if "red" in t.team_id.lower() or "Red" in t.team_name)
    team_blue = next(t for t in csv_resp.teams if "blue" in t.team_id.lower() or "Blue" in t.team_name)

    # Check colliding IDs 1 and 2 disambiguated
    red_m1 = next(m for m in team_red.members if m.name == "Alice")
    red_m2 = next(m for m in team_red.members if m.name == "Bob")
    blue_m1 = next(m for m in team_blue.members if m.name == "Charlie")
    blue_m2 = next(m for m in team_blue.members if m.name == "Dana")
    blue_m3 = next(m for m in team_blue.members if m.name == "UniqueEvan")

    assert red_m1.member_id == f"{team_red.team_id}_1"
    assert red_m1.raw_data.get("original_member_id") == "1"

    assert red_m2.member_id == f"{team_red.team_id}_2"
    assert red_m2.raw_data.get("original_member_id") == "2"

    assert blue_m1.member_id == f"{team_blue.team_id}_1"
    assert blue_m1.raw_data.get("original_member_id") == "1"

    assert blue_m2.member_id == f"{team_blue.team_id}_2"
    assert blue_m2.raw_data.get("original_member_id") == "2"

    # Non-colliding member 3 must NOT be rewritten
    assert blue_m3.member_id == "3"
    assert "original_member_id" not in blue_m3.raw_data

    # Check warnings
    disambig_warns = [w for w in csv_resp.warnings if "Disambiguated colliding member_id" in w.message]
    assert len(disambig_warns) == 4

    # --- Part B: JSON Ingestion ---
    json_data = [
        {
            "team_id": "T_100",
            "team_name": "Team Golden",
            "members": [
                {"member_id": "1", "name": "Member G1"},
                {"member_id": "2", "name": "Member G2"},
            ],
        },
        {
            "team_id": "T_200",
            "team_name": "Team Silver",
            "members": [
                {"member_id": "1", "name": "Member S1"},
                {"member_id": "2", "name": "Member S2"},
            ],
        },
    ]
    json_resp = parse_json(json.dumps(json_data).encode("utf-8"))
    assert json_resp.success is True
    assert json_resp.teams_count == 2

    t1 = next(t for t in json_resp.teams if t.team_id == "T_100")
    t2 = next(t for t in json_resp.teams if t.team_id == "T_200")

    assert t1.members[0].member_id == "T_100_1"
    assert t1.members[0].raw_data["original_member_id"] == "1"
    assert t1.members[1].member_id == "T_100_2"
    assert t1.members[1].raw_data["original_member_id"] == "2"

    assert t2.members[0].member_id == "T_200_1"
    assert t2.members[0].raw_data["original_member_id"] == "1"
    assert t2.members[1].member_id == "T_200_2"
    assert t2.members[1].raw_data["original_member_id"] == "2"

    json_disambig_warns = [w for w in json_resp.warnings if "Disambiguated colliding member_id" in w.message]
    assert len(json_disambig_warns) == 4


# ---------------------------------------------------------------------------
# FIX 4: Signal extraction flattening and end-to-end chaining
# ---------------------------------------------------------------------------


def test_fix4_signals_flatten_and_end_to_end_chain():
    """Verify /api/signals/extract -> POST /api/signals/flatten -> /api/rules/evaluate & /api/scoring/evaluate."""
    teams_payload = [
        {
            "team_id": "team_delta",
            "team_name": "Team Delta",
            "members": [
                {
                    "member_id": "mem_d1",
                    "name": "Dave",
                    "email": "dave@example.com",
                    "github_url": "https://github.com/dave",
                    "cgpa": "8.5",
                    "academic_year": "2024",
                },
                {
                    "member_id": "mem_d2",
                    "name": "Eve",
                    "email": "eve@example.com",
                    "github_url": "https://github.com/eve",
                    "cgpa": "9.0",
                    "academic_year": "2024",
                },
            ],
        }
    ]

    # 1. Execute signal extraction via API
    extract_resp = client.post(
        "/api/signals/extract",
        json={
            "teams": teams_payload,
            "selected_signals": ["academic_cgpa", "academic_year"],
        },
    )
    assert extract_resp.status_code == 200, extract_resp.text
    extraction_data = extract_resp.json()
    assert "teams" in extraction_data
    assert "member_results" in extraction_data["teams"][0]

    # 2. Test python helper directly
    flat_helper = flatten_extraction_signals(extraction_data)
    assert isinstance(flat_helper, list)
    assert len(flat_helper) == 2
    assert flat_helper[0]["member_id"] == "mem_d1"
    assert "signals" in flat_helper[0]

    # 3. Post to /api/signals/flatten endpoint
    flatten_resp = client.post(
        "/api/signals/flatten",
        json=extraction_data,
    )
    assert flatten_resp.status_code == 200, flatten_resp.text
    flat_signals = flatten_resp.json()
    assert isinstance(flat_signals, list)
    assert len(flat_signals) == 2
    assert flat_signals[0]["member_id"] == "mem_d1"
    assert any(s["signal_key"] == "academic_cgpa" for s in flat_signals[0]["signals"])

    # 4. Chain flat_signals directly into /api/rules/evaluate
    rules_resp = client.post(
        "/api/rules/evaluate",
        json={
            "teams": teams_payload,
            "signals": flat_signals,
            "config_id": "basic",
        },
    )
    assert rules_resp.status_code == 200, rules_resp.text
    rules_data = rules_resp.json()
    assert len(rules_data["teams"]) == 1
    assert str(rules_data["teams"][0]["status"]).upper() in ("ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW")

    # 5. Chain flat_signals directly into /api/scoring/evaluate
    scoring_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": teams_payload,
            "signals": flat_signals,
            "config_id": "balanced",
        },
    )
    assert scoring_resp.status_code == 200, scoring_resp.text
    scoring_data = scoring_resp.json()
    assert len(scoring_data["teams"]) == 1
    team_res = scoring_data["teams"][0]
    assert team_res["score_status"] in ("calculated", "CALCULATED")
    assert team_res["final_score"] is not None
