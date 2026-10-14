"""Tests for Resume Analyzer (Prompt 4).

Covers:
1. Valid PDF extraction.
2. Valid DOCX extraction.
3. Skill and technology extraction (languages, frameworks, databases, tools).
4. Project information extraction.
5. Education and graduation-year extraction.
6. Experience and achievement extraction.
7. External-link detection (GitHub, LinkedIn, portfolio).
8. Missing or empty resumes.
9. Unsupported file types.
10. Corrupted or unreadable documents.
11. File-size limits and URL security / SSRF protection.
12. Evidence and status correctness.
13. Individual signal selection.
14. Multiple members and temporary Team IDs.
15. Fault isolation when one resume fails.
16. Full multi-analyzer compatibility (GitHub, Academics, and Resume together).
17. Direct file upload via POST /api/signals/extract-resume.
"""

from __future__ import annotations

import datetime
import io
from typing import Any
from unittest.mock import MagicMock, patch

import docx
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ingestion import MemberSchema, TeamSchema
from app.signals.github import GitHubAnalyzer
from app.signals.registry import default_signal_registry
from app.signals.resume import (
    ResumeSignalExtractor,
    download_resume_file,
    extract_certifications_achievements_from_text,
    extract_education_from_text,
    extract_experience_from_text,
    extract_external_links_from_text,
    extract_skills_from_text,
    extract_text_from_document,
    validate_url_security,
)
from app.signals.schemas import SignalStatus

client = TestClient(app)
EXTRACT_RESUME_URL = "/api/signals/extract-resume"
EXTRACT_URL = "/api/signals/extract"
CATALOG_URL = "/api/signals/catalog"


# =========================================================================
# Test Fixtures & Document Generators
# =========================================================================


def make_test_pdf_bytes(lines: list[str]) -> bytes:
    """Generate a valid in-memory 1-page PDF containing the provided lines."""
    ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for idx, l in enumerate(lines):
        safe_l = (
            l.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        if idx == 0:
            ops.append(f"({safe_l}) Tj")
        else:
            ops.append(f"T* ({safe_l}) Tj")
    ops.append("ET")
    stream_content = "\n".join(ops).encode("latin-1", errors="replace")
    stream_len = len(stream_content)

    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length " + str(stream_len).encode("ascii") + b" >>\n"
        b"stream\n" + stream_content + b"\nendstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n0\n%%EOF"
    )
    return pdf_bytes


def make_test_docx_bytes(paragraphs: list[str]) -> bytes:
    """Generate a valid in-memory DOCX document containing the provided paragraphs."""
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


STANDARD_RESUME_LINES = [
    "Rahul Sharma",
    "Email: rahul@example.com | Phone: +91 9876543210",
    "GitHub: https://github.com/rahulsharma | LinkedIn: https://linkedin.com/in/rahulsharma",
    "Portfolio: https://rahulsharma.dev",
    "",
    "EDUCATION",
    "Bachelor of Technology in Computer Science and Engineering",
    "National Institute of Technology, Graduating May 2025 (CGPA: 8.8/10)",
    "",
    "TECHNICAL SKILLS",
    "Languages: Python, Go, TypeScript, C++, SQL",
    "Frameworks & Libraries: FastAPI, React, Next.js, Django, PyTorch",
    "Databases: PostgreSQL, Redis, MongoDB",
    "DevOps & Tools: Docker, Kubernetes, Git, AWS, Linux",
    "",
    "EXPERIENCE",
    "Software Engineer Intern | Acme Cloud Inc | May 2024 - Aug 2024",
    "- Developed high-throughput microservices using FastAPI and PostgreSQL.",
    "- Containerized services using Docker and deployed on AWS ECS.",
    "",
    "PROJECTS",
    "Distributed Key-Value Store | Go, Raft, gRPC",
    "- Implemented a replicated consensus key-value store using Raft algorithm in Go.",
    "Real-time Chat Engine | TypeScript, React, Redis",
    "- Built real-time messaging platform using WebSockets, React, and Redis Pub/Sub.",
    "",
    "ACHIEVEMENTS & CERTIFICATIONS",
    "AWS Certified Solutions Architect - Associate",
    "1st Place Winner at HackNIT 2023 Hackathon",
]


# =========================================================================
# 1. Document Extraction Tests (PDF & DOCX)
# =========================================================================


