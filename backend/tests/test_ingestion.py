"""Tests for the registration data ingestion endpoint.

Covers CSV and JSON uploads including:
- Valid uploads with complete and partial data
- Missing optional fields (warnings, not errors)
- Empty files
- Invalid / malformed files
- Missing required columns / fields
- Duplicate member IDs
- Inconsistent team names
- Invalid field values (e.g. bad email)
"""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

UPLOAD_URL = "/api/ingestion/upload"


# =========================================================================
# Helpers
# =========================================================================

def _upload_csv(content: str, filename: str = "teams.csv"):
    """Upload a CSV string via the test client."""
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, io.BytesIO(content.encode()), "text/csv")},
    )


def _upload_json(data, filename: str = "teams.json"):
    """Upload a JSON-serializable object via the test client."""
    raw = json.dumps(data).encode() if not isinstance(data, bytes) else data
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, io.BytesIO(raw), "application/json")},
    )


def _upload_json_string(text: str, filename: str = "teams.json"):
    """Upload raw text as JSON via the test client."""
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, io.BytesIO(text.encode()), "application/json")},
    )


# =========================================================================
# 1. Health check still works
# =========================================================================

class TestHealthEndpoint:
    def test_health_check(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"


# =========================================================================
# 2. Valid CSV uploads
# =========================================================================

class TestValidCSV:
    def test_single_team_single_member(self):
        csv = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "T1,Alpha,M1,Alice,alice@example.com,https://resume.com/alice,https://github.com/alice,https://linkedin.com/in/alice,https://alice.dev\n"
        )
        resp = _upload_csv(csv)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
        assert body["members_count"] == 1
        assert len(body["teams"]) == 1
        assert body["teams"][0]["team_id"] == "T1"
        assert body["teams"][0]["members"][0]["name"] == "Alice"

    def test_single_team_multiple_members(self):
        csv = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "T1,Alpha,M1,Alice,alice@example.com,,,,\n"
            "T1,Alpha,M2,Bob,bob@example.com,,,,\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
        assert body["members_count"] == 2

    def test_multiple_teams(self):
        csv = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "T1,Alpha,M1,Alice,alice@example.com,,,,\n"
            "T2,Beta,M2,Bob,bob@example.com,,,,\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 2
        assert body["members_count"] == 2


# =========================================================================
# 3. Valid JSON uploads
# =========================================================================

