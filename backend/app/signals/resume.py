"""Resume Signal Extractor for PDF and DOCX candidate resumes.

Extracts evidence-backed information from resumes without OCR:
- Skills and Technologies (programming languages, frameworks, databases, tools)
- Projects (titles, descriptions, associated technologies, and evidence snippets)
- Education (degrees, institutions, graduation years, GPA)
- Experience and Achievements (internships, work history, roles, certifications)
- External Links (GitHub, portfolio, LinkedIn, other professional profiles)

Includes SSRF-safe URL downloading, document validation, error isolation,
and integration with BaseSignalExtractor and SignalExtractorRegistry.
"""

from __future__ import annotations

import datetime
import io
import ipaddress
import os
import re
import socket
import urllib.parse
from typing import Any, Optional

import docx
import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.schemas.ingestion import MemberSchema
from app.signals.base import BaseSignalExtractor
from app.signals.schemas import (
    ExtractedSignal,
    ExtractorDescriptor,
    SignalDefinition,
    SignalEvidence,
    SignalStatus,
)

# ---------------------------------------------------------------------------
# Maximum sizes and timeouts
# ---------------------------------------------------------------------------

DEFAULT_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_DOWNLOAD_TIMEOUT = 10.0  # seconds

# ---------------------------------------------------------------------------
# Technology and Skill Catalogs
# ---------------------------------------------------------------------------

PROGRAMMING_LANGUAGES: dict[str, str] = {
    r"\bpython\b": "Python",
    r"\bjavascript\b|\bjs\b": "JavaScript",
    r"\btypescript\b|\bts\b": "TypeScript",
    r"\bc\+\+(?!\w)|\bcpp\b": "C++",
    r"\bc#(?!\w)|\bc-sharp\b": "C#",
    r"\b(?:c\s+programming|ansi\s+c|c\s*[/,]\s*c\+\+|c\s*[/,]\s*cpp)\b": "C",
    r"\bjava\b(?!script)": "Java",
    r"\bgolang\b|\bgo\s+(?:programming|developer|engineer|lang)\b|(?:(?<=[,/|•:-])\s*go(?:\s*[,/|•:-]|\b))|(?:\bgo\s*[,/|•:-])": "Go",
    r"\brust\b": "Rust",
    r"\bruby\b": "Ruby",
    r"\bphp\b": "PHP",
    r"\bswift\b": "Swift",
    r"\bkotlin\b": "Kotlin",
    r"\bscala\b": "Scala",
    r"\br\s+programming\b|\br\s*[,/]\s*python\b|\br-lang\b": "R",
    r"\bdart\b": "Dart",
    r"\bsql\b|\bpl/sql\b|\bt-sql\b": "SQL",
    r"\bbash\b|\bshell\b|\bpowershell\b": "Shell",
    r"\bhtml(?:5)?\b": "HTML",
    r"\bcss(?:3)?\b": "CSS",
    r"\bsolidity\b": "Solidity",
    r"\bmatlab\b": "MATLAB",
    r"\bperl\b": "Perl",
    r"\bhaskell\b": "Haskell",
    r"\bjulia\b": "Julia",
    r"\blua\b": "Lua",
}

FRAMEWORKS_LIBRARIES: dict[str, str] = {
    r"\breact(?:\.js|js)?\b(?! native)": "React",
    r"\breact\s+native\b": "React Native",
    r"\bnext(?:\.js|js)?\b": "Next.js",
    r"\bvue(?:\.js|js)?\b": "Vue",
    r"\bangular(?:\.js|js)?\b": "Angular",
    r"\bsvelte\b": "Svelte",
    r"\bdjango\b": "Django",
    r"\bfastapi\b": "FastAPI",
    r"\bflask\b": "Flask",
    r"\bspring\s+boot\b|\bspring\s+framework\b": "Spring Boot",
    r"\bexpress(?:\.js|js)?\b": "Express",
    r"\bnode(?:\.js|js)?\b": "Node.js",
    r"\bnest(?:\.js|js)?\b": "NestJS",
    r"\basp\.net\b|\b\.net\s+core\b|\b\.net\b": ".NET",
    r"\bruby\s+on\s+rails\b|\brails\b": "Ruby on Rails",
    r"\bpytorch\b": "PyTorch",
    r"\btensorflow\b": "TensorFlow",
    r"\bkeras\b": "Keras",
    r"\bscikit-learn\b|\bsklearn\b": "Scikit-learn",
    r"\bpandas\b": "Pandas",
    r"\bnumpy\b": "NumPy",
    r"\btailwind(?:\s+css)?\b": "Tailwind CSS",
    r"\bbootstrap\b": "Bootstrap",
    r"\bgraphql\b": "GraphQL",
    r"\bredux\b": "Redux",
    r"\bopencv\b": "OpenCV",
}