class TestDocumentParsing:
    def test_valid_pdf_extraction(self):
        """Extracts readable text from a valid PDF document."""
        pdf_bytes = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        text, err, meta = extract_text_from_document(pdf_bytes, "resume.pdf")

        assert err is None
        assert text is not None
        assert "Rahul Sharma" in text
        assert "FastAPI" in text
        assert meta["format"] == "pdf"
        assert meta["pages"] == 1

    def test_valid_docx_extraction(self):
        """Extracts readable text from a valid DOCX document."""
        docx_bytes = make_test_docx_bytes(STANDARD_RESUME_LINES)
        text, err, meta = extract_text_from_document(docx_bytes, "resume.docx")

        assert err is None
        assert text is not None
        assert "Rahul Sharma" in text
        assert "Docker" in text
        assert meta["format"] == "docx"

    def test_empty_document_bytes(self):
        """Empty byte payload returns a clear validation error."""
        text, err, meta = extract_text_from_document(b"", "resume.pdf")
        assert text is None
        assert err is not None
        assert "empty" in err.lower()

    def test_unsupported_file_type(self):
        """Unsupported format like image or zip without docx structure fails gracefully."""
        dummy_zip = b"PK\x05\x06" + b"\x00" * 18  # empty zip, no word/document.xml
        text, err, meta = extract_text_from_document(dummy_zip, "resume.zip")
        assert text is None
        assert err is not None
        assert "unsupported" in err.lower()

    def test_corrupted_pdf_document(self):
        """Corrupted PDF bytes fail gracefully without crashing."""
        corrupt_bytes = b"%PDF-1.4\nCorrupted content without xref or valid objects\n%%EOF"
        text, err, meta = extract_text_from_document(corrupt_bytes, "resume.pdf")
        assert text is None
        assert err is not None
        assert "corrupted" in err.lower() or "invalid" in err.lower()

    def test_scanned_or_empty_text_pdf(self):
        """PDF with blank or negligible text indicates OCR is not enabled."""
        blank_pdf = make_test_pdf_bytes(["   ", ""])
        text, err, meta = extract_text_from_document(blank_pdf, "scanned.pdf")
        assert text is None
        assert err is not None
        assert "no readable text" in err.lower()


# =========================================================================
# 2. Signal Extraction Logic
# =========================================================================


