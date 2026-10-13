"""Regression tests for Prompt 3.2: Audit findings fixes and academic interpretations.

Verifies:
1. CSV & JSON ingestion when IDs are missing (deterministic stable ID generation, grouping, stability).
2. GitHub repository configuration (max_repos_inspected pagination, include_forks filtering).
3. GitHub recent activity sampling documentation and limitation disclosure.
4. Hardened GitHub URL validation (strict domain check, userinfo/port rejection, reserved path rejection).
5. Degree-aware academic year interpretation (3/4/5/2-year degrees, unresolved final years, conflicts, graduation batches).
"""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ingestion.parser import parse_csv, parse_json
from app.main import app
from app.schemas.ingestion import FieldPresenceStatus, MemberSchema, TeamSchema
from app.signals.academic import (
    AcademicMetricsAnalyzer,
    infer_degree_duration,
    parse_academic_year,
    resolve_degree_info,
)
from app.signals.github import (
    GitHubAnalyzer,
    extract_and_validate_github_username,
)
from app.signals.schemas import SignalStatus

client = TestClient(app)
UPLOAD_URL = "/api/ingestion/upload"
EXTRACT_URL = "/api/signals/extract"


# =========================================================================
# 1. Missing IDs CSV & JSON Ingestion Regression Tests
# =========================================================================


class TestMissingIDsIngestion:
    def test_csv_missing_both_team_id_and_member_id(self):
        """CSV without team_id and member_id succeeds, groups members, and generates stable IDs."""
        csv_data = (
            "Team Name,Participant Name,CGPA,GitHub Profile\n"
            "Code Warriors,Rahul,8.5,https://github.com/rahul1\n"
            "Code Warriors,Priya,9.0,https://github.com/priya1\n"
            "Byte Builders,Aman,8.2,\n"
        )
        mapping = {
            "Team Name": "team_name",
            "Participant Name": "name",
            "CGPA": "cgpa",
            "GitHub Profile": "github_url",
        }
        resp = parse_csv(csv_data.encode("utf-8"), mapping=mapping)
        assert resp.success is True
        assert resp.teams_count == 2
        assert resp.members_count == 3

        teams_by_name = {t.team_name: t for t in resp.teams}
        code_warriors = teams_by_name["Code Warriors"]
        byte_builders = teams_by_name["Byte Builders"]

        # Same team shares the same generated team_id
        assert code_warriors.team_id.startswith("team_code_warriors_")
        assert byte_builders.team_id.startswith("team_byte_builders_")
        assert code_warriors.team_id != byte_builders.team_id

        # Members in code_warriors have distinct member_ids
        m1, m2 = code_warriors.members[0], code_warriors.members[1]
        assert m1.name == "Rahul"
        assert m2.name == "Priya"
        assert m1.member_id == f"{code_warriors.team_id}_m1"
        assert m2.member_id == f"{code_warriors.team_id}_m2"
        assert m1.member_id != m2.member_id

        # Missing ID presence status is correctly tracked
        assert m1.field_statuses["member_id"] == FieldPresenceStatus.NOT_COLLECTED
        assert m1.field_statuses["team_id"] == FieldPresenceStatus.NOT_COLLECTED
        assert m1.field_statuses["name"] == FieldPresenceStatus.PRESENT

    def test_deterministic_id_generation_across_runs(self):
        """Repeated parsing runs on identical data produce identical generated IDs."""
        csv_data = (
            "team_name,name\n"
            "Alpha Devs,Alice\n"
            "Alpha Devs,Bob\n"
        )
        run1 = parse_csv(csv_data.encode("utf-8"))
        run2 = parse_csv(csv_data.encode("utf-8"))

        assert run1.success is True and run2.success is True
        t1 = run1.teams[0]
        t2 = run2.teams[0]
        assert t1.team_id == t2.team_id
        assert t1.members[0].member_id == t2.members[0].member_id
        assert t1.members[1].member_id == t2.members[1].member_id

    def test_duplicate_participant_names_in_same_team_receive_distinct_ids(self):
        """Two members with identical names receive unique stable member_ids."""
        csv_data = (
            "team_name,name\n"
            "Clones,Rahul\n"
            "Clones,Rahul\n"
        )
        resp = parse_csv(csv_data.encode("utf-8"))
        assert resp.success is True
        team = resp.teams[0]
        assert len(team.members) == 2
        m1, m2 = team.members[0], team.members[1]
        assert m1.name == m2.name == "Rahul"
        assert m1.member_id != m2.member_id
        assert m1.member_id.endswith("_m1")
        assert m2.member_id.endswith("_m2")

    def test_json_missing_team_id_and_member_id(self):
        """JSON payload missing team_id and member_id generates stable IDs."""
        json_data = [
            {
                "team_name": "Phoenix",
                "members": [
                    {"name": "Elena"},
                    {"name": "Marcus"},
                ],
            }
        ]
        resp = parse_json(json.dumps(json_data).encode("utf-8"))
        assert resp.success is True
        team = resp.teams[0]
        assert team.team_id.startswith("team_phoenix_")
        assert team.members[0].member_id == f"{team.team_id}_m1"
        assert team.members[1].member_id == f"{team.team_id}_m2"

    def test_supplied_ids_preserved_intact(self):
        """When valid team_id and member_id are explicitly supplied, they are kept."""
        csv_data = (
            "team_id,team_name,member_id,name\n"
            "MY_CUSTOM_TEAM_99,Custom Team,CUSTOM_MEM_1,Alice\n"
        )
        resp = parse_csv(csv_data.encode("utf-8"))
        assert resp.success is True
        team = resp.teams[0]
        assert team.team_id == "MY_CUSTOM_TEAM_99"
        assert team.members[0].member_id == "CUSTOM_MEM_1"
        assert team.members[0].field_statuses["team_id"] == FieldPresenceStatus.PRESENT
        assert team.members[0].field_statuses["member_id"] == FieldPresenceStatus.PRESENT


