"""Regression tests for Prompt 3.3: Duplicate Team Name Detection and Temporary IDs.

Verifies:
1. Detection of ambiguous duplicate team names in CSV across separate registration blocks.
2. Distinct temporary IDs assigned to ambiguous teams (temp_team_{slug}_{hash}_unresolved_{idx}).
3. Marking of temporary & unresolved identity (is_temporary_id=True, is_unresolved=True, duplicate_name_detected=True).
4. Prevention of incorrect grouping: multi-member teams on contiguous rows are NOT split.
5. Preservation of explicitly supplied team IDs when distinguishing teams with identical names.
6. Handling of mixed explicit and missing IDs for same-name teams.
7. Normalization across casing, punctuation, and whitespace variants.
8. JSON ingestion duplicate team name detection and temporary ID assignment.
9. JSON duplicate explicit team_id error retention.
10. Informative duplicate-team warnings in the ingestion response with affected locations.
11. Repeat upload determinism for identical files.
12. Downstream signal extraction preservation of temporary IDs and unresolved status.
13. API upload endpoint verification.
"""

from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from app.ingestion.parser import (
    generate_stable_team_id,
    generate_temporary_team_id,
    normalize_team_name,
    parse_csv,
    parse_json,
)
from app.main import app
from app.signals.registry import default_signal_registry

client = TestClient(app)
UPLOAD_URL = "/api/ingestion/upload"
EXTRACT_URL = "/api/signals/extract"


# =========================================================================
# 1. Normalization & ID Generation Unit Tests
# =========================================================================


class TestNormalizationAndIDGeneration:
    def test_normalize_team_name(self):
        """Punctuation, symbols, casing, and whitespace variants normalize to canonical form."""
        assert normalize_team_name("Code Warriors") == "code warriors"
        assert normalize_team_name("  code   warriors  ") == "code warriors"
        assert normalize_team_name("Code-Warriors") == "code warriors"
        assert normalize_team_name("code_warriors") == "code warriors"
        assert normalize_team_name("Code Warriors!") == "code warriors"
        assert normalize_team_name("  CODE   WARRIORS...  ") == "code warriors"

    def test_temporary_id_format(self):
        """Temporary IDs have distinct temp_team_ prefix and _unresolved_{idx} suffix."""
        id1 = generate_temporary_team_id("Code Warriors", 1)
        id2 = generate_temporary_team_id("Code Warriors", 2)

        assert id1.startswith("temp_team_code_warriors_")
        assert id1.endswith("_unresolved_1")
        assert id2.startswith("temp_team_code_warriors_")
        assert id2.endswith("_unresolved_2")
        assert id1 != id2


# =========================================================================
# 2. CSV Duplicate Detection & Temporary IDs
# =========================================================================


