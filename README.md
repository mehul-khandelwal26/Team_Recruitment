# Team Recruitment Automation Tool

Configurable and explainable hackathon team shortlisting system.

---

## 🎯 Problem

Hackathon organizers receive hundreds of team registrations and need to **shortlist the top X teams** fairly and transparently. Manual review is slow, inconsistent, and opaque. This tool automates the process with dynamic registration form support, selective signal extraction, configurable eligibility rules, weighted scoring, and human-readable explanations for every decision.

## ✨ Key Features

- **CSV / JSON ingestion** – upload registration data in common formats with dynamic form discovery.
- **Dynamic schema mapping** – map custom organizer column names to canonical target fields without code changes.
- **Missing ID generation & duplicate team handling** – autogenerates missing member/team IDs, detects ambiguous duplicate team names, assigns non-merging temporary IDs (`TEMP_TEAM_...`), and surfaces actionable organizer warnings.
- **Arbitrary field preservation** – unmapped form fields and raw records are safely preserved in `custom_fields` and `raw_data`.
- **Extensible signal extraction** – pluggable analyzers for GitHub activity, academics, resume documents, and future data sources.
- **Document parsing & resume analysis** – extracts skills, projects, education, work experience, certifications, and links from PDF and DOCX documents without OCR.
- **Safe remote acquisition & direct upload** – SSRF-protected resume downloading (blocks loopback, private networks, cloud metadata) with 10 MB caps, plus direct multipart file upload via `/api/signals/extract-resume`.
- **Selective signal execution** – organizers can select broad categories or individual signals without running unneeded analyzers.
- **Verifiable evidence & audit trails** – all extracted signals include provenance, raw inputs, timestamps, and confidence scores (distinguishing verified API metrics from self-reported resume claims).
- **Fault-isolated multi-team evaluation** – failure or missing data for one member or signal never halts execution of others.
- **Variable team sizes** – handle teams of any size without hard-coded member limits.
- **Scoring separation** – extraction remains cleanly decoupled from scoring rules, weighting, and ranking.

## 🛠️ Technology Stack

| Layer          | Technology                                   |
| -------------- | -------------------------------------------- |
| Backend        | Python 3.10+ · FastAPI · Pydantic v2         |
| Server         | Uvicorn                                      |
| Data           | Pandas                                       |
| HTTP / API     | HTTPX                                        |
| Document Parsers | PyPDF (`pypdf`) · Python-Docx (`python-docx`) |
| Testing        | Pytest · Starlette TestClient (126 tests)    |
| Frontend       | React + Vite *(planned)*                     |
| Database       | PostgreSQL *(planned)*                       |

## 🗺️ Project Roadmap

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Prompt 1** | Backend foundation, architectural structure, and base configuration | ✅ Completed |
| **Prompt 2** | CSV/JSON ingestion, dynamic form mapping, and validation | ✅ Completed |
| *Prompt 2.1 / 3.2* | Auto-ID generation for missing IDs, CGPA scale preservation | ✅ Completed |
| *Prompt 3.3* | Duplicate team name detection, temporary IDs, and ambiguous team warnings | ✅ Completed |
| **Prompt 3** | Evaluation signal extraction framework, GitHub analyzer, and Academic analyzer | ✅ Completed |
| **Additional Milestone** | **Resume Analyzer**: PDF/DOCX parsing, SSRF security, 12 signals, direct file upload | ✅ Completed |
| **Prompt 4** | Configurable eligibility rules and hard filters | 🔲 *Next Up* |
| **Prompt 5** | Weighted scoring and team-level aggregation | 🔲 Planned |
| **Prompt 6** | Ranking, top-X selection, and human-readable explanations | 🔲 Planned |
| **Prompt 7** | Frontend integration and organizer dashboard | 🔲 Planned |
| **Prompt 8** | End-to-end testing and final improvements | 🔲 Planned |

---

## 📦 Current Implementation Status