class TestResumeSignalExtraction:
    @pytest.fixture
    def extractor(self) -> ResumeSignalExtractor:
        return ResumeSignalExtractor()

    @pytest.fixture
    def sample_member(self) -> MemberSchema:
        pdf_bytes = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        return MemberSchema(
            member_id="M1",
            name="Rahul Sharma",
            resume_url="https://example.com/resumes/rahul.pdf",
            custom_fields={"resume_bytes": pdf_bytes},
        )

    def test_skills_and_technologies_extraction(self, extractor, sample_member):
        """Extracts programming languages, frameworks, databases, and tools."""
        signals = extractor.extract(
            sample_member,
            selected_signals={
                "resume_extracted_skills",
                "resume_programming_languages",
                "resume_frameworks_libraries",
                "resume_databases",
                "resume_tools_technologies",
            },
        )
        sig_map = {s.signal_key: s for s in signals}

        # Overall skills signal
        overall = sig_map["resume_extracted_skills"]
        assert overall.status == SignalStatus.EXTRACTED
        val = overall.value
        assert "Python" in val["languages"]
        assert "Go" in val["languages"]
        assert "TypeScript" in val["languages"]
        assert "FastAPI" in val["frameworks"]
        assert "React" in val["frameworks"]
        assert "PostgreSQL" in val["databases"]
        assert "Docker" in val["tools"]
        assert val["total_skills_count"] >= 7

        # Individual fine-grained signals
        langs = sig_map["resume_programming_languages"]
        assert langs.status == SignalStatus.EXTRACTED
        assert "Python" in langs.value

        fws = sig_map["resume_frameworks_libraries"]
        assert fws.status == SignalStatus.EXTRACTED
        assert "FastAPI" in fws.value

        dbs = sig_map["resume_databases"]
        assert dbs.status == SignalStatus.EXTRACTED
        assert "PostgreSQL" in dbs.value

        tools = sig_map["resume_tools_technologies"]
        assert tools.status == SignalStatus.EXTRACTED
        assert "Docker" in tools.value

    def test_project_information_extraction(self, extractor, sample_member):
        """Identifies project names, descriptions, associated technologies, and evidence."""
        signals = extractor.extract(
            sample_member,
            selected_signals={"resume_projects"},
        )
        proj_sig = signals[0]
        assert proj_sig.status == SignalStatus.EXTRACTED
        projects = proj_sig.value
        assert len(projects) >= 1

        p1 = projects[0]
        assert "Distributed Key-Value Store" in p1["name"]
        assert "Go" in p1["technologies"]
        assert p1["verified"] is False
        assert p1["provenance"] == "self_reported_resume"
        assert "Distributed Key-Value Store" in p1["evidence"]

    def test_education_and_graduation_year_extraction(self, extractor, sample_member):
        """Extracts degree, institution, graduation year, and GPA."""
        signals = extractor.extract(
            sample_member,
            selected_signals={"resume_education", "resume_degree_level"},
        )
        sig_map = {s.signal_key: s for s in signals}

        edu_sig = sig_map["resume_education"]
        assert edu_sig.status == SignalStatus.EXTRACTED
        edu = edu_sig.value
        assert edu["degree_short"] == "B.Tech"
        assert "National Institute of Technology" in edu["institution"]
        assert edu["graduation_year"] == 2025
        assert edu["gpa"] == "8.8/10"
        assert edu["verified"] is False

        deg_sig = sig_map["resume_degree_level"]
        assert deg_sig.status == SignalStatus.EXTRACTED
        assert deg_sig.value == "B.Tech"

    def test_experience_and_achievements_extraction(self, extractor, sample_member):
        """Extracts internships, work experience, roles, estimated years, and achievements."""
        signals = extractor.extract(
            sample_member,
            selected_signals={
                "resume_experience",
                "resume_experience_years",
                "resume_certifications_achievements",
            },
        )
        sig_map = {s.signal_key: s for s in signals}

        exp_sig = sig_map["resume_experience"]
        assert exp_sig.status == SignalStatus.EXTRACTED
        assert len(exp_sig.value) >= 1
        entry = exp_sig.value[0]
        assert "Software Engineer Intern" in entry["role"]
        assert "May 2024 - Aug 2024" in entry["duration"]

        exp_years = sig_map["resume_experience_years"]
        assert exp_years.status == SignalStatus.EXTRACTED
        assert exp_years.value >= 0.25

        achieve_sig = sig_map["resume_certifications_achievements"]
        assert achieve_sig.status == SignalStatus.EXTRACTED
        achievements = achieve_sig.value
        titles = [a["title"] for a in achievements]
        assert any("AWS Certified" in t for t in titles)
        assert any("1st Place" in t or "HackNIT" in t for t in titles)

    def test_external_links_detection(self, extractor, sample_member):
        """Extracts GitHub, LinkedIn, and portfolio URLs."""
        signals = extractor.extract(
            sample_member,
            selected_signals={"resume_external_links"},
        )
        link_sig = signals[0]
        assert link_sig.status == SignalStatus.EXTRACTED
        val = link_sig.value
        assert "https://github.com/rahulsharma" in val["github_urls"]
        assert "https://linkedin.com/in/rahulsharma" in val["linkedin_urls"]
        assert "https://rahulsharma.dev" in val["portfolio_urls"]

    def test_missing_resume_returns_not_applicable(self, extractor):
        """Member with no resume URL or document returns NOT_APPLICABLE without failing."""
        member = MemberSchema(member_id="M_NO_RESUME", name="No Resume Candidate")
        signals = extractor.extract(
            member,
            selected_signals={"resume_extracted_skills", "resume_education"},
        )
        assert len(signals) == 2
        for s in signals:
            assert s.status == SignalStatus.NOT_APPLICABLE
            assert s.value is None
            assert "Missing" in s.error_message or "not provide" in s.error_message


# =========================================================================
# 3. Security, SSRF & URL Fetching
# =========================================================================


class TestResumeSecurityAndSSRF:
    def test_ssrf_rejects_private_and_loopback_ips(self):
        """Private IP addresses (10.x, 192.168.x, 127.x) and loopback are blocked."""
        # 127.0.0.1
        safe, err = validate_url_security("http://127.0.0.1/resume.pdf")
        assert safe is False
        assert "loopback" in err.lower() or "blocked" in err.lower()

        # 10.0.0.1
        safe, err = validate_url_security("http://10.0.0.1/resume.pdf")
        assert safe is False
        assert "private" in err.lower() or "blocked" in err.lower()

        # Cloud metadata service (169.254.169.254)
        safe, err = validate_url_security("http://169.254.169.254/latest/meta-data")
        assert safe is False
        assert "metadata" in err.lower() or "link-local" in err.lower() or "blocked" in err.lower()

    def test_ssrf_rejects_credentials_in_url(self):
        """URLs containing username:password credentials are blocked."""
        safe, err = validate_url_security("http://admin:secret@example.com/resume.pdf")
        assert safe is False
        assert "credentials" in err.lower()

    def test_ssrf_rejects_non_standard_ports(self):
        """Ports like 22, 3306, 6379 are blocked."""
        safe, err = validate_url_security("http://example.com:22/resume.pdf")
        assert safe is False
        assert "port" in err.lower()

    def test_download_enforces_size_limit(self):
        """Simulated large payload exceeding max_bytes limit is aborted."""
        large_bytes = b"X" * (5000)

        # Mock stream yielding chunks exceeding max_bytes
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-length": "5000"}
        mock_resp.iter_bytes.return_value = [b"X" * 1024 for _ in range(5)]
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream", return_value=mock_resp):
                data, err = download_resume_file("https://example.com/huge.pdf", max_bytes=2048)
                assert data is None
                assert err is not None
                assert "exceeds" in err.lower() or "exceeded" in err.lower()

    def test_download_handles_network_timeout(self):
        """Network timeout during download fails safely."""
        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream", side_effect=httpx.TimeoutException("Timed out")):
                data, err = download_resume_file("https://example.com/resume.pdf", timeout=2.0)
                assert data is None
                assert err is not None
                assert "timed out" in err.lower()


