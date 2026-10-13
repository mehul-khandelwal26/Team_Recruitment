"""Automated test suite for extensible signal extraction framework.

Covers:
1. Registry registration and discovery.
2. Listing available categories and individual signals.
3. Selecting individual signals.
4. Successful academic extraction.
5. Missing and invalid academic values.
6. Academic fields with custom source-column mappings.
7. CPI/CGPA scale handling.
8. GitHub API responses using mocked HTTP responses.
9. Invalid GitHub inputs, missing profiles, API errors, and rate limits.
10. Multiple members and multiple teams.
11. One failed extraction alongside successful unrelated extractions.
12. Unsupported or unregistered signals.
13. Preservation of existing ingestion and dynamic form behavior.
14. Prevention of accidental zero values for missing data.
"""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ingestion import MemberSchema, TeamSchema
from app.signals.academic import (
    AcademicMetricsAnalyzer,
    parse_academic_score,
    parse_academic_year,
)
from app.signals.base import BaseSignalExtractor, SignalExtractorRegistry
from app.signals.github import (
    GitHubAnalyzer,
    extract_and_validate_github_username,
)
from app.signals.registry import default_signal_registry
from app.signals.schemas import (
    CategoryDefinition,
    ExtractedSignal,
    ExtractorDescriptor,
    SignalDefinition,
    SignalStatus,
)

client = TestClient(app)

CATALOG_URL = "/api/signals/catalog"
CATEGORIES_URL = "/api/signals/categories"
ANALYZERS_URL = "/api/signals/analyzers"
SIGNALS_URL = "/api/signals/signals"
EXTRACT_URL = "/api/signals/extract"
EXTRACT_FILE_URL = "/api/signals/extract-file"


# =========================================================================
# 1. Registry & Discovery Tests
# =========================================================================


