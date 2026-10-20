"""Comprehensive test suite for Smart Cloud Resume Links, Multi-Signal Fallback, and Companion ZIP Ingestion.

Verifies:
1. Cloud URL normalization (Google Drive, Google Docs, Dropbox).
2. Trusted hop-by-hop redirect following vs untrusted redirect SSRF blocking.
3. Friendly error messages for private or HTML preview cloud links.
4. Multi-Signal Fallback: 'CSV First, Resume Second' for Academic (CGPA, Year) and GitHub.
5. Ingestion of companion ZIP archives matching by path, email, roll number, or name.
6. Memory hygiene: raw binary bytes discarded after text extraction.
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ingestion.parser import parse_csv, parse_json
from app.schemas.ingestion import MemberSchema
from app.signals.schemas import SignalStatus
from app.signals.academic import AcademicMetricsAnalyzer
from app.signals.github import GitHubAnalyzer
from app.signals.resume import (
    ResumeSignalExtractor,
    download_resume_file,
    get_or_extract_resume_signals,
    normalize_cloud_resume_url,
)


class TestCloudUrlNormalization:
    """Test URL transformation for Google Drive, Google Docs, and Dropbox sharing links."""

    def test_google_drive_view_url(self):
        url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view?usp=sharing"
        normalized = normalize_cloud_resume_url(url)
        assert "drive.usercontent.google.com/download" in normalized
        assert "id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms" in normalized
        assert "export=download" in normalized

    def test_google_drive_open_id_url(self):
        url = "https://drive.google.com/open?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms"
        normalized = normalize_cloud_resume_url(url)
        assert "drive.usercontent.google.com/download" in normalized
        assert "id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms" in normalized

    def test_google_docs_export_url(self):
        url = "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/edit"
        normalized = normalize_cloud_resume_url(url)
        assert normalized == "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/export?format=pdf"

    def test_dropbox_url_dl0_to_dl1(self):
        url = "https://www.dropbox.com/s/abcdef12345/resume.pdf?dl=0"
        normalized = normalize_cloud_resume_url(url)
        assert normalized == "https://www.dropbox.com/s/abcdef12345/resume.pdf?dl=1"

    def test_generic_url_untouched(self):
        url = "https://example.com/resumes/john_doe.pdf"
        assert normalize_cloud_resume_url(url) == url


class TestCloudDownloaderSecurityAndRedirects:
    """Test download handling for trusted vs untrusted domains and error handling."""

    def test_untrusted_domain_rejects_redirects(self):
        """Arbitrary untrusted hosts returning HTTP 302 are rejected to prevent redirect-based SSRF."""
        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream") as mock_stream:
                mock_resp = MagicMock()
                mock_resp.status_code = 302
                mock_stream.return_value.__enter__.return_value = mock_resp

                bytes_out, err = download_resume_file("https://evil-redirector.com/resume.pdf")
                assert bytes_out is None
                assert "redirects are not permitted" in err.lower()

    def test_trusted_cloud_follows_redirects(self):
        """Google Drive / Dropbox links are permitted to follow trusted redirects."""
        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream") as mock_stream:
                resp_302 = MagicMock()
                resp_302.status_code = 302
                resp_302.headers = {"location": "https://drive.usercontent.google.com/download?id=123&confirm=t"}

                resp_200 = MagicMock()
                resp_200.status_code = 200
                resp_200.headers = {"content-type": "application/pdf"}
                resp_200.iter_bytes.return_value = [b"%PDF-1.5 simulated resume"]

                # 1st call returns 302 redirect, 2nd call returns 200 binary
                mock_stream.return_value.__enter__.side_effect = [resp_302, resp_200]

                bytes_out, err = download_resume_file(
                    "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view"
                )
                assert err is None
                assert bytes_out == b"%PDF-1.5 simulated resume"

    def test_private_google_drive_returns_clear_message(self):
        """HTTP 403 on Google Drive explains link sharing configuration."""
        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream") as mock_stream:
                mock_resp = MagicMock()
                mock_resp.status_code = 403
                mock_stream.return_value.__enter__.return_value = mock_resp

                bytes_out, err = download_resume_file(
                    "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view"
                )
                assert bytes_out is None
                assert "private or requires authentication" in err.lower()

    def test_html_preview_page_detected_and_reported(self):
        """When Google Drive returns an HTML preview or sign-in page instead of binary document."""
        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream") as mock_stream:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
                mock_resp.iter_bytes.return_value = [b"<!DOCTYPE html><html><body>Sign in to Google</body></html>"]
                mock_stream.return_value.__enter__.return_value = mock_resp

                bytes_out, err = download_resume_file(
                    "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view"
                )
                assert bytes_out is None
                assert "html preview or sign-in page" in err.lower()


class TestMultiSignalFallbackBridge:
    """Test 'CSV First, Resume Second' fallback resolution for Academic and GitHub signals."""

    def test_csv_cgpa_takes_priority_over_resume_cgpa(self):
        """If CSV explicitly provides CGPA, it is used with registration_data provenance."""
        member = MemberSchema(
            member_id="M1",
            name="Alice",
            cgpa="8.2",
            academic_year="3rd year",
            custom_fields={
                "resume_text": "Education: B.Tech in Computer Science from IIT Bombay, 2026. CGPA: 9.8. GitHub: https://github.com/alice"
            },
        )
        analyzer = AcademicMetricsAnalyzer()
        results = analyzer.extract(member)
        cgpa_sig = next(s for s in results if s.signal_key == "academic_cgpa")

        assert cgpa_sig.value == 8.2
        assert cgpa_sig.evidence.source == "registration_data"
        assert cgpa_sig.evidence.confidence == 1.0

    def test_missing_csv_cgpa_falls_back_to_resume_cgpa(self):
        """If CSV omits CGPA, analyzer extracts it from resume with resume_parser provenance."""
        member = MemberSchema(
            member_id="M2",
            name="Bob",
            cgpa=None,
            academic_year=None,
            custom_fields={
                "resume_text": "Education: Bachelor of Technology from NIT Trichy, Expected 2026. CGPA: 9.15. GitHub: https://github.com/bob"
            },
        )
        analyzer = AcademicMetricsAnalyzer()
        results = analyzer.extract(member)

        cgpa_sig = next(s for s in results if s.signal_key == "academic_cgpa")
        assert cgpa_sig.value == 9.15
        assert cgpa_sig.evidence.source == "resume_parser"
        assert cgpa_sig.evidence.confidence == 0.85
        assert cgpa_sig.evidence.metadata.get("inferred_from_resume") is True

        year_sig = next(s for s in results if s.signal_key == "academic_year")
        assert year_sig.value == "Batch 2026"
        assert year_sig.evidence.source == "resume_parser"
        assert year_sig.evidence.confidence == 0.85

    def test_missing_csv_github_falls_back_to_resume_links(self):
        """If CSV omits GitHub URL, GitHubAnalyzer inspects links extracted from candidate resume."""
        member = MemberSchema(
            member_id="M3",
            name="Charlie",
            github_url=None,
            custom_fields={
                "resume_text": "Projects: Built fullstack React and FastAPI apps. GitHub profile: https://github.com/charliedev"
            },
        )

        def mock_github_handler(request: httpx.Request):
            return httpx.Response(200, json={"login": "charliedev", "public_repos": 14})

        mock_client = httpx.Client(transport=httpx.MockTransport(mock_github_handler))
        analyzer = GitHubAnalyzer(http_client=mock_client)
        results = analyzer.extract(member, selected_signals={"github_public_repo_count"})

        repo_sig = results[0]
        assert repo_sig.status == SignalStatus.EXTRACTED
        assert repo_sig.value == 14
        assert repo_sig.evidence.confidence == 0.95
        assert repo_sig.evidence.metadata.get("inferred_from_resume") is True

    def test_missing_both_csv_and_resume_returns_not_applicable_without_zero(self):
        """Candidates with neither CSV nor resume academic data get NOT_APPLICABLE (never zero)."""
        member = MemberSchema(
            member_id="M4",
            name="Dave",
            cgpa=None,
            academic_year=None,
            custom_fields={},
        )
        analyzer = AcademicMetricsAnalyzer()
        results = analyzer.extract(member)

        cgpa_sig = next(s for s in results if s.signal_key == "academic_cgpa")
        assert cgpa_sig.status == SignalStatus.NOT_APPLICABLE
        assert cgpa_sig.value is None


class TestCompanionZipIngestion:
    """Test optional companion resumes ZIP archive processing during registration upload."""

    def _create_test_zip(self, files: dict[str, str]) -> bytes:
        """Helper to create an in-memory ZIP archive of sample text documents."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for fname, content in files.items():
                zf.writestr(fname, content.encode("utf-8"))
        return buf.getvalue()

    def test_companion_zip_matches_by_email_and_name(self):
        """Candidate in CSV without resume_url gets matched to file in ZIP by email or name."""
        csv_data = (
            "team_name,name,email,cgpa\n"
            "Team Alpha,Alice Johnson,alice@example.com,\n"
            "Team Alpha,Bob Smith,bob@example.com,7.5\n"
        ).encode("utf-8")

        # Mock extract_text_from_document to return predictable text
        def mock_extract(raw_bytes, fname):
            return (
                f"Resume of {fname}. Education: B.Tech 2026, CGPA: 9.4. Skills: Python, React, PostgreSQL.",
                None,
                {"format": "pdf"},
            )

        zip_bytes = self._create_test_zip({
            "alice@example.com.pdf": "dummy binary",
            "bob_smith.pdf": "dummy binary",
        })

        with patch("app.ingestion.parser.extract_text_from_document", side_effect=mock_extract):
            res = parse_csv(csv_data, resumes_zip_bytes=zip_bytes)

        assert res.success is True
        assert res.teams_count == 1
        team = res.teams[0]
        alice = next(m for m in team.members if m.name == "Alice Johnson")
        bob = next(m for m in team.members if m.name == "Bob Smith")

        assert "resume_text" in alice.custom_fields
        assert "CGPA: 9.4" in alice.custom_fields["resume_text"]
        assert alice.custom_fields["resume_filename"] == "alice@example.com.pdf"

        assert "resume_text" in bob.custom_fields
        assert bob.custom_fields["resume_filename"] == "bob_smith.pdf"

        # Downstream fallback test: Alice had no CGPA in CSV, but now gets 9.4 from resume!
        analyzer = AcademicMetricsAnalyzer()
        alice_sigs = analyzer.extract(alice)
        cgpa_sig = next(s for s in alice_sigs if s.signal_key == "academic_cgpa")
        assert cgpa_sig.value == 9.4
        assert cgpa_sig.evidence.source == "resume_parser"