# =========================================================================
# 4. Registry, API, Multi-Member & Fault Isolation Tests
# =========================================================================


class TestRegistryAndAPIFunctionality:
    def test_catalog_exposes_resume_analyzer_and_signals(self):
        """GET /api/signals/catalog exposes the Resume analyzer and its signals."""
        resp = client.get(CATALOG_URL)
        assert resp.status_code == 200
        body = resp.json()

        analyzer_ids = {a["extractor_id"] for a in body["analyzers"]}
        assert "resume_parser" in analyzer_ids

        all_signals = {s["signal_key"] for s in body["signals"]}
        assert "resume_extracted_skills" in all_signals
        assert "resume_projects" in all_signals
        assert "resume_education" in all_signals
        assert "resume_experience" in all_signals
        assert "resume_external_links" in all_signals

    def test_individual_signal_selection(self):
        """Selecting only resume_education executes only education without running other resume signals."""
        pdf_bytes = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        team = TeamSchema(
            team_id="T_SELECT",
            team_name="Selection Team",
            members=[
                MemberSchema(
                    member_id="M_SEL",
                    name="Selective Candidate",
                    resume_url="resume.pdf",
                    custom_fields={"resume_bytes": pdf_bytes},
                )
            ],
        )

        res = default_signal_registry.execute_extraction(
            teams=[team],
            selected_signals=["resume_education"],
        )
        assert res.total_teams == 1
        m_res = res.teams[0].member_results[0]
        assert len(m_res.signals) == 1
        assert m_res.signals[0].signal_key == "resume_education"
        assert m_res.signals[0].status == SignalStatus.EXTRACTED

    def test_fault_isolation_when_one_resume_fails(self):
        """When one member's resume is corrupted, other members succeed independently."""
        valid_pdf = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        corrupted_bytes = b"Corrupted invalid PDF header"

        team = TeamSchema(
            team_id="T_ISOLATION",
            team_name="Isolation Team",
            members=[
                MemberSchema(
                    member_id="M_CORRUPT",
                    name="Corrupted Member",
                    resume_url="bad.pdf",
                    custom_fields={"resume_bytes": corrupted_bytes},
                ),
                MemberSchema(
                    member_id="M_VALID",
                    name="Valid Member",
                    resume_url="good.pdf",
                    custom_fields={"resume_bytes": valid_pdf},
                ),
            ],
        )

        res = default_signal_registry.execute_extraction(
            teams=[team],
            selected_signals=["resume_extracted_skills"],
        )
        assert res.total_teams == 1
        m_corrupt_res = res.teams[0].member_results[0]
        m_valid_res = res.teams[0].member_results[1]

        # Corrupted member's signal failed
        assert m_corrupt_res.signals[0].status == SignalStatus.FAILED
        assert "corrupted" in m_corrupt_res.signals[0].error_message.lower() or "unsupported" in m_corrupt_res.signals[0].error_message.lower()

        # Valid member's signal extracted successfully
        assert m_valid_res.signals[0].status == SignalStatus.EXTRACTED
        assert "Python" in m_valid_res.signals[0].value["languages"]

    def test_temporary_team_ids_preserved_in_resume_extraction(self):
        """Downstream extraction preserves temporary unresolved Team IDs."""
        valid_pdf = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        team = TeamSchema(
            team_id="temp_team_warriors_d4b1a2_unresolved_1",
            team_name="Warriors",
            is_temporary_id=True,
            is_unresolved=True,
            duplicate_name_detected=True,
            members=[
                MemberSchema(
                    member_id="temp_team_warriors_d4b1a2_unresolved_1_m1",
                    name="Temp Member",
                    resume_url="resume.pdf",
                    custom_fields={"resume_bytes": valid_pdf},
                )
            ],
        )

        res = default_signal_registry.execute_extraction(
            teams=[team],
            selected_signals=["resume_education"],
        )
        team_res = res.teams[0]
        assert team_res.team_id == "temp_team_warriors_d4b1a2_unresolved_1"
        assert team_res.is_temporary_id is True
        assert team_res.is_unresolved is True

    def test_multi_analyzer_compatibility(self):
        """GitHub, Academic, and Resume analyzers run concurrently in the same extraction run."""
        valid_pdf = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        team = TeamSchema(
            team_id="T_MULTI",
            team_name="Multi Analyzer Team",
            members=[
                MemberSchema(
                    member_id="M_ALL",
                    name="Full Candidate",
                    cgpa="9.2",
                    academic_year="3rd Year",
                    github_url="https://github.com/rahulsharma",
                    resume_url="resume.pdf",
                    custom_fields={"resume_bytes": valid_pdf},
                )
            ],
        )

        # Mock GitHub API call so no external internet request is made
        mock_user = {
            "login": "rahulsharma",
            "name": "Rahul Sharma",
            "public_repos": 15,
            "html_url": "https://github.com/rahulsharma",
        }
        mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, json=mock_user))
        with patch.object(GitHubAnalyzer, "_get_client", return_value=httpx.Client(transport=mock_transport)):
            res = default_signal_registry.execute_extraction(
                teams=[team],
                selected_signals=[
                    "academic_cgpa",
                    "github_public_repo_count",
                    "resume_extracted_skills",
                ],
            )

        assert res.total_teams == 1
        m_sig = res.teams[0].member_results[0]
        sig_map = {s.signal_key: s for s in m_sig.signals}

        assert sig_map["academic_cgpa"].status == SignalStatus.EXTRACTED
        assert sig_map["academic_cgpa"].value == 9.2

        assert sig_map["github_public_repo_count"].status == SignalStatus.EXTRACTED
        assert sig_map["github_public_repo_count"].value == 15

        assert sig_map["resume_extracted_skills"].status == SignalStatus.EXTRACTED
        assert "Python" in sig_map["resume_extracted_skills"].value["languages"]

    def test_direct_resume_file_upload_endpoint(self):
        """POST /api/signals/extract-resume extracts signals directly from uploaded PDF."""
        pdf_bytes = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        resp = client.post(
            EXTRACT_RESUME_URL,
            files={"file": ("candidate_resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"candidate_name": "Direct Candidate", "selected_signals": "resume_extracted_skills,resume_education"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_members"] == 1
        member_res = body["teams"][0]["member_results"][0]
        assert member_res["name"] == "Direct Candidate"

        signals = {s["signal_key"]: s for s in member_res["signals"]}
        assert signals["resume_extracted_skills"]["status"] == "extracted"
        assert "Python" in signals["resume_extracted_skills"]["value"]["languages"]
        assert signals["resume_education"]["status"] == "extracted"
        assert signals["resume_education"]["value"]["degree_short"] == "B.Tech"

    def test_direct_docx_file_upload_endpoint(self):
        """POST /api/signals/extract-resume extracts signals directly from uploaded DOCX."""
        docx_bytes = make_test_docx_bytes(STANDARD_RESUME_LINES)
        resp = client.post(
            EXTRACT_RESUME_URL,
            files={"file": ("candidate_resume.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"candidate_name": "Docx Candidate"},
        )

        assert resp.status_code == 200
        body = resp.json()
        member_res = body["teams"][0]["member_results"][0]
        signals = {s["signal_key"]: s for s in member_res["signals"]}
        assert signals["resume_extracted_skills"]["status"] == "extracted"
        assert "Docker" in signals["resume_extracted_skills"]["value"]["tools"]

    def test_direct_upload_rejects_unsupported_file_extension(self):
        """POST /api/signals/extract-resume rejects non-pdf/non-docx uploads."""
        resp = client.post(
            EXTRACT_RESUME_URL,
            files={"file": ("bad_file.exe", io.BytesIO(b"executable data"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "unsupported" in resp.json()["detail"].lower()


# =========================================================================
# Prompt 3.1 Hardening Tests (Security & Accuracy Verification)
# =========================================================================


class TestResumeHardeningP31:
    """Tests for Prompt 3.1 Security & Accuracy Hardening."""

    # 1. P0.1 - Local files
    def test_local_file_access_disabled_by_default(self, tmp_path):
        """By default, allow_local_files is False; absolute and file:// paths fail without leaking existence."""
        probe_file = tmp_path / "probe.pdf"
        probe_file.write_bytes(b"%PDF-1.4 dummy")

        m_abs = MemberSchema(member_id="m1", name="Alice", resume_url=str(probe_file))
        res = ResumeSignalExtractor().extract(m_abs, {"resume_extracted_skills"}, {})
        assert res[0].status == SignalStatus.FAILED
        assert res[0].error_message == "Local file access is disabled."

        # Non-existent file also gives generic message (no existence oracle)
        m_nonexist = MemberSchema(member_id="m2", name="Bob", resume_url=str(tmp_path / "ghost.pdf"))
        res_ne = ResumeSignalExtractor().extract(m_nonexist, {"resume_extracted_skills"}, {})
        assert res_ne[0].status == SignalStatus.FAILED
        assert res_ne[0].error_message == "Local file access is disabled."

        # file:// scheme also rejected by default
        m_file_uri = MemberSchema(member_id="m3", name="Charlie", resume_url=f"file:///{probe_file}")
        res_uri = ResumeSignalExtractor().extract(m_file_uri, {"resume_extracted_skills"}, {})
        assert res_uri[0].status == SignalStatus.FAILED
        assert res_uri[0].error_message == "Local file access is disabled."

    def test_unc_paths_blocked_without_smb_hang(self):
        """UNC paths (\\\\server\\share, //server/share) are rejected without touching filesystem."""
        unc_path = r"\\192.168.1.100\resumes\resume.pdf"
        m_unc = MemberSchema(member_id="m_unc", name="UNC", resume_url=unc_path)
        # With default config:
        res = ResumeSignalExtractor().extract(m_unc, {"resume_extracted_skills"}, {})
        assert res[0].status == SignalStatus.FAILED
        assert res[0].error_message == "Local file access is disabled."

        # Even with allow_local_files=True, UNC is rejected:
        res_cfg = ResumeSignalExtractor().extract(m_unc, {"resume_extracted_skills"}, {"allow_local_files": True})
        assert res_cfg[0].status == SignalStatus.FAILED
        assert res_cfg[0].error_message == "Local file access is disabled."

    def test_local_file_allowed_with_explicit_config(self, tmp_path):
        """When allow_local_files is explicitly True, valid files are read; missing files return not found."""
        pdf_bytes = make_test_pdf_bytes(["Python Developer", "Education", "B.Tech in Computer Science"])
        pdf_file = tmp_path / "valid.pdf"
        pdf_file.write_bytes(pdf_bytes)

        m_ok = MemberSchema(member_id="m_ok", name="Ok", resume_url=str(pdf_file))
        res = ResumeSignalExtractor().extract(m_ok, {"resume_extracted_skills"}, {"allow_local_files": True})
        assert res[0].status == SignalStatus.EXTRACTED
        assert "Python" in res[0].value["languages"]

        # Missing file returns clear not found with path
        missing_path = str(tmp_path / "not_there.pdf")
        m_miss = MemberSchema(member_id="m_miss", name="Miss", resume_url=missing_path)
        res_m = ResumeSignalExtractor().extract(m_miss, {"resume_extracted_skills"}, {"allow_local_files": True})
        assert res_m[0].status == SignalStatus.FAILED
        assert "Local resume file not found:" in res_m[0].error_message

    # 2. P0.2 - SSRF & DNS rebinding
    def test_ssrf_port_allowlist_strictly_80_443(self):
        """Only ports 80 and 443 are allowed; 8080 and 8443 are blocked."""
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
            safe_80, _ = validate_url_security("http://example.com:80/resume.pdf")
            safe_443, _ = validate_url_security("https://example.com:443/resume.pdf")
            blocked_8080, err_8080 = validate_url_security("http://example.com:8080/resume.pdf")
            blocked_8443, err_8443 = validate_url_security("https://example.com:8443/resume.pdf")

        assert safe_80 is True
        assert safe_443 is True
        assert blocked_8080 is False
        assert "Restricted port" in err_8080
        assert blocked_8443 is False
        assert "Restricted port" in err_8443

    def test_ssrf_rejects_cgnat_ips(self):
        """Carrier-Grade NAT (100.64.0.0/10) is rejected."""
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [(2, 1, 6, "", ("100.64.0.1", 80))]
            safe, err = validate_url_security("http://cgnat.test/resume.pdf")
            assert safe is False
            assert "non-global IP address" in err or "blocked" in err

    def test_download_rejects_http_redirects(self):
        """Redirects (301/302) are rejected to prevent redirect-based SSRF."""
        with patch("app.signals.resume.validate_url_security", return_value=(True, None)):
            with patch("httpx.Client.stream") as mock_stream:
                mock_resp = MagicMock()
                mock_resp.status_code = 302
                mock_stream.return_value.__enter__.return_value = mock_resp
                bytes_out, err = download_resume_file("https://example.com/redirect.pdf")
                assert bytes_out is None
                assert "redirects are not permitted" in err.lower()

    # 3. P0.3 - Non-blocking I/O
    def test_health_check_responds_during_extraction(self):
        """FastAPI event loop remains responsive for /api/health while extraction runs in threadpool."""
        import asyncio
        import time

        async def run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                async def delayed_extract():
                    orig_execute = default_signal_registry.execute_extraction

                    def slow_sync(teams, selected_signals, config):
                        time.sleep(0.3)
                        return orig_execute(teams=teams, selected_signals=selected_signals, config=config)

                    req_payload = {
                        "teams": [
                            {
                                "team_id": "T_ASYNC",
                                "team_name": "Async Team",
                                "members": [{"member_id": "M_ASYNC", "name": "Async Dev", "resume_url": "resume.pdf", "custom_fields": {"resume_text": "Python developer"}}],
                            }
                        ],
                        "selected_signals": ["resume_extracted_skills"],
                    }
                    with patch.object(default_signal_registry, "execute_extraction", side_effect=slow_sync):
                        return await ac.post(EXTRACT_URL, json=req_payload)

                async def probe_health():
                    await asyncio.sleep(0.05)
                    t0 = time.perf_counter()
                    resp = await ac.get("/api/health")
                    t_elapsed = time.perf_counter() - t0
                    return resp.status_code, t_elapsed

                res_extract, (health_status, health_elapsed) = await asyncio.gather(
                    delayed_extract(),
                    probe_health(),
                )
                assert health_status == 200
                assert res_extract.status_code == 200
                assert health_elapsed < 0.25

        asyncio.run(run())

    # 4. P1.4 - Links accuracy & schemeless
    def test_schemeless_and_competitive_programming_links(self):
        """Schemeless URLs, CP platforms, and normalized https:// are properly extracted."""
        raw_text = (
            "Contact: github.com/test-user, www.linkedin.com/in/test-user., "
            "leetcode.com/problem_solver; codeforces.com/profile/tourist) "
            "portfolio.dev/me! Also check kaggle.com/grandmaster"
        )
        data, evidence = extract_external_links_from_text(raw_text)

        assert "https://github.com/test-user" in data["github_urls"]
        assert "https://www.linkedin.com/in/test-user" in data["linkedin_urls"]
        assert "https://leetcode.com/problem_solver" in data["competitive_programming_urls"]
        assert "https://codeforces.com/profile/tourist" in data["competitive_programming_urls"]
        assert "https://kaggle.com/grandmaster" in data["competitive_programming_urls"]
        assert "https://portfolio.dev/me" in data["portfolio_urls"]
        assert not any(u.endswith((".", ",", ";", "!", ")")) for u in data["github_urls"] + data["competitive_programming_urls"])

    # 5. P1.5 - Experience duration & parsing
    def test_experience_with_present_and_injectable_today(self):
        """Active role with 'Present' uses reference date and never returns 0.0."""
        text = "Backend Developer | Startup Labs | Jan 2024 - Present"
        ref_date = datetime.date(2026, 10, 1)  # ~34 months = 2.83 years
        entries, years, evidence = extract_experience_from_text(text, today=ref_date)

        assert len(entries) == 1
        assert entries[0]["role"] == "Backend Developer"
        assert entries[0]["organization"] == "Startup Labs"
        assert 2.7 <= years <= 2.9

    def test_unstructured_resume_without_experience_header(self):
        """Unstructured resumes without 'Experience' section still extract dated roles."""
        text = "Rahul Sharma\nSoftware Engineer at TechCorp\nJune 2021 - May 2023\nBuilt distributed databases"
        entries, years, _ = extract_experience_from_text(text)
        assert len(entries) >= 1
        assert entries[0]["role"] == "Software Engineer"
        assert entries[0]["organization"] == "TechCorp"
        assert 1.9 <= years <= 2.1

    def test_multiline_job_entry_not_split(self):
        """Multi-line job entries are grouped together instead of creating split duplicate entries."""
        text = (
            "Experience\n"
            "Software Engineer at Acme Corp\n"
            "Jan 2022 - Dec 2022\n"
            "- Developed payment gateways\n"
            "- Optimized SQL queries"
        )
        entries, years, _ = extract_experience_from_text(text)
        assert len(entries) == 1
        assert entries[0]["role"] == "Software Engineer"
        assert entries[0]["organization"] == "Acme Corp"
        assert entries[0]["duration"] == "Jan 2022 - Dec 2022"

    def test_experience_overlapping_intervals_merged(self):
        """Overlapping job intervals are merged to avoid double-counting experience."""
        text = (
            "Experience\n"
            "Role 1 | Company A | Jan 2023 - Dec 2023\n"
            "Role 2 | Company B | Jun 2023 - Jun 2024\n"
        )
        # Jan 2023 to Jun 2024 = 18 months = 1.5 years (not 1.0 + 1.0 = 2.0)
        entries, years, _ = extract_experience_from_text(text)
        assert len(entries) == 2
        assert years == 1.5

    def test_internship_date_fallback_flag(self):
        """Undated internships receive 0.25 fallback and fallback_dates=True; dated ones use real duration."""
        undated = "Experience\nSoftware Engineer Intern at BigCo"
        entries_u, years_u, _ = extract_experience_from_text(undated)
        assert len(entries_u) == 1
        assert entries_u[0]["fallback_dates"] is True
        assert years_u == 0.25

        dated = "Experience\nSoftware Engineer Intern at BigCo | Jun 2023 - Aug 2023"
        entries_d, years_d, _ = extract_experience_from_text(dated)
        assert len(entries_d) == 1
        assert entries_d[0].get("fallback_dates") is not True
        assert 0.24 <= years_d <= 0.26

    # 6. P1.6 - Education accuracy & graduation year
    def test_education_latest_year_extracted_from_range(self):
        """Graduation year range '2020 - 2024' extracts the latest year (2024)."""
        text = "Education\nB.Tech in Computer Science\nNational Institute of Technology, Trichy\n2020 - 2024"
        edu, deg_short, _ = extract_education_from_text(text)
        assert edu["degree_short"] == "B.Tech"
        assert edu["institution"] == "National Institute of Technology, Trichy"
        assert edu["graduation_year"] == 2024

    def test_degree_pattern_does_not_match_lowercase_be(self):
        """Lowercase 'be' in conversational prose never matches Bachelor of Engineering."""
        text = "I aspire to be a leader in technology."
        edu, deg_short, _ = extract_education_from_text(text)
        assert edu["degree"] is None
        assert deg_short is None

    def test_ms_office_and_ms_sql_do_not_match_degree(self):
        """Mentions of MS Office or MS SQL Server do not match Master of Science degree."""
        text = "Skills: MS Office, MS SQL Server. I want to be a leader."
        edu, deg_short, _ = extract_education_from_text(text)
        assert edu["degree"] is None
        assert deg_short is None

    # 7. P1.7 - Skill false positives in prose
    def test_prose_ambiguous_words_yield_zero_skills_and_degrees(self):
        """Conversational prose with ambiguous keywords yields zero skills and zero degrees."""
        prose = "In my next role, I want to express my ideas swiftly to be a leader."
        skills, _ = extract_skills_from_text(prose)
        edu, deg, _ = extract_education_from_text(prose)

        assert skills["languages"] == []
        assert skills["frameworks"] == []
        assert skills["total_skills_count"] == 0
        assert edu["degree"] is None
        assert deg is None

    def test_ambiguous_skills_extracted_in_tech_list_or_skills_section(self):
        """Ambiguous skills match when in Skills section or tech list."""
        tech_list = "Skills: Python, Rust, Swift, Go, Next.js, Express"
        skills, _ = extract_skills_from_text(tech_list)
        assert "Python" in skills["languages"]
        assert "Rust" in skills["languages"]
        assert "Swift" in skills["languages"]
        assert "Go" in skills["languages"]
        assert "Next.js" in skills["frameworks"]
        assert "Express" in skills["frameworks"]

    # 8. P1.8 - Achievements & Hackathons
    def test_hackathon_and_achievements_detection(self):
        """Detects varied hackathon placement formats and strips bullet prefixes."""
        text = (
            "Achievements\n"
            "1. Winner - Hackathon 2023\n"
            "• Runner-up | Smart India Hackathon\n"
            "- Finalist (Global AI Hackathon)\n"
            "Hackathon Champion 2024\n"
        )
        items, evidence = extract_certifications_achievements_from_text(text)
        titles = [i["title"] for i in items]
        assert any("Winner" in t for t in titles)
        assert any("Runner-up" in t or "Smart India" in t for t in titles)
        assert any("Finalist" in t for t in titles)
        assert any("Champion" in t for t in titles)
        assert not any(t.startswith(("1.", "•", "-")) for t in titles)

    # 10. P2.10 - Dynamic confidence
    def test_dynamic_confidence_attached_to_all_12_signals(self):
        """All 12 produced resume signals include dynamic confidence in [0.0, 1.0] and confidence_rule."""
        pdf_bytes = make_test_pdf_bytes(STANDARD_RESUME_LINES)
        member = MemberSchema(
            member_id="m_conf",
            name="Conf Candidate",
            resume_url="resume.pdf",
            custom_fields={"resume_bytes": pdf_bytes},
        )
        signals = ResumeSignalExtractor().extract(member)

        assert len(signals) == 12
        for s in signals:
            assert s.status == SignalStatus.EXTRACTED
            assert s.evidence is not None
            assert s.evidence.confidence is not None
            assert 0.0 <= s.evidence.confidence <= 1.0
            assert "confidence_rule" in s.evidence.metadata
            assert isinstance(s.evidence.metadata["confidence_rule"], str)

