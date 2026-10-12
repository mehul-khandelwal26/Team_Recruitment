"""Tests for dynamic registration forms, field discovery, and schema mapping.

Validates:
- Preservation of arbitrary CSV and JSON fields
- Distinction between raw_data, normalized fields, and custom_fields
- Field discovery and type inference endpoint (/api/ingestion/inspect)
- Configurable field mapping via /api/ingestion/upload
- Suggested mappings for common aliases and ambiguous cases
- Missing required structural mappings vs unmapped custom fields
- Signal extractor registry contracts and selective extractor queries
- Scoring boundaries architecture schemas
"""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ingestion import FieldPresenceStatus
from app.signals.registry import default_signal_registry
from app.scoring.schemas import CriterionType, EvaluationCriterion, ScoringConfiguration

client = TestClient(app)

UPLOAD_URL = "/api/ingestion/upload"
INSPECT_URL = "/api/ingestion/inspect"
CANONICAL_URL = "/api/ingestion/canonical-fields"


# =========================================================================
# 1. Arbitrary CSV Columns Preservation (Forms A, B, C)
# =========================================================================


class TestArbitraryCSVFields:
    def test_form_a_preserves_custom_fields(self):
        """Form A: Team Name, Member Name, CGPA, GitHub URL, Academic Year, Why do you want to join?"""
        csv_data = (
            "team_id,team_name,member_id,name,cgpa,github_url,academic_year,Why do you want to join?\n"
            "T1,Alpha,M1,Alice,9.4,https://github.com/alice,3rd Year,Passionate about AI ethics\n"
        )
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("form_a.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
        member = body["teams"][0]["members"][0]

        # Normalized recognized fields
        assert member["name"] == "Alice"
        assert member["cgpa"] == "9.4"
        assert member["github_url"] == "https://github.com/alice"
        assert member["academic_year"] == "3rd Year"

        # Arbitrary custom field preserved
        assert "Why do you want to join?" in member["custom_fields"]
        assert member["custom_fields"]["Why do you want to join?"] == "Passionate about AI ethics"

        # Raw data preserved
        assert "Why do you want to join?" in member["raw_data"]
        assert member["raw_data"]["Why do you want to join?"] == "Passionate about AI ethics"

        # Unmapped fields reported in response
        assert "Why do you want to join?" in body["unmapped_fields"]

    def test_form_b_preserves_custom_domain_and_hackathons(self):
        """Form B: Resume, Previous Projects, Preferred Domain, Number of Hackathons Participated In."""
        csv_data = (
            "team_id,team_name,member_id,name,resume_url,Previous Projects,Preferred Domain,Hackathons Count\n"
            "T2,Beta,M2,Bob,https://resume.com/bob,Built DEX,Web3,5\n"
        )
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("form_b.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        )
        body = resp.json()
        assert body["success"] is True
        member = body["teams"][0]["members"][0]

        assert member["resume_url"] == "https://resume.com/bob"
        assert member["custom_fields"]["Previous Projects"] == "Built DEX"
        assert member["custom_fields"]["Preferred Domain"] == "Web3"
        assert member["custom_fields"]["Hackathons Count"] == "5"

    def test_empty_custom_field_does_not_crash(self):
        """Custom field present with empty value becomes None, not error."""
        csv_data = (
            "team_id,team_name,member_id,name,Why do you want to join?\n"
            "T1,Alpha,M1,Alice,\n"
        )
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("teams.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        )
        body = resp.json()
        assert body["success"] is True
        member = body["teams"][0]["members"][0]
        assert member["custom_fields"]["Why do you want to join?"] is None


# =========================================================================
# 2. Arbitrary JSON Attributes Preservation
# =========================================================================


class TestArbitraryJSONFields:
    def test_json_team_and_member_custom_fields(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "track": "Open Innovation",
                "pitch_video_url": "https://youtube.com/watch?v=123",
                "members": [
                    {
                        "member_id": "M1",
                        "name": "Alice",
                        "cgpa": "9.8",
                        "dietary_preference": "Vegan",
                        "tshirt_size": "M",
                    }
                ],
            }
        ]
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("teams.json", io.BytesIO(json.dumps(data).encode()), "application/json")},
        )
        body = resp.json()
        assert body["success"] is True

        team = body["teams"][0]
        # Team-level custom attributes
        assert team["custom_fields"]["track"] == "Open Innovation"
        assert team["custom_fields"]["pitch_video_url"] == "https://youtube.com/watch?v=123"

        # Member-level custom attributes
        member = team["members"][0]
        assert member["custom_fields"]["dietary_preference"] == "Vegan"
        assert member["custom_fields"]["tshirt_size"] == "M"
        assert member["cgpa"] == "9.8"