class TestValidJSON:
    def test_single_team(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [
                    {
                        "member_id": "M1",
                        "name": "Alice",
                        "email": "alice@example.com",
                        "github_url": "https://github.com/alice",
                    }
                ],
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
        assert body["members_count"] == 1

    def test_multiple_teams(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [
                    {"member_id": "M1", "name": "Alice"},
                ],
            },
            {
                "team_id": "T2",
                "team_name": "Beta",
                "members": [
                    {"member_id": "M2", "name": "Bob"},
                    {"member_id": "M3", "name": "Carol"},
                ],
            },
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 2
        assert body["members_count"] == 3


# =========================================================================
# 4. Missing optional fields → warnings (NOT errors)
# =========================================================================

class TestMissingOptionalFields:
    def test_csv_missing_optional_produces_warnings(self):
        csv = (
            "team_id,team_name,member_id,name\n"
            "T1,Alpha,M1,Alice\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
        # All 5 optional fields missing → 5 warnings
        assert len(body["warnings"]) == 5
        warning_fields = {w["field"] for w in body["warnings"]}
        assert "email" in warning_fields
        assert "github_url" in warning_fields

    def test_json_missing_optional_produces_warnings(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [{"member_id": "M1", "name": "Alice"}],
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is True
        assert len(body["warnings"]) == 5

    def test_partial_optional_fields(self):
        """Only some optional fields missing → warnings only for those."""
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [
                    {
                        "member_id": "M1",
                        "name": "Alice",
                        "email": "alice@example.com",
                        "github_url": "https://github.com/alice",
                    }
                ],
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is True
        # 3 optional fields missing: resume_url, linkedin_url, portfolio_url
        assert len(body["warnings"]) == 3
        warning_fields = {w["field"] for w in body["warnings"]}
        assert "email" not in warning_fields
        assert "resume_url" in warning_fields


# =========================================================================
# 5. Empty files
# =========================================================================

class TestEmptyFiles:
    def test_empty_csv(self):
        resp = _upload_csv("")
        body = resp.json()
        assert body["success"] is False
        assert any("empty" in e["message"].lower() for e in body["errors"])

    def test_empty_json(self):
        resp = _upload_json_string("")
        body = resp.json()
        assert body["success"] is False
        assert any("empty" in e["message"].lower() for e in body["errors"])

    def test_empty_json_array(self):
        resp = _upload_json([])
        body = resp.json()
        assert body["success"] is False
        assert any("empty" in e["message"].lower() for e in body["errors"])


# =========================================================================
# 6. Invalid / malformed files
# =========================================================================

class TestMalformedFiles:
    def test_invalid_json(self):
        resp = _upload_json_string("{not valid json!!!")
        body = resp.json()
        assert body["success"] is False
        assert any("malformed" in e["message"].lower() or "json" in e["message"].lower() for e in body["errors"])

    def test_unsupported_file_type(self):
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("data.xml", io.BytesIO(b"<root/>"), "application/xml")},
        )
        assert resp.status_code == 400

    def test_json_not_array(self):
        resp = _upload_json_string('{"team_id": "T1"}')
        body = resp.json()
        assert body["success"] is False
        assert any("array" in e["message"].lower() for e in body["errors"])


# =========================================================================
# 7. Missing required columns (CSV)
# =========================================================================

class TestMissingRequiredColumns:
    def test_missing_team_name_column(self):
        csv = "member_id,name\nM1,Alice\n"
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is False
        assert any("team_name" in e["message"] for e in body["errors"])

    def test_missing_name_column(self):
        csv = "team_id,team_name,member_id\nT1,Alpha,M1\n"
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is False
        assert any("name" in e["message"] for e in body["errors"])


# =========================================================================
# 8. Duplicate member IDs
# =========================================================================

class TestDuplicateMemberIds:
    def test_csv_duplicate_member_id(self):
        csv = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "T1,Alpha,M1,Alice,alice@example.com,,,,\n"
            "T1,Alpha,M1,Bob,bob@example.com,,,,\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is False
        assert any("duplicate" in e["message"].lower() for e in body["errors"])

    def test_json_duplicate_member_id(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [
                    {"member_id": "M1", "name": "Alice"},
                    {"member_id": "M1", "name": "Bob"},
                ],
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is False
        assert any("duplicate" in e["message"].lower() for e in body["errors"])


# =========================================================================
# 9. Inconsistent team names
# =========================================================================

class TestInconsistentTeamNames:
    def test_csv_inconsistent_team_name(self):
        csv = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "T1,Alpha,M1,Alice,alice@example.com,,,,\n"
            "T1,Beta,M2,Bob,bob@example.com,,,,\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is False
        assert any("inconsistent" in e["message"].lower() for e in body["errors"])


# =========================================================================
# 10. Invalid field values
# =========================================================================

class TestInvalidFieldValues:
    def test_csv_empty_member_id_generates_id(self):
        csv = (
            "team_id,team_name,member_id,name\n"
            "T1,Alpha,,Alice\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is True
        assert body["teams"][0]["members"][0]["member_id"] == "T1_m1"

    def test_csv_empty_name(self):
        csv = (
            "team_id,team_name,member_id,name\n"
            "T1,Alpha,M1,\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is False
        assert any("name" in e["message"].lower() for e in body["errors"])

    def test_json_missing_required_member_field(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [{"member_id": "M1"}],  # missing 'name'
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is False
        assert len(body["errors"]) > 0

    def test_json_empty_members_array(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [],
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is False
        assert len(body["errors"]) > 0

    def test_json_invalid_email(self):
        data = [
            {
                "team_id": "T1",
                "team_name": "Alpha",
                "members": [
                    {"member_id": "M1", "name": "Alice", "email": "not-an-email"},
                ],
            }
        ]
        resp = _upload_json(data)
        body = resp.json()
        assert body["success"] is False
        assert any("email" in e["message"].lower() for e in body["errors"])


# =========================================================================
# 11. Whitespace trimming
# =========================================================================

class TestWhitespaceTrimming:
    def test_csv_whitespace_trimmed(self):
        csv = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "  T1 , Alpha , M1 , Alice , alice@example.com,,,,\n"
        )
        resp = _upload_csv(csv)
        body = resp.json()
        assert body["success"] is True
        team = body["teams"][0]
        assert team["team_id"] == "T1"
        assert team["team_name"] == "Alpha"
        assert team["members"][0]["member_id"] == "M1"
        assert team["members"][0]["name"] == "Alice"


# =========================================================================
# 12. File extension fallback
# =========================================================================

class TestFileExtensionFallback:
    def test_csv_by_extension_when_mime_unknown(self):
        csv_content = (
            "team_id,team_name,member_id,name\n"
            "T1,Alpha,M1,Alice\n"
        )
        resp = client.post(
            UPLOAD_URL,
            files={"file": ("data.csv", io.BytesIO(csv_content.encode()), "application/octet-stream")},
        )
        body = resp.json()
        assert body["success"] is True
        assert body["teams_count"] == 1