| Component | Status | Details |
| :--- | :--- | :--- |
| Project structure | ✅ Done | Clean architectural layer separation |
| FastAPI app skeleton | ✅ Done | Application instance, health check, CORS, router mounts |
| Ingestion & Discovery | ✅ Done | CSV/JSON upload, dynamic header discovery, schema mapping |
| Missing ID generation | ✅ Done | Generates missing Team/Member IDs without overwriting explicit IDs |
| Duplicate team detection | ✅ Done | Detects same-name teams, assigns temporary IDs (`TEMP_TEAM_...`), preserves separation |
| Dynamic form mapping | ✅ Done | Preserves arbitrary custom fields, tracks missing states |
| Signal Extraction Framework | ✅ Implemented | Extensible registry, selective signals, catalog APIs |
| GitHub Analyzer | ✅ Implemented | Public repo count, repo metadata, recent activity, profile verification |
| Academic Analyzer | ✅ Implemented | CGPA/CPI normalization, academic year/batch, scale checks |
| **Resume Analyzer** | ✅ Implemented | **12 signals**, PDF & DOCX extraction, SSRF security, direct upload API |
| Portfolio Analyzer | 🔲 Staged Contract | `PortfolioAnalyzerContract` registered as planned capability |
| Eligibility rules (Prompt 4) | 🔲 Staged Schema | Boundary contracts in place; implementation ready |
| Scoring engine (Prompt 5) | 🔲 Staged Schema | Criteria schemas defined; evaluation planned |
| Aggregation (Prompt 5) | 🔲 Not started | Planned with scoring engine |
| Ranking & Selection (Prompt 6) | 🔲 Not started | Planned after aggregation |
| React frontend (Prompt 7) | 🔲 Not started | Planned after backend completion |

---

## 🔍 Signal Extraction Framework

### How the Registry Works

The extraction framework uses a centralized `SignalExtractorRegistry` where independent analyzers register themselves via `BaseSignalExtractor`.

1. **Self-Describing Descriptors**: Each analyzer exposes an `ExtractorDescriptor` declaring:
   - `extractor_id`: Unique identifier (e.g. `github_analyzer`, `academic_metrics`).
   - `category`: Broad category (e.g. `technical`, `academic`).
   - `produced_signals`: List of supported signal keys.
   - `signals`: Detailed `SignalDefinition` models (name, description, value_type, unit).
   - `required_inputs` & `optional_inputs`: Input field dependencies.
   - `optional_config`: Supported configuration parameters.
2. **Category & Signal Grouping**: Organizers can browse categories and individual signals, enabling entire categories or picking individual signals.
3. **Selective Execution**: Calling `execute_extraction(teams, selected_signals)` only runs analyzers associated with the chosen signals, and analyzers only calculate the requested signals.
4. **Fault Isolation**: If one candidate has an invalid GitHub handle or missing academic record, that specific signal receives `FAILED` or `NOT_APPLICABLE`. The analyzer continues processing other members and other signals.
5. **Missing-Data Integrity**: Missing inputs **never silently convert to 0**. They receive `SignalStatus.NOT_APPLICABLE` with explicit evidence.

### Implemented Signals

#### 1. GitHub Analyzer (`github_analyzer`)
Category: `technical` (displayed as *Technical & GitHub*)

- **`github_public_repo_count`** (`integer`): Total count of public repositories on the candidate's GitHub profile.
- **`github_repo_metadata`** (`dict`): Verifiable repository metadata including total stars, total forks, primary programming languages, and top 5 repositories.
- **`github_recent_activity`** (`dict`): Verifiable public activity metrics including recent public events count, push event count, commit count, and 90-day activity flag.
- **`github_profile_verified`** (`boolean`): Confirms that the profile exists and is publicly accessible.

*Input acceptance*: Supports full URLs (`https://github.com/username`), short URLs (`github.com/username`), `@username`, or plain usernames.

#### 2. Academic Analyzer (`academic_metrics`)
Category: `academic` (displayed as *Academics*)

- **`academic_cgpa`** (`float`): Extracted and validated CGPA, CPI, or GPA numeric score. Preserves original scale and raw source input.
- **`academic_year`** (`string`): Normalized academic year of study (e.g. `"1st Year"`, `"2nd Year"`, `"3rd Year"`, `"4th Year"`, `"Postgraduate"`) or graduation batch (e.g. `"Batch 2026"`).
- **`normalized_cgpa_10_scale`** (`float`): Score normalized to a standard 10-point scale. Per project specifications, converting between scales (e.g. 4.0 scale to 10.0 scale) requires explicit configuration (`{"allow_scale_conversion": True}`).

*Dynamic mapping support*: Reads canonical `cgpa` and `academic_year` or custom organizer column names configured via `cgpa_field` / `academic_year_field`.

#### 3. Resume Analyzer (`resume_signal_extractor`)
Category: `experience` (displayed as *Experience & Projects*)

Extracts technical background, projects, work experience, and educational credentials from candidate resume documents.