# =========================================================================
# 3. Field Discovery & Schema Inspection (/api/ingestion/inspect)
# =========================================================================


class TestFieldDiscoveryEndpoint:
    def test_inspect_csv_schema_and_suggestions(self):
        csv_data = (
            "Team,Group Title,Participant ID,Participant Name,Email Address,GitHub Profile,CPI,Why Join\n"
            "T1,Alpha,M1,Alice,alice@example.com,https://github.com/alice,8.5,Curious\n"
            "T1,Alpha,M2,Bob,bob@example.com,https://github.com/bob,9.1,Enthusiastic\n"
        )
        resp = client.post(
            INSPECT_URL,
            files={"file": ("registrations.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["file_type"] == "csv"
        assert body["total_records"] == 2
        assert body["total_teams_detected"] == 1

        fields_by_name = {f["original_name"]: f for f in body["discovered_fields"]}

        # Check suggestions
        assert fields_by_name["Team"]["suggested_mapping"] == "team_name" or fields_by_name["Team"]["suggested_mapping"] in ["team_id", "team_name"]
        assert fields_by_name["Participant Name"]["suggested_mapping"] == "name"
        assert fields_by_name["Participant ID"]["suggested_mapping"] == "member_id"
        assert fields_by_name["Email Address"]["suggested_mapping"] == "email"
        assert fields_by_name["Email Address"]["inferred_type"] == "email"
        assert fields_by_name["GitHub Profile"]["suggested_mapping"] == "github_url"
        assert fields_by_name["GitHub Profile"]["inferred_type"] == "url"

        # CPI matches CGPA with explanation
        cpi_field = fields_by_name["CPI"]
        assert cpi_field["suggested_mapping"] == "cgpa"
        assert "scale" in cpi_field["suggestion_reason"].lower()

        # Why Join is unmapped custom field
        why_field = fields_by_name["Why Join"]
        assert why_field["status"] == "unmapped"
        assert why_field["suggested_mapping"] is None

    def test_inspect_json_schema(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [
                    {
                        "member_id": "M1",
                        "name": "Alice",
                        "portfolio_url": "https://alice.dev",
                    }
                ],
            }
        ]
        resp = client.post(
            INSPECT_URL,
            files={"file": ("data.json", io.BytesIO(json.dumps(data).encode()), "application/json")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["file_type"] == "json"
        assert len(body["missing_structural_fields"]) == 0

    def test_canonical_fields_catalog(self):
        resp = client.get(CANONICAL_URL)
        assert resp.status_code == 200
        catalog = resp.json()
        keys = {c["field_key"] for c in catalog}
        assert "team_id" in keys
        assert "team_name" in keys
        assert "member_id" in keys
        assert "name" in keys
        assert "github_url" in keys
        assert "cgpa" in keys


# =========================================================================
# 4. Configurable Field Mapping
# =========================================================================


class TestConfigurableFieldMapping:
    def test_upload_with_explicit_mapping(self):
        """CSV with non-standard column names mapped explicitly via mapping form parameter."""
        csv_data = (
            "Group ID,Group Name,Participant Code,Full Name,Motivation\n"
            "T10,Hackers,P1,Charlie,To learn\n"
        )
        mapping = {
            "Group ID": "team_id",
            "Group Name": "team_name",
            "Participant Code": "member_id",
            "Full Name": "name",
        }
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("custom.csv", io.BytesIO(csv_data.encode()), "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
        team = body["teams"][0]
        assert team["team_id"] == "T10"
        assert team["team_name"] == "Hackers"
        member = team["members"][0]
        assert member["member_id"] == "P1"
        assert member["name"] == "Charlie"
        assert member["custom_fields"]["Motivation"] == "To learn"

    def test_upload_with_missing_required_mapping(self):
        """When an essential structural field is not mapped, returns clear error."""
        csv_data = (
            "Group ID,Participant Code,Full Name\n"
            "T10,P1,Charlie\n"
        )
        mapping = {
            "Group ID": "team_id",
            "Participant Code": "member_id",
            "Full Name": "name",
            # team_name is missing!
        }
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("custom.csv", io.BytesIO(csv_data.encode()), "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
        body = resp.json()
        assert body["success"] is False
        assert any("team_name" in e["message"] for e in body["errors"])

    def test_upload_with_duplicate_required_target_mapping(self):
        """Mapping two columns to the same required field raises error."""
        csv_data = (
            "Col1,Col2,ID,Name\n"
            "T1,T2,M1,Alice\n"
        )
        mapping = {
            "Col1": "team_id",
            "Col2": "team_id",  # duplicate target
            "ID": "member_id",
            "Name": "name",
        }
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("custom.csv", io.BytesIO(csv_data.encode()), "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
        body = resp.json()
        assert body["success"] is False
        assert any("multiple columns mapped" in e["message"].lower() for e in body["errors"])

    def test_upload_with_malformed_mapping_json(self):
        csv_data = "team_id,team_name,member_id,name\nT1,Alpha,M1,Alice\n"
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("data.csv", io.BytesIO(csv_data.encode()), "text/csv")},
            data={"mapping": "{not valid json}"},
        )
        body = resp.json()
        assert body["success"] is False
        assert any("invalid field mapping json" in e["message"].lower() for e in body["errors"])


# =========================================================================
# 5. Missing Data States & Status Tracking
# =========================================================================


class TestMissingDataStates:
    def test_distinguishes_not_collected_vs_collected_blank(self):
        """Resume URL not collected vs GitHub URL collected but empty."""
        csv_data = (
            "team_id,team_name,member_id,name,github_url\n"
            "T1,Alpha,M1,Alice,\n"  # github_url column present, cell empty
        )
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("data.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        )
        body = resp.json()
        assert body["success"] is True
        member = body["teams"][0]["members"][0]

        statuses = member["field_statuses"]
        # github_url was in the form but blank
        assert statuses["github_url"] == FieldPresenceStatus.COLLECTED_BLANK.value
        # resume_url was never collected by the form
        assert statuses["resume_url"] == FieldPresenceStatus.NOT_COLLECTED.value
        # name was provided
        assert statuses["name"] == FieldPresenceStatus.PRESENT.value


# =========================================================================
# 6. Signal Extraction Architecture & Extractor Contracts
# =========================================================================


class TestSignalExtractionContracts:
    def test_default_signal_registry_has_standard_contracts(self):
        descriptors = default_signal_registry.list_descriptors()
        ids = {d.extractor_id for d in descriptors}
        assert "github_analyzer" in ids
        assert "resume_parser" in ids
        assert "academic_metrics" in ids
        assert "portfolio_analyzer" in ids

    def test_query_compatible_extractors(self):
        """Organizers with only GitHub data get only the GitHub extractor."""
        available_fields = {"github_url", "name"}
        compatible = default_signal_registry.get_compatible_extractors(available_fields)
        ids = {d.extractor_id for d in compatible}
        assert "github_analyzer" in ids
        assert "resume_parser" not in ids

    def test_extractors_are_not_enabled_by_default(self):
        """All extractors must require explicit organizer selection."""
        for desc in default_signal_registry.list_descriptors():
            assert desc.is_enabled_by_default is False


# =========================================================================
# 7. Scoring Boundaries Architecture
# =========================================================================


class TestScoringBoundaries:
    def test_presence_of_field_does_not_imply_scoring(self):
        """Verification of scoring configuration contract."""
        criterion = EvaluationCriterion(
            criterion_id="crit_1",
            name="GitHub Activity",
            criterion_type=CriterionType.NUMERIC_WEIGHT,
            target_signal_key="github_public_repo_count",
            weight=2.0,
            is_selected=False,  # NOT selected by default
        )
        config = ScoringConfiguration(
            config_id="cfg_1",
            name="Hackathon Evaluation 2026",
            selected_criteria=[criterion],
        )
        assert config.selected_criteria[0].is_selected is False