# =========================================================================
# 2. GitHub Repo Configuration (max_repos_inspected & include_forks)
# =========================================================================


class TestGitHubRepoConfiguration:
    def test_include_forks_false_excludes_forks_from_metadata(self):
        """Default include_forks=False excludes forks from stars/forks/languages/top repos."""
        repos_json = [
            {
                "name": "original-repo",
                "stargazers_count": 100,
                "forks_count": 20,
                "language": "Python",
                "fork": False,
            },
            {
                "name": "forked-popular-repo",
                "stargazers_count": 50000,
                "forks_count": 10000,
                "language": "JavaScript",
                "fork": True,
            },
        ]
        user_json = {"login": "dev", "public_repos": 15, "html_url": "https://github.com/dev"}

        def handler(request: httpx.Request):
            if "/repos" in str(request.url):
                return httpx.Response(200, json=repos_json)
            return httpx.Response(200, json=user_json)

        client_mock = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=client_mock)
        member = MemberSchema(member_id="M1", name="Dev", github_url="https://github.com/dev")

        # include_forks = False (default)
        res = analyzer.extract(
            member,
            selected_signals={"github_repo_metadata", "github_public_repo_count"},
            config={"include_forks": False},
        )
        sigs = {r.signal_key: r for r in res}
        meta = sigs["github_repo_metadata"].value

        # Forks excluded from stars and languages
        assert meta["total_stars"] == 100
        assert meta["total_forks"] == 20
        assert meta["primary_languages"] == ["Python"]
        assert len(meta["top_repositories"]) == 1
        assert meta["top_repositories"][0]["name"] == "original-repo"
        assert meta["include_forks"] is False
        assert meta["forks_excluded"] == 1

        # Profile public repo count retained from GitHub API
        assert sigs["github_public_repo_count"].value == 15

    def test_include_forks_true_includes_forks(self):
        """When include_forks=True, forks are included in repository-level metrics."""
        repos_json = [
            {
                "name": "original-repo",
                "stargazers_count": 100,
                "forks_count": 20,
                "language": "Python",
                "fork": False,
            },
            {
                "name": "forked-popular-repo",
                "stargazers_count": 500,
                "forks_count": 50,
                "language": "JavaScript",
                "fork": True,
            },
        ]
        user_json = {"login": "dev", "public_repos": 2, "html_url": "https://github.com/dev"}

        def handler(request: httpx.Request):
            if "/repos" in str(request.url):
                return httpx.Response(200, json=repos_json)
            return httpx.Response(200, json=user_json)

        client_mock = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=client_mock)
        member = MemberSchema(member_id="M1", name="Dev", github_url="https://github.com/dev")

        res = analyzer.extract(
            member,
            selected_signals={"github_repo_metadata"},
            config={"include_forks": True},
        )
        meta = res[0].value
        assert meta["total_stars"] == 600
        assert meta["total_forks"] == 70
        assert "JavaScript" in meta["primary_languages"]
        assert len(meta["top_repositories"]) == 2
        assert meta["include_forks"] is True
        assert meta["forks_excluded"] == 0

    def test_max_repos_inspected_paginates_when_over_100(self):
        """When max_repos_inspected > 100, extractor paginates multiple pages."""
        pages_called = []

        def handler(request: httpx.Request):
            url = str(request.url)
            if "/repos" in url:
                # Capture page query param
                page = request.url.params.get("page", "1")
                pages_called.append(page)
                # Return batch of 100 items for page 1, 50 for page 2
                batch_size = 100 if page == "1" else 50
                batch = [
                    {
                        "name": f"repo-{page}-{i}",
                        "stargazers_count": 1,
                        "forks_count": 0,
                        "language": "Python",
                        "fork": False,
                    }
                    for i in range(batch_size)
                ]
                return httpx.Response(200, json=batch)
            return httpx.Response(200, json={"login": "dev", "public_repos": 150})

        client_mock = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=client_mock)
        member = MemberSchema(member_id="M1", name="Dev", github_url="https://github.com/dev")

        res = analyzer.extract(
            member,
            selected_signals={"github_repo_metadata"},
            config={"max_repos_inspected": 150},
        )
        assert res[0].status == SignalStatus.EXTRACTED
        # Both page 1 and page 2 must have been queried
        assert "1" in pages_called
        assert "2" in pages_called
        assert res[0].evidence.metadata["repos_inspected"] == 150