class TestCSVDuplicateTeamDetection:
    def test_csv_duplicate_team_names_non_contiguous_blocks_get_distinct_temporary_ids(self):
        """Non-contiguous occurrences of identical team names get distinct temporary IDs without splitting members."""
        csv_data = (
            "Team Name,Participant Name\n"
            "Code Warriors,Alice\n"
            "Code Warriors,Bob\n"
            "Byte Builders,Charlie\n"
            "Code Warriors,David\n"
            "Code Warriors,Eve\n"
        )
        mapping = {"Team Name": "team_name", "Participant Name": "name"}
        resp = parse_csv(csv_data.encode("utf-8"), mapping=mapping)

        assert resp.success is True
        assert resp.teams_count == 3
        assert resp.members_count == 5

        # We have two Code Warriors teams and one Byte Builders team
        cw_teams = [t for t in resp.teams if t.team_name == "Code Warriors"]
        bb_teams = [t for t in resp.teams if t.team_name == "Byte Builders"]

        assert len(cw_teams) == 2
        assert len(bb_teams) == 1

        team_cw1, team_cw2 = cw_teams[0], cw_teams[1]
        team_bb = bb_teams[0]

        # Distinct temporary IDs
        assert team_cw1.team_id != team_cw2.team_id
        assert team_cw1.team_id.startswith("temp_team_code_warriors_")
        assert team_cw1.team_id.endswith("_unresolved_1")
        assert team_cw2.team_id.startswith("temp_team_code_warriors_")
        assert team_cw2.team_id.endswith("_unresolved_2")

        # Marked clearly as temporary and unresolved
        assert team_cw1.is_temporary_id is True
        assert team_cw1.is_unresolved is True
        assert team_cw1.duplicate_name_detected is True

        assert team_cw2.is_temporary_id is True
        assert team_cw2.is_unresolved is True
        assert team_cw2.duplicate_name_detected is True

        # Byte Builders is regular and resolved
        assert team_bb.team_id.startswith("team_byte_builders_")
        assert team_bb.is_temporary_id is False
        assert team_bb.is_unresolved is False
        assert team_bb.duplicate_name_detected is False

        # Members within each team are preserved together (not split)
        assert len(team_cw1.members) == 2
        assert [m.name for m in team_cw1.members] == ["Alice", "Bob"]
        assert team_cw1.members[0].member_id == f"{team_cw1.team_id}_m1"
        assert team_cw1.members[1].member_id == f"{team_cw1.team_id}_m2"

        assert len(team_cw2.members) == 2
        assert [m.name for m in team_cw2.members] == ["David", "Eve"]
        assert team_cw2.members[0].member_id == f"{team_cw2.team_id}_m1"
        assert team_cw2.members[1].member_id == f"{team_cw2.team_id}_m2"

        # Check duplicate warnings
        dup_warnings = [w for w in resp.warnings if w.field == "team_name"]
        assert len(dup_warnings) == 2
        warn_team_ids = {w.team_id for w in dup_warnings}
        assert warn_team_ids == {team_cw1.team_id, team_cw2.team_id}
        assert any("rows 2-3" in w.message for w in dup_warnings)
        assert any("rows 5-6" in w.message for w in dup_warnings)

    def test_csv_legitimate_multi_member_team_not_split(self):
        """Contiguous rows of the same team name form ONE team without temporary IDs."""
        csv_data = (
            "team_name,name\n"
            "Code Warriors,Rahul\n"
            "Code Warriors,Priya\n"
            "Code Warriors,Aman\n"
        )
        resp = parse_csv(csv_data.encode("utf-8"))

        assert resp.success is True
        assert resp.teams_count == 1
        assert resp.members_count == 3

        team = resp.teams[0]
        assert team.team_name == "Code Warriors"
        assert team.team_id.startswith("team_code_warriors_")
        assert team.is_temporary_id is False
        assert team.is_unresolved is False
        assert team.duplicate_name_detected is False
        assert len(team.members) == 3

        # No duplicate warnings
        dup_warnings = [w for w in resp.warnings if w.field == "team_name"]
        assert len(dup_warnings) == 0

    def test_csv_explicit_ids_distinguishing_same_name_teams_preserved(self):
        """Explicitly supplied Team IDs distinguishing same-name teams are never overwritten."""
        csv_data = (
            "team_id,team_name,name\n"
            "T1,Alpha,Alice\n"
            "T1,Alpha,Bob\n"
            "T2,Alpha,Charlie\n"
        )
        resp = parse_csv(csv_data.encode("utf-8"))

        assert resp.success is True
        assert resp.teams_count == 2
        assert resp.members_count == 3

        teams_by_id = {t.team_id: t for t in resp.teams}
        assert "T1" in teams_by_id
        assert "T2" in teams_by_id

        t1 = teams_by_id["T1"]
        t2 = teams_by_id["T2"]

        # Explicit IDs preserved, not overwritten by temp IDs
        assert t1.team_id == "T1"
        assert t2.team_id == "T2"
        assert t1.is_temporary_id is False
        assert t2.is_temporary_id is False
        assert t1.duplicate_name_detected is True
        assert t2.duplicate_name_detected is True

        assert len(t1.members) == 2
        assert len(t2.members) == 1

        # Warnings notify organizer of duplicate name across explicit IDs
        dup_warnings = [w for w in resp.warnings if w.field == "team_name"]
        assert len(dup_warnings) == 2
        assert any("Preserved explicit ID 'T1'" in w.message and "T2" in w.message for w in dup_warnings)
        assert any("Preserved explicit ID 'T2'" in w.message and "T1" in w.message for w in dup_warnings)

    def test_csv_mixed_explicit_and_missing_ids_for_duplicate_names(self):
        """One team has explicit ID, another has identical name but missing ID."""
        csv_data = (
            "team_id,team_name,name\n"
            "EXPLICIT_1,Delta Force,Alice\n"
            ",Delta Force,Bob\n"
        )
        resp = parse_csv(csv_data.encode("utf-8"))

        assert resp.success is True
        assert resp.teams_count == 2
        assert resp.members_count == 2

        teams_by_id = {t.team_id: t for t in resp.teams}
        assert "EXPLICIT_1" in teams_by_id

        explicit_team = teams_by_id["EXPLICIT_1"]
        temp_team = [t for t in resp.teams if t.team_id != "EXPLICIT_1"][0]

        assert explicit_team.is_temporary_id is False
        assert explicit_team.duplicate_name_detected is True

        assert temp_team.is_temporary_id is True
        assert temp_team.is_unresolved is True
        assert temp_team.duplicate_name_detected is True
        assert temp_team.team_id.startswith("temp_team_delta_force_")

        dup_warnings = [w for w in resp.warnings if w.field == "team_name"]
        assert len(dup_warnings) == 2

    def test_team_name_normalization_variants_detected_as_duplicates(self):
        """Punctuation and casing differences in team names across non-contiguous blocks are detected as duplicates."""
        csv_data = (
            "team_name,name\n"
            "Code Warriors,Alice\n"
            "Byte Builders,Charlie\n"
            "code-warriors,David\n"
        )
        resp = parse_csv(csv_data.encode("utf-8"))

        assert resp.success is True
        assert resp.teams_count == 3

        cw_teams = [t for t in resp.teams if normalize_team_name(t.team_name) == "code warriors"]
        assert len(cw_teams) == 2
        assert cw_teams[0].is_temporary_id is True
        assert cw_teams[1].is_temporary_id is True
        assert cw_teams[0].team_id != cw_teams[1].team_id