DATABASES: dict[str, str] = {
    r"\bpostgresql\b|\bpostgres\b": "PostgreSQL",
    r"\bmysql\b": "MySQL",
    r"\bsqlite(?:3)?\b": "SQLite",
    r"\bmongodb\b|\bmongo\b": "MongoDB",
    r"\bredis\b": "Redis",
    r"\bcassandra\b": "Cassandra",
    r"\bdynamodb\b": "DynamoDB",
    r"\boracle\s+db\b|\boracle\s+database\b": "Oracle",
    r"\belasticsearch\b": "Elasticsearch",
    r"\bfirebase\b": "Firebase",
    r"\bsupabase\b": "Supabase",
    r"\bsnowflake\b": "Snowflake",
    r"\bbigquery\b": "BigQuery",
    r"\bmariadb\b": "MariaDB",
    r"\bneo4j\b": "Neo4j",
}

TOOLS_TECHNOLOGIES: dict[str, str] = {
    r"\bdocker\b": "Docker",
    r"\bkubernetes\b|\bk8s\b": "Kubernetes",
    r"\bgit\b(?!hub|lab)": "Git",
    r"\bgithub\b": "GitHub",
    r"\bgitlab\b": "GitLab",
    r"\blinux\b|\bubuntu\b|\bdebian\b": "Linux",
    r"\baws\b|\bamazon\s+web\s+services\b": "AWS",
    r"\bazure\b": "Azure",
    r"\bgcp\b|\bgoogle\s+cloud\b": "GCP",
    r"\bjenkins\b": "Jenkins",
    r"\bci/cd\b|\bcontinuous\s+integration\b": "CI/CD",
    r"\bterraform\b": "Terraform",
    r"\bansible\b": "Ansible",
    r"\bnginx\b": "Nginx",
    r"\bapache\b": "Apache",
    r"\bpostman\b": "Postman",
    r"\bkafka\b": "Kafka",
    r"\brabbitmq\b": "RabbitMQ",
    r"\bjira\b": "Jira",
    r"\bfigma\b": "Figma",
}

# ---------------------------------------------------------------------------
# SSRF-Safe Downloader
# ---------------------------------------------------------------------------