# =========================================================================
# 3. GitHub Recent Activity Sampling & Limitations Disclosure
# =========================================================================


class TestGitHubActivitySamplingDisclosure:
    def test_activity_discloses_sampling_boundaries_and_private_omission(self):
        """Recent activity discloses that it is a public sample and private commits are omitted."""
        events_json = [
            {
                "type": "PushEvent",
                "created_at": "2026-10-01T12:00:00Z",
                "payload": {"commits": [{"sha": "c1"}, {"sha": "c2"}]},
            }
        ]
        user_json = {"login": "dev", "public_repos": 5}

        def handler(request: httpx.Request):
            if "/events" in str(request.url):
                return httpx.Response(200, json=events_json)
            return httpx.Response(200, json=user_json)

        client_mock = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=client_mock)
        member = MemberSchema(member_id="M1", name="Dev", github_url="https://github.com/dev")

        res = analyzer.extract(member, selected_signals={"github_recent_activity"})
        sig = res[0]
        assert sig.status == SignalStatus.EXTRACTED

        # Evidence metadata explicitly notes public-only sample
        assert sig.evidence.metadata["is_public_sample_only"] is True
        assert sig.evidence.metadata["private_activity_omitted"] is True

        # Value contains sample limitations object
        val = sig.value
        limits = val["sample_limitations"]
        assert limits["is_public_sample_only"] is True
        assert limits["private_activity_included"] is False
        assert limits["push_commit_cap_per_event"] == 20
        assert limits["max_public_events_retained_by_github"] == 300
        assert "zero public events does not imply" in limits["note"].lower()

        # Both names present for commits
        assert val["recent_commit_count"] == 2
        assert val["recent_public_push_commits"] == 2


# =========================================================================
# 4. Hardened GitHub URL Validation Regression Tests
# =========================================================================


class TestHardenedGitHubURLValidation:
    def test_rejects_spoofed_domains(self):
        """Domains containing 'github.com' but belonging to attackers are rejected."""
        spoofed = [
            "https://evil-github.com/alice",
            "https://github.com.attacker.org/alice",
            "https://notgithub.com/alice",
            "https://mygithub.company.com/alice",
        ]
        for url in spoofed:
            uname, err = extract_and_validate_github_username(url)
            assert uname is None
            assert err is not None
            assert "not a github url" in err.lower()

    def test_rejects_embedded_credentials(self):
        """URLs with user:password@ are rejected."""
        uname, err = extract_and_validate_github_username("https://user:pass@github.com/alice")
        assert uname is None
        assert "embedded credentials" in err.lower()

    def test_rejects_non_standard_ports(self):
        """URLs with non-standard ports (e.g. 8080) are rejected."""
        uname, err = extract_and_validate_github_username("https://github.com:8080/alice")
        assert uname is None
        assert "non-standard port" in err.lower()

    def test_rejects_reserved_system_paths(self):
        """Reserved system paths like /explore, /features, /orgs are rejected."""
        reserved = [
            "https://github.com/explore",
            "https://github.com/features",
            "https://github.com/pricing",
            "https://github.com/orgs",
            "https://github.com/marketplace",
            "explore",
        ]
        for item in reserved:
            uname, err = extract_and_validate_github_username(item)
            assert uname is None
            assert "reserved github" in err.lower()

    def test_accepts_valid_variations(self):
        """Valid variations (uppercase host, www, leading @, raw username) are accepted."""
        valid_cases = [
            ("https://GITHUB.COM/alice", "alice"),
            ("https://www.github.com/alice", "alice"),
            ("github.com/alice", "alice"),
            ("@alice", "alice"),
            ("alice", "alice"),
        ]
        for raw, expected in valid_cases:
            uname, err = extract_and_validate_github_username(raw)
            assert uname == expected
            assert err is None


# =========================================================================
# 5. Degree-Aware Academic Year Interpretation Regression Tests
# =========================================================================