# =========================================================================
# 3. JSON Duplicate Detection & Temporary IDs
# =========================================================================


class TestJSONDuplicateTeamDetection:
    def test_json_duplicate_teams_without_ids_receive_distinct_temporary_ids(self):
        """JSON payload with duplicate team names without IDs succeeds with temporary IDs."""
        json_data = [
            {
                "team_name": "Phoenix",
                "members": [{"name": "Elena"}, {"name": "Marcus"}],
            },
            {
                "team_name": "Phoenix",
                "members": [{"name": "Lucas"}],
            },
        ]
        resp = parse_json(json.dumps(json_data).encode("utf-8"))

        assert resp.success is True
        assert resp.teams_count == 2
        assert resp.members_count == 3

        t1, t2 = resp.teams[0], resp.teams[1]
        assert t1.team_id != t2.team_id
        assert t1.team_id.startswith("temp_team_phoenix_")
        assert t1.team_id.endswith("_unresolved_1")
        assert t2.team_id.startswith("temp_team_phoenix_")
        assert t2.team_id.endswith("_unresolved_2")

        assert t1.is_temporary_id is True and t2.is_temporary_id is True
        assert t1.is_unresolved is True and t2.is_unresolved is True
        assert t1.duplicate_name_detected is True and t2.duplicate_name_detected is True

        assert len(t1.members) == 2
        assert len(t2.members) == 1

        dup_warnings = [w for w in resp.warnings if w.field == "team_name"]
        assert len(dup_warnings) == 2
        assert any("team index 0" in w.message for w in dup_warnings)
        assert any("team index 1" in w.message for w in dup_warnings)

    def test_json_duplicate_teams_with_explicit_ids_preserved(self):
        """JSON payload with duplicate team names but distinct explicit IDs preserves IDs."""
        json_data = [
            {
                "team_id": "P1",
                "team_name": "Phoenix",
                "members": [{"name": "Elena"}],
            },
            {
                "team_id": "P2",
                "team_name": "Phoenix",
                "members": [{"name": "Lucas"}],
            },
        ]
        resp = parse_json(json.dumps(json_data).encode("utf-8"))

        assert resp.success is True
        assert resp.teams_count == 2
        assert resp.teams[0].team_id == "P1"
        assert resp.teams[1].team_id == "P2"
        assert resp.teams[0].duplicate_name_detected is True
        assert resp.teams[1].duplicate_name_detected is True
        assert resp.teams[0].is_temporary_id is False
        assert resp.teams[1].is_temporary_id is False

        dup_warnings = [w for w in resp.warnings if w.field == "team_name"]
        assert len(dup_warnings) == 2

    def test_json_duplicate_explicit_team_id_still_fails_validation(self):
        """Duplicate explicit team_ids in JSON must still fail validation."""
        json_data = [
            {
                "team_id": "P1",
                "team_name": "Phoenix",
                "members": [{"name": "Elena"}],
            },
            {
                "team_id": "P1",
                "team_name": "Phoenix",
                "members": [{"name": "Lucas"}],
            },
        ]
        resp = parse_json(json.dumps(json_data).encode("utf-8"))

        assert resp.success is False
        assert any("duplicate team_id 'p1'" in e.message.lower() for e in resp.errors)