- **`resume_extracted_skills`** (`dict`): Comprehensive skill catalog containing `languages`, `frameworks`, `databases`, `tools`, `all_skills`, and `total_skills_count`.
- **`resume_programming_languages`** (`list`): Programming languages identified in the resume (e.g. `["Go", "Python", "TypeScript", "C++"]`).
- **`resume_frameworks_libraries`** (`list`): Web frameworks, machine learning libraries, and UI toolkits (e.g. `["FastAPI", "React", "PyTorch"]`).
- **`resume_databases`** (`list`): Relational and NoSQL databases, search engines, and data stores (e.g. `["PostgreSQL", "Redis", "MongoDB"]`).
- **`resume_tools_technologies`** (`list`): Developer tools, cloud platforms, container platforms, and CI/CD tools (e.g. `["Docker", "Kubernetes", "AWS", "Git"]`).
- **`resume_projects`** (`list`): Self-reported projects with `name`, `technologies`, `description`, `evidence`, and `verified: False`.
- **`resume_education`** (`dict`): Academic credentials including `degree`, `degree_short`, `institution`, `graduation_year`, and `gpa`.
- **`resume_degree_level`** (`string`): Canonical degree level (e.g. `"B.Tech"`, `"B.E."`, `"M.Tech"`, `"Ph.D."`).
- **`resume_experience`** (`list`): Internships and employment history with `role`, `organization`, `duration`, `description`, and `evidence`.
- **`resume_experience_years`** (`float`): Estimated duration of technical experience in years (unit: `years`), computed with month-level precision, active 'Present' duration calculation, and overlapping interval merging.
- **`resume_certifications_achievements`** (`list`): Certifications, hackathon placements (`Winner`, `Runner-up`, `Finalist`, `Champion`, `1st Place`), and honors with stripped bullet prefixes.
- **`resume_external_links`** (`dict`): Professional links grouped by `github_urls`, `linkedin_urls`, `portfolio_urls`, `competitive_programming_urls`, and `other_urls`.

*Input methods supported*:
- Direct multipart file uploads via `POST /api/signals/extract-resume` (`.pdf` and `.docx`).
- Remote URLs (`member.resume_url` or mapped form column).
- Raw bytes passed via `custom_fields["resume_bytes"]`.

*Document safety & security controls*:
- **Local-File Security Policy**: Local paths, `file://` URIs, and UNC network shares (`\\server\share`, `//server/share`) are strictly blocked by default (`allow_local_files` defaults to `False`), returning `SignalStatus.FAILED` with a generic message without touching the filesystem or leaking file existence. Local file access is only enabled when explicitly configured with `{"allow_local_files": True}` (UNC network shares remain blocked).
- **SSRF & DNS Rebinding Defense**: Pre-connection resolution validates that all resolved addresses are globally routable (`ip.is_global`), blocking loopback (`127.0.0.0/8`, `::1`), private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local, Carrier-Grade NAT (`100.64.0.0/10`), and cloud metadata IPs (`169.254.169.254`). Ports are strictly restricted to `{80, 443}` (rejecting 8080/8443). `SSRFSafeNetworkBackend` re-validates the connected peer socket IP at connect time to prevent DNS rebinding attacks, and HTTP redirects are strictly rejected.
- **Non-Blocking I/O**: Synchronous extraction work is executed via `starlette.concurrency.run_in_threadpool`, ensuring long PDF parses or downloads do not block the event loop or freeze `/api/health`.
- **Dynamic Confidence Scoring**: Replaces static values with evidence-calibrated confidence in `[0.0, 1.0]` across all 12 signals based on document length quality and evidence strength (e.g. `degree_and_institution_found`, `dated_experience_entries`, `validated_urls_with_recognized_domains`). The rule applied is recorded in `metadata["confidence_rule"]`.
- **Resource Protection & Fault Isolation**: Enforces a 10 MB file-size limit and 10.0s connection timeouts. Corrupted, encrypted, empty, or unreadable documents fail gracefully without halting other team members or other analyzers.
- **Provenance Tracking**: All resume signals carry `SignalEvidence` with `provenance: "self_reported_resume"` and `verified: False` to maintain a clear boundary from verified external profile APIs.

### How to Register a Future Analyzer

To add a new analyzer:

```python
from app.schemas.ingestion import MemberSchema
from app.signals.base import BaseSignalExtractor
from app.signals.schemas import (
    ExtractedSignal,
    ExtractorDescriptor,
    SignalDefinition,
    SignalStatus,
)

class MyCustomAnalyzer(BaseSignalExtractor):
    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="my_custom_analyzer",
            name="My Custom Analyzer",
            description="Analyzes custom domain metrics.",
            category="custom_category",
            required_inputs=["my_input_field"],
            produced_signals=["custom_metric_key"],
            signals=[
                SignalDefinition(
                    signal_key="custom_metric_key",
                    name="Custom Metric",
                    description="Measures specific candidate signal.",
                    category="custom_category",
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
        # Perform extraction safely
        ...
```

Register it in `app.signals.registry` without changing core execution logic:

```python
default_signal_registry.register(MyCustomAnalyzer())
```

---

## 📡 Signal Extraction API Endpoints

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| `GET` | `/api/signals/catalog` | Complete catalog of categories, analyzers, and supported signals |
| `GET` | `/api/signals/categories` | List all available signal categories |
| `GET` | `/api/signals/analyzers` | List metadata descriptors of all registered analyzers |
| `GET` | `/api/signals/signals` | List all individual evaluation signals |
| `POST` | `/api/signals/extract` | Run selective extraction on pre-parsed team structures |
| `POST` | `/api/signals/extract-file` | Upload CSV/JSON and run selective signal extraction in one step |
| `POST` | `/api/signals/extract-resume` | Direct upload of a candidate's PDF or DOCX resume document |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+ (tested with Python 3.12)

### Backend Setup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (cmd):
venv\Scripts\activate.bat
# macOS / Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Environment configuration (optional)
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 6. Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Variables

Configuration is loaded from environment variables or `.env`:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `APP_ENV` | `development` | Application environment (`development` / `production`) |
| `APP_DEBUG` | `true` | Debug mode |
| `APP_HOST` | `0.0.0.0` | Host binding |
| `APP_PORT` | `8000` | Port binding |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum upload file size |
| `GITHUB_TOKEN` | *None* | Optional GitHub Personal Access Token (increases rate limit from 60 to 5,000 req/hr) |
| `GITHUB_API_BASE_URL` | `https://api.github.com` | GitHub API base URL (overridable for testing) |
| `GITHUB_REQUEST_TIMEOUT`| `10.0` | Request timeout in seconds for GitHub API calls |

### Running Tests

Run the complete automated test suite locally:

```bash
# From workspace root
.\backend\venv\Scripts\python.exe -m pytest backend -v

# Or from backend directory with activated venv:
pytest -v
```

The test suite includes **126 automated tests** with 100% pass rate:
- **`backend/tests/test_ingestion.py`** (47 tests): CSV/JSON ingestion, header discovery, dynamic form mapping, custom field preservation, and validation.
- **`backend/tests/test_duplicate_teams_regression.py`** (15 tests): Duplicate team name detection, automatic ID generation, temporary non-merging IDs (`TEMP_TEAM_...`), and warning generation.
- **`backend/tests/test_signals.py`** (39 tests): Extensible signal registry, catalog discovery, GitHub API analysis, Academic CGPA/batch normalization, and cross-analyzer fault isolation.
- **`backend/tests/test_resume_analyzer.py`** (25 tests): PDF & DOCX text parsing, all 12 resume signals, SSRF security defenses, size limits, direct file upload endpoint, and multi-analyzer compatibility.

All external HTTP calls in the test suite are mocked; no real GitHub API tokens or external network access are required.

---

## ⚠️ Current Limitations & Next Steps

1. **Next Milestone (Prompt 4 - Configurable Eligibility Rules & Hard Filters)**: Implementing organizer-defined eligibility rules (minimum CGPA, required programming languages, degree requirements, minimum experience) evaluated before weighted scoring.
2. **Scoring Engine & Team Aggregation (Prompt 5)**: Composite weighted scoring, missing-data strategies, and team-level score aggregation are staged as schemas in `app.scoring.schemas`.
3. **Future AI Resume Analyzer**: An architectural audit confirmed that an advanced external AI/LLM resume provider can be plugged in via strategy pattern without altering existing signal contracts or downstream scoring.
4. **Database Persistence**: Currently in-memory and request/response-based. Relational database persistence will be introduced in a future milestone.
5. **GitHub Unauthenticated Rate Limits**: Unauthenticated calls to GitHub API are limited to 60 requests per hour per IP. Set `GITHUB_TOKEN` in `.env` for production workloads to achieve 5,000 req/hr.