class TestDegreeAwareAcademicYear:
    def setup_method(self):
        self.analyzer = AcademicMetricsAnalyzer()

    def test_3_year_degree_final_year_resolves_to_3rd_year(self):
        """3-year degree (BCA, B.Sc) 'Final Year' resolves to Year 3."""
        member = MemberSchema(
            member_id="M1",
            name="Rahul",
            academic_year="Final Year",
            custom_fields={"degree": "BCA"},
        )
        res = self.analyzer.extract(member, selected_signals={"academic_year"})
        assert res[0].status == SignalStatus.EXTRACTED
        assert res[0].value == "3rd Year"
        assert res[0].evidence.metadata["year_number"] == 3
        assert res[0].evidence.metadata["degree_duration"] == 3

    def test_4_year_degree_final_year_resolves_to_4th_year(self):
        """4-year degree (B.Tech, B.E) 'Final Year' resolves to Year 4."""
        member = MemberSchema(
            member_id="M1",
            name="Priya",
            academic_year="Final Year",
            custom_fields={"degree": "B.Tech"},
        )
        res = self.analyzer.extract(member, selected_signals={"academic_year"})
        assert res[0].status == SignalStatus.EXTRACTED
        assert res[0].value == "4th Year"
        assert res[0].evidence.metadata["year_number"] == 4
        assert res[0].evidence.metadata["degree_duration"] == 4

    def test_5_year_degree_final_year_resolves_to_5th_year(self):
        """5-year degree (Dual Degree, B.Arch) 'Final Year' resolves to Year 5."""
        member = MemberSchema(
            member_id="M1",
            name="Aman",
            academic_year="Final Year",
            custom_fields={"degree": "Dual Degree"},
        )
        res = self.analyzer.extract(member, selected_signals={"academic_year"})
        assert res[0].status == SignalStatus.EXTRACTED
        assert res[0].value == "5th Year"
        assert res[0].evidence.metadata["year_number"] == 5

    def test_2_year_degree_final_year_resolves_to_2nd_year(self):
        """2-year degree (MCA, M.Tech) 'Final Year' resolves to Year 2."""
        member = MemberSchema(
            member_id="M1",
            name="Ananya",
            academic_year="Final Year",
            custom_fields={"degree": "MCA"},
        )
        res = self.analyzer.extract(member, selected_signals={"academic_year"})
        assert res[0].status == SignalStatus.EXTRACTED
        assert res[0].value == "2nd Year"
        assert res[0].evidence.metadata["year_number"] == 2

    def test_unknown_degree_preserves_final_year_without_assuming_numeric_year(self):
        """When degree duration is unknown, 'Final Year' is preserved with year_number=None."""
        member = MemberSchema(
            member_id="M1",
            name="Alex",
            academic_year="Final Year",
        )
        res = self.analyzer.extract(member, selected_signals={"academic_year"})
        assert res[0].status == SignalStatus.EXTRACTED
        assert res[0].value == "Final Year"
        assert res[0].evidence.metadata["year_number"] is None
        assert res[0].evidence.metadata["is_resolved"] is False

    def test_degree_aware_pre_final_year(self):
        """Pre-final year resolves relative to degree duration."""
        # 4-year degree -> 3rd year
        m4 = MemberSchema(member_id="M1", name="Dev", academic_year="Pre-final Year", custom_fields={"degree": "B.Tech"})
        r4 = self.analyzer.extract(m4, selected_signals={"academic_year"})
        assert r4[0].value == "3rd Year"
        assert r4[0].evidence.metadata["year_number"] == 3

        # 3-year degree -> 2nd year
        m3 = MemberSchema(member_id="M2", name="Dev", academic_year="Pre-final Year", custom_fields={"degree": "B.Sc"})
        r3 = self.analyzer.extract(m3, selected_signals={"academic_year"})
        assert r3[0].value == "2nd Year"
        assert r3[0].evidence.metadata["year_number"] == 2

    def test_explicit_duration_override_in_config(self):
        """Explicit duration in config overrides degree standard mapping."""
        member = MemberSchema(
            member_id="M1",
            name="Dev",
            academic_year="Final Year",
            custom_fields={"degree": "B.Tech"},
        )
        # B.Tech normally 4, override to 5 (e.g. 5-year integrated program)
        res = self.analyzer.extract(
            member,
            selected_signals={"academic_year"},
            config={"degree_duration": 5},
        )
        assert res[0].value == "5th Year"
        assert res[0].evidence.metadata["year_number"] == 5

    def test_conflicting_academic_info_fails_with_clear_error(self):
        """Year of study exceeding degree duration is flagged as conflict."""
        member = MemberSchema(
            member_id="M1",
            name="Dev",
            academic_year="5th Year",
            custom_fields={"degree": "BCA"},  # BCA is 3 years
        )
        res = self.analyzer.extract(member, selected_signals={"academic_year"})
        assert res[0].status == SignalStatus.FAILED
        assert res[0].value is None
        assert "conflicting academic data" in res[0].error_message.lower()
        assert res[0].evidence.metadata["conflict"] is True