class DummyTestAnalyzer(BaseSignalExtractor):
    """Custom dummy analyzer to test registration without modifying existing extractors."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="dummy_analyzer",
            name="Dummy Test Analyzer",
            description="Analyzer for testing extensibility.",
            category="custom_testing",
            required_inputs=["dummy_field"],
            produced_signals=["dummy_signal_metric"],
            signals=[
                SignalDefinition(
                    signal_key="dummy_signal_metric",
                    name="Dummy Signal Metric",
                    description="Test metric",
                    category="custom_testing",
                    value_type="integer",
                )
            ],
            is_enabled_by_default=False,
        )

    def extract(
        self,
        member: MemberSchema,
        selected_signals: set[str] | None = None,
        config: dict | None = None,
    ) -> list[ExtractedSignal]:
        return [
            ExtractedSignal(
                signal_key="dummy_signal_metric",
                category="custom_testing",
                value=42,
                status=SignalStatus.EXTRACTED,
            )
        ]


class TestRegistryAndDiscovery:
    def test_custom_analyzer_registration_and_discovery(self):
        """Registering a new analyzer does not modify core execution flow or existing analyzers."""
        custom_registry = SignalExtractorRegistry()
        custom_registry.register(GitHubAnalyzer())
        custom_registry.register(DummyTestAnalyzer())

        descriptors = custom_registry.list_descriptors()
        ids = {d.extractor_id for d in descriptors}
        assert "github_analyzer" in ids
        assert "dummy_analyzer" in ids

        # Check category auto-creation
        cats = {c.category_id for c in custom_registry.list_categories()}
        assert "technical" in cats
        assert "custom_testing" in cats

        # Check signal discovery
        signals = {s.signal_key: s for s in custom_registry.list_signals()}
        assert "dummy_signal_metric" in signals
        assert signals["dummy_signal_metric"].category == "custom_testing"

    def test_listing_available_categories_and_signals(self):
        """Default registry provides technical, academic, experience, and portfolio categories."""
        catalog = default_signal_registry.get_catalog()
        cat_ids = {c.category_id for c in catalog.categories}
        assert "technical" in cat_ids
        assert "academic" in cat_ids

        sig_keys = {s.signal_key for s in catalog.signals}
        assert "github_public_repo_count" in sig_keys
        assert "github_repo_metadata" in sig_keys
        assert "github_recent_activity" in sig_keys
        assert "github_profile_verified" in sig_keys
        assert "academic_cgpa" in sig_keys
        assert "academic_year" in sig_keys
        assert "normalized_cgpa_10_scale" in sig_keys

    def test_api_endpoints_for_catalog_and_discovery(self):
        """API endpoints return structured descriptors and catalog."""
        resp = client.get(CATALOG_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert "categories" in body
        assert "analyzers" in body
        assert "signals" in body

        # Specific endpoints
        resp_cats = client.get(CATEGORIES_URL)
        assert resp_cats.status_code == 200
        assert any(c["category_id"] == "technical" for c in resp_cats.json())

        resp_analyzers = client.get(ANALYZERS_URL)
        assert resp_analyzers.status_code == 200
        assert any(a["extractor_id"] == "github_analyzer" for a in resp_analyzers.json())

        resp_signals = client.get(SIGNALS_URL)
        assert resp_signals.status_code == 200
        assert any(s["signal_key"] == "academic_cgpa" for s in resp_signals.json())


# =========================================================================
# 2. Selective Signal Extraction Tests
# =========================================================================


class TestSelectiveSignalExtraction:
    def test_selecting_single_signal_executes_only_that_signal(self):
        """Selecting only github_public_repo_count runs ONLY that signal."""
        mock_response = httpx.Response(
            200,
            json={"public_repos": 17, "html_url": "https://github.com/alice"},
            request=httpx.Request("GET", "https://api.github.com/users/alice"),
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        analyzer = GitHubAnalyzer(http_client=mock_client)
        member = MemberSchema(member_id="M1", name="Alice", github_url="alice")

        # Select ONLY github_public_repo_count
        results = analyzer.extract(member, selected_signals={"github_public_repo_count"})
        assert len(results) == 1
        assert results[0].signal_key == "github_public_repo_count"
        assert results[0].value == 17
        assert results[0].status == SignalStatus.EXTRACTED

        # Crucial: verify repos endpoint and events endpoint were NOT called
        assert mock_client.get.call_count == 1
        assert "repos" not in str(mock_client.get.call_args)
        assert "events" not in str(mock_client.get.call_args)

    def test_unsupported_or_unregistered_signals_handling(self):
        """Unsupported signals are cleanly flagged without breaking valid signals."""
        team = TeamSchema(
            team_id="T1",
            team_name="Devs",
            members=[MemberSchema(member_id="M1", name="Alice", cgpa="9.2")],
        )
        run_resp = default_signal_registry.execute_extraction(
            teams=[team],
            selected_signals=["academic_cgpa", "nonexistent_alien_signal"],
        )
        assert run_resp.total_teams == 1
        member_res = run_resp.teams[0].member_results[0]

        sigs = {s.signal_key: s for s in member_res.signals}
        assert sigs["academic_cgpa"].status == SignalStatus.EXTRACTED
        assert sigs["academic_cgpa"].value == 9.2

        assert sigs["nonexistent_alien_signal"].status == SignalStatus.FAILED
        assert "not supported" in sigs["nonexistent_alien_signal"].error_message.lower()
        assert any("unsupported" in w.lower() for w in run_resp.warnings)


# =========================================================================
# 3. Academic Analyzer Tests
# =========================================================================


class TestAcademicAnalyzer:
    def setup_method(self):
        self.analyzer = AcademicMetricsAnalyzer()

    def test_academic_cgpa_successful_extraction(self):
        """Standard CGPA formats parse and normalize properly."""
        cases = [
            ("9.4", 9.4, 10.0),
            ("8.5/10", 8.5, 10.0),
            ("3.8/4.0", 3.8, 4.0),
            ("CPI: 8.7", 8.7, 10.0),
            ("87.5%", 87.5, 100.0),
        ]
        for raw, expected_score, expected_scale in cases:
            member = MemberSchema(member_id="M1", name="Alice", cgpa=raw)
            results = self.analyzer.extract(member, selected_signals={"academic_cgpa"})
            assert len(results) == 1
            res = results[0]
            assert res.status == SignalStatus.EXTRACTED
            assert res.value == expected_score
            assert res.evidence is not None
            assert res.evidence.source == "registration_data"
            assert res.evidence.metadata["raw_value"] == raw
            assert res.evidence.metadata["scale"] == expected_scale

    def test_academic_year_successful_extraction(self):
        """Academic year patterns normalize to canonical labels."""
        cases = [
            ("3rd Year", "3rd Year", 3),
            ("3", "3rd Year", 3),
            ("Junior", "3rd Year", 3),
            ("1st", "1st Year", 1),
            ("final year", "Final Year", None),  # Unknown degree -> preserved without assuming 4th year
            ("Masters", "Postgraduate", None),
        ]
        for raw, expected_label, expected_num in cases:
            member = MemberSchema(member_id="M1", name="Alice", academic_year=raw)
            results = self.analyzer.extract(member, selected_signals={"academic_year"})
            assert len(results) == 1
            res = results[0]
            assert res.status == SignalStatus.EXTRACTED
            assert res.value == expected_label
            assert res.evidence.metadata["year_number"] == expected_num

        # Batch years are preserved without setting year_number to 2025/2026
        for raw_batch, grad_yr in [("Batch 2026", 2026), ("2025", 2025)]:
            member = MemberSchema(member_id="M1", name="Alice", academic_year=raw_batch)
            results = self.analyzer.extract(member, selected_signals={"academic_year"})
            assert len(results) == 1
            res = results[0]
            assert res.status == SignalStatus.EXTRACTED
            assert res.value == f"Batch {grad_yr}"
            assert res.evidence.metadata["year_number"] is None
            assert res.evidence.metadata["graduation_year"] == grad_yr

    def test_missing_academic_values_produce_not_applicable(self):
        """Missing academic records result in NOT_APPLICABLE, NEVER 0."""
        member = MemberSchema(member_id="M1", name="Alice", cgpa=None, academic_year=None)
        results = self.analyzer.extract(
            member, selected_signals={"academic_cgpa", "academic_year", "normalized_cgpa_10_scale"}
        )
        for res in results:
            assert res.status == SignalStatus.NOT_APPLICABLE
            assert res.value is None
            assert res.value != 0  # CRITICAL: Missing data must never silently become 0

    def test_invalid_academic_values(self):
        """Negative, non-numeric, or out-of-scale academic scores fail gracefully."""
        # Negative score
        m_neg = MemberSchema(member_id="M1", name="Alice", cgpa="-2.5")
        res_neg = self.analyzer.extract(m_neg, selected_signals={"academic_cgpa"})[0]
        assert res_neg.status == SignalStatus.FAILED
        assert "cannot be negative" in res_neg.error_message.lower()

        # Non-numeric
        m_txt = MemberSchema(member_id="M2", name="Bob", cgpa="Grade A")
        res_txt = self.analyzer.extract(m_txt, selected_signals={"academic_cgpa"})[0]
        assert res_txt.status == SignalStatus.FAILED
        assert "unable to parse numeric" in res_txt.error_message.lower()

        # Out-of-scale on 10-point scale
        m_out = MemberSchema(member_id="M3", name="Charlie", cgpa="12.5")
        res_out = self.analyzer.extract(m_out, selected_signals={"academic_cgpa"})[0]
        assert res_out.status == SignalStatus.FAILED
        assert "exceeds maximum scale" in res_out.error_message.lower()

        # Invalid academic year
        m_yr = MemberSchema(member_id="M4", name="David", academic_year="15th Year")
        res_yr = self.analyzer.extract(m_yr, selected_signals={"academic_year"})[0]
        assert res_yr.status == SignalStatus.FAILED
        assert "unrecognized academic year" in res_yr.error_message.lower()

    def test_academic_custom_column_mappings(self):
        """Analyzer reads from custom source columns specified in config."""
        member = MemberSchema(
            member_id="M1",
            name="Alice",
            custom_fields={"Student CPI Score": "8.9", "College Batch": "2027"},
        )
        results = self.analyzer.extract(
            member,
            selected_signals={"academic_cgpa", "academic_year"},
            config={
                "cgpa_field": "Student CPI Score",
                "academic_year_field": "College Batch",
            },
        )
        sigs = {r.signal_key: r for r in results}
        assert sigs["academic_cgpa"].status == SignalStatus.EXTRACTED
        assert sigs["academic_cgpa"].value == 8.9
        assert sigs["academic_cgpa"].evidence.metadata["source_field"] == "Student CPI Score"

        assert sigs["academic_year"].status == SignalStatus.EXTRACTED
        assert sigs["academic_year"].value == "Batch 2027"
        assert sigs["academic_year"].evidence.metadata["source_field"] == "College Batch"

    def test_cpi_cgpa_scale_handling_and_conversion_rules(self):
        """CPI/CGPA on 4-point scale does not convert to 10-point scale without explicit flag."""
        member_4_scale = MemberSchema(member_id="M1", name="Alice", cgpa="3.6/4.0")

        # Without allow_scale_conversion: must FAIL
        res_no_conv = self.analyzer.extract(
            member_4_scale,
            selected_signals={"normalized_cgpa_10_scale"},
            config={},
        )[0]
        assert res_no_conv.status == SignalStatus.FAILED
        assert "conversion to 10-point scale requires explicit configuration" in res_no_conv.error_message.lower()

        # With explicit allow_scale_conversion: converts accurately (3.6 / 4.0 * 10 = 9.0)
        res_conv = self.analyzer.extract(
            member_4_scale,
            selected_signals={"normalized_cgpa_10_scale"},
            config={"allow_scale_conversion": True},
        )[0]
        assert res_conv.status == SignalStatus.EXTRACTED
        assert res_conv.value == 9.0
        assert res_conv.evidence.metadata["normalized_score"] == 9.0


# =========================================================================
# 4. GitHub Analyzer Tests (Mocked API Responses)
# =========================================================================


class TestGitHubAnalyzer:
    def test_github_username_normalization(self):
        """Varied URL and username formats resolve cleanly to canonical usernames."""
        valid_inputs = [
            ("https://github.com/octocat", "octocat"),
            ("http://github.com/octocat/", "octocat"),
            ("https://www.github.com/octocat", "octocat"),
            ("github.com/octocat", "octocat"),
            ("@octocat", "octocat"),
            ("octocat", "octocat"),
            ("https://github.com/octocat?tab=repositories", "octocat"),
            ("https://github.com/torvalds/linux", "torvalds"),
        ]
        for raw, expected in valid_inputs:
            uname, err = extract_and_validate_github_username(raw)
            assert err is None
            assert uname == expected

    def test_github_invalid_inputs(self):
        """Non-GitHub URLs or invalid username characters return descriptive errors."""
        invalid_inputs = [
            ("https://linkedin.com/in/octocat", "not a github url"),
            ("https://github.com/", "does not contain a profile username"),
            ("octo!cat", "not a valid github username"),
            ("-octocat", "not a valid github username"),
        ]
        for raw, err_snippet in invalid_inputs:
            uname, err = extract_and_validate_github_username(raw)
            assert uname is None
            assert err is not None
            assert err_snippet in err.lower()

    def test_github_missing_input_produces_not_applicable(self):
        """Missing GitHub URL returns NOT_APPLICABLE, never zero."""
        analyzer = GitHubAnalyzer()
        member = MemberSchema(member_id="M1", name="Alice", github_url=None)
        results = analyzer.extract(member, selected_signals={"github_public_repo_count"})
        assert len(results) == 1
        assert results[0].status == SignalStatus.NOT_APPLICABLE
        assert results[0].value is None
        assert results[0].value != 0

    def test_github_successful_extraction_with_mocked_api(self):
        """Mocked GitHub API returns repo count, repo metadata, and activity."""
        user_json = {
            "login": "octocat",
            "name": "The Octocat",
            "public_repos": 8,
            "html_url": "https://github.com/octocat",
            "created_at": "2011-01-25T18:44:36Z",
        }
        repos_json = [
            {
                "name": "Hello-World",
                "stargazers_count": 2500,
                "forks_count": 1200,
                "language": "Ruby",
                "html_url": "https://github.com/octocat/Hello-World",
                "updated_at": "2026-09-01T12:00:00Z",
                "fork": False,
            },
            {
                "name": "Spoon-Knife",
                "stargazers_count": 11000,
                "forks_count": 3000,
                "language": "HTML",
                "html_url": "https://github.com/octocat/Spoon-Knife",
                "updated_at": "2026-10-01T12:00:00Z",
                "fork": False,
            },
        ]
        events_json = [
            {
                "type": "PushEvent",
                "created_at": "2026-10-05T10:00:00Z",
                "payload": {"commits": [{"sha": "123"}, {"sha": "456"}]},
            },
            {
                "type": "WatchEvent",
                "created_at": "2026-10-04T08:00:00Z",
                "payload": {},
            },
        ]

        def handler(request: httpx.Request):
            url_str = str(request.url)
            if url_str.endswith("/repos") or "/repos?" in url_str:
                return httpx.Response(200, json=repos_json)
            if url_str.endswith("/events/public") or "/events/public?" in url_str:
                return httpx.Response(200, json=events_json)
            if "/users/octocat" in url_str:
                return httpx.Response(200, json=user_json)
            return httpx.Response(404, json={"message": "Not Found"})

        transport = httpx.MockTransport(handler)
        mock_client = httpx.Client(transport=transport)
        analyzer = GitHubAnalyzer(http_client=mock_client)

        member = MemberSchema(member_id="M1", name="Octocat", github_url="https://github.com/octocat")
        results = analyzer.extract(
            member,
            selected_signals={
                "github_profile_verified",
                "github_public_repo_count",
                "github_repo_metadata",
                "github_recent_activity",
            },
        )
        sigs = {r.signal_key: r for r in results}

        # 1. Profile verified
        assert sigs["github_profile_verified"].status == SignalStatus.EXTRACTED
        assert sigs["github_profile_verified"].value is True

        # 2. Public repo count
        assert sigs["github_public_repo_count"].status == SignalStatus.EXTRACTED
        assert sigs["github_public_repo_count"].value == 8

        # 3. Repo metadata
        assert sigs["github_repo_metadata"].status == SignalStatus.EXTRACTED
        meta_val = sigs["github_repo_metadata"].value
        assert meta_val["total_stars"] == 13500
        assert meta_val["total_forks"] == 4200
        assert "Ruby" in meta_val["primary_languages"]
        assert len(meta_val["top_repositories"]) == 2

        # 4. Recent activity
        assert sigs["github_recent_activity"].status == SignalStatus.EXTRACTED
        act_val = sigs["github_recent_activity"].value
        assert act_val["recent_events_count"] == 2
        assert act_val["push_events_count"] == 1
        assert act_val["recent_commit_count"] == 2
        assert act_val["has_recent_activity"] is True

    def test_github_api_404_not_found(self):
        """Inaccessible or non-existent profile returns FAILED with 404 message."""
        def handler(request: httpx.Request):
            return httpx.Response(404, json={"message": "Not Found"})

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=mock_client)

        member = MemberSchema(member_id="M1", name="Ghost", github_url="ghost-user-999999")
        results = analyzer.extract(member, selected_signals={"github_public_repo_count"})
        assert results[0].status == SignalStatus.FAILED
        assert "not found (http 404)" in results[0].error_message.lower()

    def test_github_api_rate_limit_exceeded(self):
        """Rate limited response (403 or 429) returns FAILED with rate limit warning."""
        def handler(request: httpx.Request):
            return httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0"},
                json={"message": "API rate limit exceeded for IP."},
            )

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=mock_client)

        member = MemberSchema(member_id="M1", name="Alice", github_url="alice")
        results = analyzer.extract(member, selected_signals={"github_public_repo_count"})
        assert results[0].status == SignalStatus.FAILED
        assert "rate limit exceeded" in results[0].error_message.lower()

    def test_github_api_timeout(self):
        """Network timeout during API call returns FAILED without crashing."""
        def handler(request: httpx.Request):
            raise httpx.TimeoutException("Connection timed out")

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        analyzer = GitHubAnalyzer(http_client=mock_client)

        member = MemberSchema(member_id="M1", name="Alice", github_url="alice")
        results = analyzer.extract(member, selected_signals={"github_public_repo_count"})
        assert results[0].status == SignalStatus.FAILED
        assert "timed out" in results[0].error_message.lower()


# =========================================================================
# 5. Multi-Team, Multi-Member & Fault Isolation Tests
# =========================================================================


class TestMultiTeamMultiMemberExtraction:
    def test_multiple_teams_and_multiple_members_hierarchy(self):
        """Extracts signals across multiple teams with multiple members preserving hierarchy."""
        team1 = TeamSchema(
            team_id="T1",
            team_name="Team Alpha",
            members=[
                MemberSchema(member_id="M1", name="Alice", cgpa="9.1", academic_year="3rd Year"),
                MemberSchema(member_id="M2", name="Bob", cgpa="8.5", academic_year="2nd Year"),
            ],
        )
        team2 = TeamSchema(
            team_id="T2",
            team_name="Team Beta",
            members=[
                MemberSchema(member_id="M3", name="Charlie", cgpa="7.9", academic_year="4th Year"),
            ],
        )

        run_resp = default_signal_registry.execute_extraction(
            teams=[team1, team2],
            selected_signals=["academic_cgpa", "academic_year"],
        )

        assert run_resp.total_teams == 2
        assert run_resp.total_members == 3
        assert len(run_resp.teams) == 2

        # Team Alpha
        t1 = run_resp.teams[0]
        assert t1.team_id == "T1"
        assert len(t1.member_results) == 2
        assert t1.member_results[0].member_id == "M1"
        assert t1.member_results[0].signals[0].value == 9.1
        assert t1.member_results[1].member_id == "M2"
        assert t1.member_results[1].signals[0].value == 8.5

        # Team Beta
        t2 = run_resp.teams[1]
        assert t2.team_id == "T2"
        assert len(t2.member_results) == 1
        assert t2.member_results[0].member_id == "M3"
        assert t2.member_results[0].signals[0].value == 7.9

    def test_isolated_failure_does_not_abort_unrelated_extractions(self):
        """Member 1 failure (invalid academic value) does not stop Member 2 or other signals."""
        team = TeamSchema(
            team_id="T1",
            team_name="Mixed Team",
            members=[
                MemberSchema(member_id="M1", name="Alice", cgpa="-5.0", academic_year="3rd Year"),
                MemberSchema(member_id="M2", name="Bob", cgpa="9.0", academic_year="invalid_year"),
            ],
        )
        run_resp = default_signal_registry.execute_extraction(
            teams=[team],
            selected_signals=["academic_cgpa", "academic_year"],
        )
        m1_sigs = {s.signal_key: s for s in run_resp.teams[0].member_results[0].signals}
        m2_sigs = {s.signal_key: s for s in run_resp.teams[0].member_results[1].signals}

        # Member 1: CGPA failed, Academic Year succeeded
        assert m1_sigs["academic_cgpa"].status == SignalStatus.FAILED
        assert m1_sigs["academic_year"].status == SignalStatus.EXTRACTED
        assert m1_sigs["academic_year"].value == "3rd Year"

        # Member 2: CGPA succeeded, Academic Year failed
        assert m2_sigs["academic_cgpa"].status == SignalStatus.EXTRACTED
        assert m2_sigs["academic_cgpa"].value == 9.0
        assert m2_sigs["academic_year"].status == SignalStatus.FAILED

    def test_cross_analyzer_multi_member_fault_isolation(self):
        """One member's GitHub 404 does not stop other members or Academic extraction."""
        def handler(request: httpx.Request):
            url_str = str(request.url)
            if "/users/alice" in url_str:
                return httpx.Response(200, json={"public_repos": 12, "html_url": "https://github.com/alice"})
            if "/users/ghost-user" in url_str:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(404, json={})

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        custom_registry = SignalExtractorRegistry()
        custom_registry.register(GitHubAnalyzer(http_client=mock_client))
        custom_registry.register(AcademicMetricsAnalyzer())

        team = TeamSchema(
            team_id="T1",
            team_name="Mixed Analyzer Team",
            members=[
                MemberSchema(member_id="M1", name="Alice", github_url="alice", cgpa="9.4"),
                MemberSchema(member_id="M2", name="Ghost", github_url="ghost-user", cgpa="8.7"),
            ],
        )

        resp = custom_registry.execute_extraction(
            teams=[team],
            selected_signals=["github_public_repo_count", "academic_cgpa"],
        )

        m1_sigs = {s.signal_key: s for s in resp.teams[0].member_results[0].signals}
        m2_sigs = {s.signal_key: s for s in resp.teams[0].member_results[1].signals}

        # Alice: both GitHub and CGPA extracted
        assert m1_sigs["github_public_repo_count"].status == SignalStatus.EXTRACTED
        assert m1_sigs["github_public_repo_count"].value == 12
        assert m1_sigs["academic_cgpa"].status == SignalStatus.EXTRACTED
        assert m1_sigs["academic_cgpa"].value == 9.4

        # Ghost: GitHub 404 failed, but CGPA extracted successfully
        assert m2_sigs["github_public_repo_count"].status == SignalStatus.FAILED
        assert "not found (http 404)" in m2_sigs["github_public_repo_count"].error_message.lower()
        assert m2_sigs["academic_cgpa"].status == SignalStatus.EXTRACTED
        assert m2_sigs["academic_cgpa"].value == 8.7