def validate_url_security(url: str) -> tuple[bool, Optional[str]]:
    """Validate that a URL is safe against SSRF attacks before downloading.

    Enforces:
    - Scheme must be http or https
    - Hostname must be present and resolve to a public IP
    - Private networks (RFC 1918), loopback, link-local, and cloud metadata IPs blocked
    - Credentials in URL blocked
    - Non-standard ports restricted
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or not a string."

    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if parsed.scheme.lower() not in {"http", "https"}:
        return False, f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    if not parsed.netloc:
        return False, "URL lacks a valid network host."

    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials (user:password@) are not permitted."

    # Validate port if specified
    if parsed.port and parsed.port not in {80, 443, 8080, 8443}:
        return False, f"Restricted port '{parsed.port}' not allowed. Only standard web ports (80, 443, 8080, 8443) are allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL lacks a valid hostname."

    # Resolve IP addresses and verify against private/local networks
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        return False, f"Failed to resolve hostname '{hostname}': {exc}"

    for family, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip_obj.is_private:
            return False, f"Access to private network IP address '{ip_str}' is blocked for security."
        if ip_obj.is_loopback:
            return False, f"Access to loopback IP address '{ip_str}' is blocked for security."
        if ip_obj.is_link_local:
            return False, f"Access to link-local IP address '{ip_str}' is blocked for security."
        if ip_obj.is_reserved or ip_obj.is_multicast:
            return False, f"Access to reserved IP address '{ip_str}' is blocked."
        if str(ip_obj) == "169.254.169.254":
            return False, "Access to cloud metadata service is blocked."

    return True, None


def download_resume_file(
    url: str,
    max_bytes: int = DEFAULT_MAX_RESUME_BYTES,
    timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
) -> tuple[Optional[bytes], Optional[str]]:
    """Safely download a resume file over HTTP/HTTPS with size limit and SSRF protection."""
    is_safe, err_msg = validate_url_security(url)
    if not is_safe:
        return None, err_msg

    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", url, headers={"User-Agent": "TeamRecruitmentTool-ResumeAnalyzer/1.0"}) as resp:
                if resp.status_code >= 400:
                    return None, f"Failed to download resume: HTTP {resp.status_code}"

                content_len = resp.headers.get("content-length")
                if content_len and int(content_len) > max_bytes:
                    return None, f"Resume exceeds maximum allowed size of {max_bytes} bytes."

                buf = io.BytesIO()
                downloaded = 0
                for chunk in resp.iter_bytes(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        return None, f"Resume download exceeded maximum allowed size of {max_bytes} bytes."
                    buf.write(chunk)
                return buf.getvalue(), None
    except httpx.TimeoutException:
        return None, f"Request timed out while downloading resume after {timeout} seconds."
    except httpx.RequestError as exc:
        return None, f"Network error while downloading resume: {exc}"
    except Exception as exc:
        return None, f"Unexpected error downloading resume: {exc}"


# ---------------------------------------------------------------------------
# Document Text Extraction (PDF & DOCX)
# ---------------------------------------------------------------------------


def extract_text_from_document(
    raw_bytes: bytes,
    filename_or_url: str = "",
) -> tuple[Optional[str], Optional[str], dict[str, Any]]:
    """Extract plain text from PDF or DOCX file bytes.

    Returns:
        (text, error_message, metadata)
    """
    if not raw_bytes or len(raw_bytes) == 0:
        return None, "Resume document is empty (0 bytes).", {"empty": True}

    # Format detection by magic bytes and extension
    is_pdf = raw_bytes.startswith(b"%PDF-") or filename_or_url.lower().endswith(".pdf")
    is_docx = (raw_bytes.startswith(b"PK\x03\x04") and (filename_or_url.lower().endswith(".docx") or b"word/" in raw_bytes[:2048])) or filename_or_url.lower().endswith(".docx")

    if is_pdf:
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            if reader.is_encrypted:
                # Try decrypting with blank password
                try:
                    decrypted = reader.decrypt("")
                except Exception:
                    decrypted = 0
                if decrypted == 0:
                    return (
                        None,
                        "Encrypted PDF document cannot be read without a password.",
                        {"format": "pdf", "encrypted": True},
                    )

            pages_text = []
            for page in reader.pages:
                t = page.extract_text() or ""
                pages_text.append(t)
            full_text = "\n\n".join(pages_text).strip()

            if not full_text or len(re.sub(r"\s+", "", full_text)) < 20:
                return (
                    None,
                    "Document contains no readable text (may be scanned image, empty, or non-text PDF). OCR is not enabled.",
                    {"format": "pdf", "pages": len(reader.pages), "empty_or_scanned": True},
                )

            return full_text, None, {"format": "pdf", "pages": len(reader.pages), "char_count": len(full_text)}
        except PdfReadError as exc:
            return None, f"Corrupted or invalid PDF document: {exc}", {"format": "pdf", "corrupted": True}
        except Exception as exc:
            return None, f"Failed to parse PDF document: {exc}", {"format": "pdf", "error": str(exc)}

    elif is_docx:
        try:
            doc = docx.Document(io.BytesIO(raw_bytes))
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            table_cells = []
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            table_cells.append(cell.text.strip())
            full_text = "\n".join(paras + table_cells).strip()

            if not full_text or len(re.sub(r"\s+", "", full_text)) < 20:
                return None, "Document contains no readable text.", {"format": "docx", "empty": True}

            return full_text, None, {"format": "docx", "paragraphs": len(doc.paragraphs), "char_count": len(full_text)}
        except Exception as exc:
            return None, f"Corrupted or invalid DOCX document: {exc}", {"format": "docx", "corrupted": True}

    else:
        return (
            None,
            "Unsupported resume file format. Only PDF (.pdf) and DOCX (.docx) documents are supported.",
            {"unsupported": True},
        )


# ---------------------------------------------------------------------------
# Section and Signal Pattern Extractors
# ---------------------------------------------------------------------------


def _find_snippet_lines(text: str, keywords: list[str], max_lines: int = 4) -> str:
    """Find text lines containing any of the given keywords for evidence snippets."""
    matching: list[str] = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        for kw in keywords:
            if kw.lower() in line.lower():
                matching.append(line)
                break
        if len(matching) >= max_lines:
            break
    return " | ".join(matching) if matching else ""


def extract_skills_from_text(text: str) -> tuple[dict[str, Any], list[str]]:
    """Extract categorized technical skills and evidence from resume text."""
    languages: list[str] = []
    frameworks: list[str] = []
    databases: list[str] = []
    tools: list[str] = []

    text_lower = text.lower()

    for pattern, name in PROGRAMMING_LANGUAGES.items():
        if re.search(pattern, text_lower) and name not in languages:
            languages.append(name)

    for pattern, name in FRAMEWORKS_LIBRARIES.items():
        if re.search(pattern, text_lower) and name not in frameworks:
            frameworks.append(name)

    for pattern, name in DATABASES.items():
        if re.search(pattern, text_lower) and name not in databases:
            databases.append(name)

    for pattern, name in TOOLS_TECHNOLOGIES.items():
        if re.search(pattern, text_lower) and name not in tools:
            tools.append(name)

    all_skills = sorted(list(set(languages + frameworks + databases + tools)))
    evidence_lines = _find_snippet_lines(text, all_skills[:6])

    skill_data = {
        "languages": sorted(languages),
        "frameworks": sorted(frameworks),
        "databases": sorted(databases),
        "tools": sorted(tools),
        "all_skills": all_skills,
        "total_skills_count": len(all_skills),
        "note": "Mention of technologies in resume text does not independently prove proficiency.",
    }
    return skill_data, [evidence_lines] if evidence_lines else []


def extract_projects_from_text(text: str) -> tuple[list[dict[str, Any]], str]:
    """Extract project names, descriptions, associated technologies, and evidence."""
    projects: list[dict[str, Any]] = []

    # Identify project sections or bullet groups
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    in_project_section = False
    current_project: Optional[dict[str, Any]] = None

    project_header_re = re.compile(r"^(?:projects?|academic\s+projects?|personal\s+projects?|technical\s+projects?)\b", re.IGNORECASE)
    section_break_re = re.compile(r"^(?:education|experience|skills|technical\s+skills|certifications?|achievements?|activities)\b", re.IGNORECASE)

    for line in lines:
        if project_header_re.search(line):
            in_project_section = True
            continue
        if in_project_section and section_break_re.search(line):
            in_project_section = False
            if current_project:
                projects.append(current_project)
                current_project = None
            continue

        if in_project_section:
            # Check for project title line: e.g. "Distributed Key-Value Store | Go, Raft" or bold bullet
            # Match formats like: "Project Title | Tech Stack" or "Project Title - Tech Stack"
            title_match = re.match(r"^([A-Z0-9][A-Za-z0-9\s_\-:]{3,40})(?:\s*[\|\-\–\—\:]\s*(.+))?$", line)
            if title_match and not line.startswith(("-", "•", "*", "http")):
                if current_project:
                    projects.append(current_project)
                p_name = title_match.group(1).strip()
                p_tech_str = title_match.group(2) or ""

                # Extract technologies associated with this project
                techs: list[str] = []
                for p_dict in [PROGRAMMING_LANGUAGES, FRAMEWORKS_LIBRARIES, DATABASES, TOOLS_TECHNOLOGIES]:
                    for pat, tname in p_dict.items():
                        if (
                            re.search(pat, p_tech_str.lower())
                            or (tname == "Go" and re.search(r"\bgo\b", p_tech_str.lower()))
                        ) and tname not in techs:
                            techs.append(tname)

                current_project = {
                    "name": p_name,
                    "technologies": techs,
                    "description": "",
                    "evidence": line,
                    "verified": False,
                    "provenance": "self_reported_resume",
                }
            elif current_project:
                # Append description
                desc = line.lstrip("-•* ").strip()
                if not current_project["description"]:
                    current_project["description"] = desc
                else:
                    current_project["description"] += " " + desc
                # Also detect techs in description
                for p_dict in [PROGRAMMING_LANGUAGES, FRAMEWORKS_LIBRARIES, DATABASES, TOOLS_TECHNOLOGIES]:
                    for pat, tname in p_dict.items():
                        if (
                            re.search(pat, desc.lower())
                            or (tname == "Go" and re.search(r"\b(?:golang|go\s+(?:programming|lang|code))\b", desc.lower()))
                        ) and tname not in current_project["technologies"]:
                            current_project["technologies"].append(tname)

    if current_project:
        projects.append(current_project)

    evidence_summary = " | ".join(p["name"] for p in projects[:3]) if projects else ""
    return projects, evidence_summary


def extract_education_from_text(text: str) -> tuple[dict[str, Any], Optional[str], str]:
    """Extract degree, institution, graduation year, GPA, and evidence snippet."""
    degree: Optional[str] = None
    degree_short: Optional[str] = None
    institution: Optional[str] = None
    grad_year: Optional[int] = None
    gpa: Optional[str] = None
    evidence: str = ""

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    degree_patterns = [
        (r"\b(?:b\.?tech(?:nology)?|bachelor\s+of\s+technology)\b", "Bachelor of Technology", "B.Tech"),
        (r"\b(?:b\.?e\.?|bachelor\s+of\s+engineering)\b", "Bachelor of Engineering", "B.E."),
        (r"\b(?:b\.?s\.?|b\.?sc|bachelor\s+of\s+science)\b", "Bachelor of Science", "B.S."),
        (r"\b(?:bca|bachelor\s+of\s+computer\s+applications)\b", "Bachelor of Computer Applications", "BCA"),
        (r"\b(?:m\.?tech(?:nology)?|master\s+of\s+technology)\b", "Master of Technology", "M.Tech"),
        (r"\b(?:m\.?s\.?|m\.?sc|master\s+of\s+science)\b", "Master of Science", "M.S."),
        (r"\b(?:mca|master\s+of\s+computer\s+applications)\b", "Master of Computer Applications", "MCA"),
        (r"\b(?:mba|master\s+of\s+business\s+administration)\b", "Master of Business Administration", "MBA"),
        (r"\b(?:ph\.?d|doctor\s+of\s+philosophy)\b", "Doctor of Philosophy", "Ph.D."),
    ]

    for line in lines:
        if not degree:
            for pat, full_d, short_d in degree_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    degree = full_d
                    degree_short = short_d
                    evidence = line
                    break

        if not institution:
            inst_match = re.search(
                r"\b(?:(?:University|Institute|College|School)\s+of\s+[A-Za-z\s]+|"
                r"[A-Z][a-zA-Z\s]+(?:Institute\s+of\s+(?:Technology|Science|Management)|College\s+of\s+[A-Za-z\s]+|University|Institute|College|Academy|IIT|NIT|IIIT|BITS|MIT|Stanford|Harvard))\b",
                line,
            )
            if inst_match:
                institution = inst_match.group(0).strip()
                if not evidence:
                    evidence = line

        if not grad_year:
            year_match = re.search(
                r"(?:expected|graduation|class\s+of|batch|passing|may|june|july|december|august)?\s*(20[1-3][0-9])",
                line,
                re.IGNORECASE,
            )
            if year_match:
                try:
                    val = int(year_match.group(1))
                    if 2010 <= val <= 2035:
                        grad_year = val
                except ValueError:
                    pass

        if not gpa:
            gpa_match = re.search(r"(?:cgpa|gpa|cpi)\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?(?:\s*/\s*[0-9]+)?)", line, re.IGNORECASE)
            if gpa_match:
                gpa = gpa_match.group(1).strip()

    edu_dict = {
        "degree": degree,
        "degree_short": degree_short,
        "institution": institution,
        "graduation_year": grad_year,
        "gpa": gpa,
        "evidence": evidence,
        "verified": False,
    }
    return edu_dict, degree_short, evidence


def extract_experience_from_text(text: str) -> tuple[list[dict[str, Any]], float, str]:
    """Extract work experience entries, internships, duration, and estimate years of experience."""
    experiences: list[dict[str, Any]] = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    role_patterns = re.compile(
        r"\b(?:software\s+engineer\s+intern|software\s+developer\s+intern|engineering\s+intern|"
        r"data\s+science\s+intern|research\s+intern|frontend\s+developer\s+intern|backend\s+developer\s+intern|"
        r"senior\s+software\s+engineer|lead\s+software\s+engineer|software\s+engineer|"
        r"software\s+developer|backend\s+developer|frontend\s+developer|"
        r"full\s+stack\s+developer|devops\s+engineer|research\s+assistant|teaching\s+assistant|"
        r"intern(?:ship)?|sde\s*[-–—]?\s*(?:intern|[123]|i+)?|swe\s*[-–—]?\s*(?:intern|[123]|i+)?)\b",
        re.IGNORECASE,
    )

    date_range_re = re.compile(
        r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*20[1-3][0-9]|20[1-3][0-9])\s*[-–—to]+\s*"
        r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*20[1-3][0-9]|20[1-3][0-9]|present)",
        re.IGNORECASE,
    )

    in_exp_section = False
    exp_header_re = re.compile(r"^(?:experience|work\s+experience|professional\s+experience|internships?|employment\s+history)\b", re.IGNORECASE)
    section_break_re = re.compile(r"^(?:education|projects|skills|technical\s+skills|certifications?|achievements?|activities)\b", re.IGNORECASE)

    current_entry: Optional[dict[str, Any]] = None

    for line in lines:
        if exp_header_re.search(line):
            in_exp_section = True
            continue
        if in_exp_section and section_break_re.search(line):
            in_exp_section = False
            if current_entry:
                experiences.append(current_entry)
                current_entry = None
            continue

        if in_exp_section:
            role_m = role_patterns.search(line)
            date_m = date_range_re.search(line)

            if role_m or date_m:
                if current_entry:
                    experiences.append(current_entry)
                role_str = role_m.group(0).title() if role_m else "Technical Contributor"
                dur_str = date_m.group(0) if date_m else ""
                current_entry = {
                    "role": role_str,
                    "organization": line.split("|")[0].split("-")[0].strip() if "|" in line or "-" in line else line,
                    "duration": dur_str,
                    "description": "",
                    "evidence": line,
                    "verified": False,
                }
            elif current_entry:
                desc = line.lstrip("-•* ").strip()
                if not current_entry["description"]:
                    current_entry["description"] = desc
                else:
                    current_entry["description"] += " " + desc

    if current_entry:
        experiences.append(current_entry)

    # Estimate experience years based on parsed entries
    est_years = 0.0
    for exp in experiences:
        dur = exp.get("duration", "").lower()
        if "intern" in exp.get("role", "").lower():
            est_years += 0.25  # ~3 months per internship
        elif "20" in dur:
            # Check year span
            years = re.findall(r"20[1-3][0-9]", dur)
            if len(years) >= 2:
                try:
                    diff = int(years[1]) - int(years[0])
                    est_years += max(0.5, float(diff))
                except Exception:
                    est_years += 0.5
            else:
                est_years += 0.5
        else:
            est_years += 0.25

    est_years = round(est_years, 2)
    evidence_str = " | ".join(f"{e['role']} at {e['organization']}" for e in experiences[:2]) if experiences else ""
    return experiences, est_years, evidence_str


def extract_certifications_achievements_from_text(text: str) -> tuple[list[dict[str, Any]], str]:
    """Extract explicitly stated certifications, hackathon wins, and achievements."""
    items: list[dict[str, Any]] = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    cert_patterns = [
        (r"\baws\s+certified\b[^\n,]*", "certification"),
        (r"\bgoogle\s+cloud\s+certified\b[^\n,]*", "certification"),
        (r"\bmicrosoft\s+certified\b[^\n,]*", "certification"),
        (r"\bcertified\s+kubernetes\b[^\n,]*", "certification"),
        (r"\b1st\s+place\b[^\n,]*|\bfirst\s+place\b[^\n,]*|\bwinner\b[^\n,]*hackathon[^\n,]*", "achievement"),
        (r"\bhackathon\b[^\n,]*(?:winner|1st|2nd|3rd|finalist|champion)", "achievement"),
        (r"\bdean'?s\s+list\b", "achievement"),
    ]

    for line in lines:
        for pat, item_type in cert_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                title = m.group(0).strip()
                if not any(i["title"].lower() == title.lower() for i in items):
                    items.append({
                        "title": title,
                        "type": item_type,
                        "evidence": line,
                        "verified": False,
                    })

    evidence_summary = " | ".join(i["title"] for i in items[:3]) if items else ""
    return items, evidence_summary


def extract_external_links_from_text(text: str) -> tuple[dict[str, list[str]], str]:
    """Extract GitHub, portfolio, LinkedIn, and other professional links from resume text."""
    github_urls: list[str] = []
    linkedin_urls: list[str] = []
    portfolio_urls: list[str] = []
    other_urls: list[str] = []

    # Match URLs with protocol or www or github.com
    url_re = re.compile(r"(?:https?://|www\.)[A-Za-z0-9_\-\.\/]+|[A-Za-z0-9_-]+\.(?:dev|me|io|app|github\.io)(?:/[A-Za-z0-9_\-\.\/]*)?", re.IGNORECASE)

    raw_matches = url_re.findall(text)
    for raw in raw_matches:
        url = raw.strip().rstrip(".,;:)")
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        url_lower = url.lower()
        if "github.com" in url_lower or "github.io" in url_lower:
            if url not in github_urls:
                github_urls.append(url)
        elif "linkedin.com" in url_lower:
            if url not in linkedin_urls:
                linkedin_urls.append(url)
        elif any(ext in url_lower for ext in [".dev", ".me", ".io", ".app", "portfolio", "personal"]):
            if url not in portfolio_urls:
                portfolio_urls.append(url)
        elif any(site in url_lower for site in ["leetcode.com", "codeforces.com", "kaggle.com", "hackerrank.com"]):
            if url not in other_urls:
                other_urls.append(url)

    link_data = {
        "github_urls": github_urls,
        "portfolio_urls": portfolio_urls,
        "linkedin_urls": linkedin_urls,
        "other_urls": other_urls,
        "note": "Extracted from resume document; not independently verified.",
    }
    evidence_summary = f"GitHub: {len(github_urls)}, LinkedIn: {len(linkedin_urls)}, Portfolio: {len(portfolio_urls)}"
    return link_data, evidence_summary


# ---------------------------------------------------------------------------
# Pluggable ResumeSignalExtractor Class
# ---------------------------------------------------------------------------


class ResumeSignalExtractor(BaseSignalExtractor):
    """Signal extractor for parsing candidate PDF and DOCX resumes."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="resume_parser",
            name="Resume & CV Signal Analyzer",
            description="Extracts technical skills, projects, education, experience, achievements, and links from PDF and DOCX resumes.",
            category="experience",
            required_inputs=["resume_url"],
            optional_inputs=["resume_text", "resume_bytes", "custom_fields"],
            produced_signals=[
                "resume_extracted_skills",
                "resume_programming_languages",
                "resume_frameworks_libraries",
                "resume_databases",
                "resume_tools_technologies",
                "resume_projects",
                "resume_education",
                "resume_degree_level",
                "resume_experience",
                "resume_experience_years",
                "resume_certifications_achievements",
                "resume_external_links",
            ],
            signals=[
                SignalDefinition(
                    signal_key="resume_extracted_skills",
                    name="Extracted Skills",
                    description="Categorized technical skills identified in resume text (languages, frameworks, databases, tools).",
                    category="experience",
                    value_type="dict",
                ),
                SignalDefinition(
                    signal_key="resume_programming_languages",
                    name="Programming Languages",
                    description="Programming languages explicitly identified in resume text.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_frameworks_libraries",
                    name="Frameworks & Libraries",
                    description="Software frameworks and libraries mentioned in resume text.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_databases",
                    name="Databases & Data Stores",
                    description="Databases and storage systems explicitly listed in resume text.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_tools_technologies",
                    name="Development Tools & Platforms",
                    description="Tools, cloud platforms, and DevOps technologies found in resume text.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_projects",
                    name="Projects",
                    description="Candidate projects with titles, descriptions, technologies, and evidence snippets.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_education",
                    name="Education Background",
                    description="Degrees, educational institutions, graduation years, and academic standing.",
                    category="experience",
                    value_type="dict",
                ),
                SignalDefinition(
                    signal_key="resume_degree_level",
                    name="Highest Degree Level",
                    description="Highest academic degree level identified (e.g. B.Tech, M.Tech, B.S.).",
                    category="experience",
                    value_type="string",
                ),
                SignalDefinition(
                    signal_key="resume_experience",
                    name="Work & Internship Experience",
                    description="Internships and professional roles with organizations, titles, durations, and details.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_experience_years",
                    name="Years of Experience",
                    description="Estimated duration or years of professional and internship experience.",
                    category="experience",
                    value_type="float",
                    unit="years",
                ),
                SignalDefinition(
                    signal_key="resume_certifications_achievements",
                    name="Certifications & Achievements",
                    description="Certifications, hackathon placements, awards, and honors.",
                    category="experience",
                    value_type="list",
                ),
                SignalDefinition(
                    signal_key="resume_external_links",
                    name="External Professional Links",
                    description="Links to GitHub, LinkedIn, portfolio, and competitive programming profiles.",
                    category="experience",
                    value_type="dict",
                ),
            ],
            is_enabled_by_default=False,
            optional_config={
                "max_resume_bytes": "Maximum resume file size in bytes (default 10 MB)",
                "download_timeout": "Download timeout in seconds (default 10.0)",
                "allow_local_files": "Allow reading local file paths for testing (default False)",
                "resume_url_field": "Custom source column name for resume URL in registration data",
            },
        )

    def extract(
        self,
        member: MemberSchema,
        selected_signals: Optional[set[str]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> list[ExtractedSignal]:
        """Produce signals for the given member."""
        target_signals = selected_signals or set(self.descriptor.produced_signals)
        cfg = config or {}
        results: list[ExtractedSignal] = []
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Resolve resume input
        resume_val, source_field = self._resolve_resume_input(member, cfg)

        # Handle missing input gracefully
        if not resume_val:
            for s_key in target_signals:
                results.append(
                    ExtractedSignal(
                        signal_key=s_key,
                        category="experience",
                        status=SignalStatus.NOT_APPLICABLE,
                        value=None,
                        error_message="Member did not provide a resume URL or document.",
                    )
                )
            return results

        # Load document bytes or pre-extracted text
        raw_bytes: Optional[bytes] = None
        extracted_text: Optional[str] = None
        load_error: Optional[str] = None
        doc_metadata: dict[str, Any] = {}

        # 1. Check if raw text is already provided in custom fields (e.g. test fixtures)
        if isinstance(resume_val, str) and member.custom_fields.get("resume_text"):
            extracted_text = member.custom_fields["resume_text"]
            doc_metadata["format"] = "text_override"

        # 2. Check if raw bytes are directly passed in custom fields
        elif member.custom_fields.get("resume_bytes"):
            raw_bytes = member.custom_fields["resume_bytes"]

        # 3. Handle URL or local file path
        elif isinstance(resume_val, str):
            res_str = resume_val.strip()
            if res_str.startswith(("http://", "https://")):
                max_bytes = int(cfg.get("max_resume_bytes", DEFAULT_MAX_RESUME_BYTES))
                timeout = float(cfg.get("download_timeout", DEFAULT_DOWNLOAD_TIMEOUT))
                raw_bytes, load_error = download_resume_file(res_str, max_bytes=max_bytes, timeout=timeout)
            elif cfg.get("allow_local_files", False) or os.path.isabs(res_str) or res_str.startswith("file://"):
                local_path = res_str[7:] if res_str.startswith("file://") else res_str
                if os.path.exists(local_path):
                    try:
                        with open(local_path, "rb") as f:
                            raw_bytes = f.read()
                    except Exception as exc:
                        load_error = f"Failed to read local resume file: {exc}"
                else:
                    load_error = f"Local resume file not found: {local_path}"
            else:
                load_error = f"Unsupported resume URL scheme: '{res_str}'. Must be HTTP or HTTPS."

        # Handle loading error
        if load_error or (raw_bytes is None and extracted_text is None):
            err = load_error or "Unable to acquire resume document."
            for s_key in target_signals:
                results.append(
                    ExtractedSignal(
                        signal_key=s_key,
                        category="experience",
                        status=SignalStatus.FAILED,
                        value=None,
                        error_message=err,
                        evidence=SignalEvidence(
                            source="resume_parser",
                            raw_input=str(resume_val),
                            extracted_at=now_ts,
                            metadata={"error": err},
                        ),
                    )
                )
            return results

        # Extract text if not already available
        if extracted_text is None and raw_bytes is not None:
            filename = str(resume_val) if isinstance(resume_val, str) else "resume.pdf"
            extracted_text, parse_error, doc_metadata = extract_text_from_document(raw_bytes, filename)
            if parse_error or not extracted_text:
                err = parse_error or "Failed to extract text from resume."
                for s_key in target_signals:
                    results.append(
                        ExtractedSignal(
                            signal_key=s_key,
                            category="experience",
                            status=SignalStatus.FAILED,
                            value=None,
                            error_message=err,
                            evidence=SignalEvidence(
                                source="resume_parser",
                                raw_input=str(resume_val),
                                extracted_at=now_ts,
                                metadata=doc_metadata,
                            ),
                        )
                    )
                return results

        # Extract all component signals from document text
        skills_dict, skill_evidence = extract_skills_from_text(extracted_text)
        projects_list, proj_evidence = extract_projects_from_text(extracted_text)
        edu_dict, degree_level, edu_evidence = extract_education_from_text(extracted_text)
        exp_list, exp_years, exp_evidence = extract_experience_from_text(extracted_text)
        achieve_list, achieve_evidence = extract_certifications_achievements_from_text(extracted_text)
        links_dict, links_evidence = extract_external_links_from_text(extracted_text)

        # Build individual ExtractedSignal responses based on target_signals
        if "resume_extracted_skills" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_extracted_skills",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=skills_dict,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        confidence=0.90,
                        metadata={
                            "total_skills": skills_dict["total_skills_count"],
                            "snippets": skill_evidence,
                            **doc_metadata,
                        },
                    ),
                )
            )

        if "resume_programming_languages" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_programming_languages",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=skills_dict["languages"],
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"count": len(skills_dict["languages"])},
                    ),
                )
            )

        if "resume_frameworks_libraries" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_frameworks_libraries",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=skills_dict["frameworks"],
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"count": len(skills_dict["frameworks"])},
                    ),
                )
            )

        if "resume_databases" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_databases",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=skills_dict["databases"],
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"count": len(skills_dict["databases"])},
                    ),
                )
            )

        if "resume_tools_technologies" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_tools_technologies",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=skills_dict["tools"],
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"count": len(skills_dict["tools"])},
                    ),
                )
            )

        if "resume_projects" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_projects",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=projects_list,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"projects_count": len(projects_list), "sample": proj_evidence},
                    ),
                )
            )

        if "resume_education" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_education",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=edu_dict,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"evidence": edu_evidence},
                    ),
                )
            )

        if "resume_degree_level" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_degree_level",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=degree_level,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"degree_identified": degree_level},
                    ),
                )
            )

        if "resume_experience" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_experience",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=exp_list,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"entries_count": len(exp_list), "sample": exp_evidence},
                    ),
                )
            )

        if "resume_experience_years" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_experience_years",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=exp_years,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"estimated_years": exp_years},
                    ),
                )
            )

        if "resume_certifications_achievements" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_certifications_achievements",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=achieve_list,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"count": len(achieve_list), "sample": achieve_evidence},
                    ),
                )
            )

        if "resume_external_links" in target_signals:
            results.append(
                ExtractedSignal(
                    signal_key="resume_external_links",
                    category="experience",
                    status=SignalStatus.EXTRACTED,
                    value=links_dict,
                    evidence=SignalEvidence(
                        source="resume_parser",
                        raw_input=str(resume_val),
                        extracted_at=now_ts,
                        metadata={"summary": links_evidence},
                    ),
                )
            )

        return results

    def _resolve_resume_input(
        self,
        member: MemberSchema,
        config: dict[str, Any],
    ) -> tuple[Optional[Any], str]:
        """Resolve the raw resume URL, document reference, or text from member data."""
        custom_field_key = config.get("resume_url_field")
        if custom_field_key and custom_field_key in member.custom_fields:
            return member.custom_fields[custom_field_key], custom_field_key

        if member.resume_url:
            return member.resume_url, "resume_url"

        for alt_key in ["resume_url", "resume", "cv", "resume_link", "resume_file"]:
            if alt_key in member.custom_fields and member.custom_fields[alt_key]:
                return member.custom_fields[alt_key], alt_key

        if member.custom_fields.get("resume_bytes"):
            return member.custom_fields["resume_bytes"], "resume_bytes"

        if member.custom_fields.get("resume_text"):
            return member.custom_fields["resume_text"], "resume_text"

        return None, "resume_url"