# =========================================================================
# 4. Repeat Upload Stability & Downstream Processing
# =========================================================================


class TestRepeatUploadAndDownstreamSeparation:
    def test_deterministic_temporary_ids_on_repeat_upload(self):
        """Repeated ingestion of identical files produces deterministic temporary IDs."""
        csv_data = (
            "team_name,name\n"
            "Titans,Alice\n"
            "Spartans,Bob\n"
            "Titans,Charlie\n"
        )
        run1 = parse_csv(csv_data.encode("utf-8"))
        run2 = parse_csv(csv_data.encode("utf-8"))

        assert run1.success is True and run2.success is True
        assert [t.team_id for t in run1.teams] == [t.team_id for t in run2.teams]
        assert [t.is_temporary_id for t in run1.teams] == [t.is_temporary_id for t in run2.teams]

    def test_downstream_signal_extraction_maintains_temporary_team_separation(self):
        """Temporary teams remain distinct records during signal extraction with unresolved flags intact."""
        csv_data = (
            "team_name,name,github_url\n"
            "Warriors,Alice,https://github.com/alice\n"
            "Knights,Bob,https://github.com/bob\n"
            "Warriors,Charlie,https://github.com/charlie\n"
        )
        ingest_resp = parse_csv(csv_data.encode("utf-8"))
        assert ingest_resp.success is True
        assert len(ingest_resp.teams) == 3

        # Run extraction using the signal registry
        extract_resp = default_signal_registry.execute_extraction(
            teams=ingest_resp.teams,
            selected_signals=["academic_cgpa"],  # run single local signal
        )

        assert extract_resp.total_teams == 3
        assert extract_resp.total_members == 3
        assert len(extract_resp.teams) == 3

        # Verify that temporary ID flags are preserved on TeamExtractionResult
        res_by_name = {t.team_name: [] for t in extract_resp.teams}
        for t in extract_resp.teams:
            res_by_name[t.team_name].append(t)

        assert len(res_by_name["Warriors"]) == 2
        w1, w2 = res_by_name["Warriors"]
        assert w1.team_id != w2.team_id
        assert w1.is_temporary_id is True and w2.is_temporary_id is True
        assert w1.is_unresolved is True and w2.is_unresolved is True

        knights = res_by_name["Knights"][0]
        assert knights.is_temporary_id is False
        assert knights.is_unresolved is False

    def test_api_upload_endpoint_returns_duplicate_warnings_and_temporary_flags(self):
        """POST /api/ingestion/upload includes temporary flags and duplicate warnings in response JSON."""
        csv_content = (
            "team_name,name\n"
            "Omega,Member1\n"
            "Sigma,Member2\n"
            "Omega,Member3\n"
        )
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("registrations.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["success"] is True
        assert body["teams_count"] == 3

        omega_teams = [t for t in body["teams"] if t["team_name"] == "Omega"]
        assert len(omega_teams) == 2
        for t in omega_teams:
            assert t["is_temporary_id"] is True
            assert t["is_unresolved"] is True
            assert t["duplicate_name_detected"] is True

        dup_warnings = [w for w in body["warnings"] if w["field"] == "team_name"]
        assert len(dup_warnings) == 2