# =========================================================================
# 6. End-to-End API Endpoint Tests
# =========================================================================


class TestSignalAPIEndpoints:
    def test_post_extract_signals_endpoint(self):
        """POST /api/signals/extract processes team payload."""
        req_data = {
            "teams": [
                {
                    "team_id": "T1",
                    "team_name": "Rocket",
                    "members": [
                        {
                            "member_id": "M1",
                            "name": "Alice",
                            "cgpa": "9.5",
                            "academic_year": "Final Year",
                        }
                    ],
                }
            ],
            "selected_signals": ["academic_cgpa", "academic_year"],
            "config": {},
        }
        resp = client.post(EXTRACT_URL, json=req_data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_teams"] == 1
        assert body["total_members"] == 1
        member_res = body["teams"][0]["member_results"][0]
        assert member_res["signals"][0]["value"] == 9.5
        assert member_res["signals"][1]["value"] == "Final Year"

    def test_post_extract_from_csv_file_endpoint(self):
        """POST /api/signals/extract-file parses CSV and extracts signals."""
        csv_data = (
            "team_id,team_name,member_id,name,Current CPI,College Year\n"
            "T1,Alpha,M1,Alice,8.8,3rd Year\n"
            "T1,Alpha,M2,Bob,9.2,2nd Year\n"
        )
        resp = client.post(
            EXTRACT_FILE_URL,
            files={"file": ("teams.csv", io.BytesIO(csv_data.encode()), "text/csv")},
            data={
                "mapping": json.dumps({"Current CPI": "cgpa", "College Year": "academic_year"}),
                "selected_signals": "academic_cgpa,academic_year",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_teams"] == 1
        assert body["total_members"] == 2
        m1 = body["teams"][0]["member_results"][0]
        assert m1["signals"][0]["value"] == 8.8
        assert m1["signals"][1]["value"] == "3rd Year"
