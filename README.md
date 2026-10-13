# Team Recruitment Automation Tool

Configurable and explainable hackathon team shortlisting system.

---

## 🎯 Problem

Hackathon organizers receive hundreds of team registrations and need to **shortlist the top X teams** fairly and transparently. Manual review is slow, inconsistent, and opaque. This tool automates the process with dynamic registration form support, selective signal extraction, configurable eligibility rules, weighted scoring, and human-readable explanations for every decision.

## ✨ Key Features

- **CSV / JSON ingestion** – upload registration data in common formats with dynamic form discovery.
- **Dynamic schema mapping** – map custom organizer column names to canonical target fields without code changes.
- **Arbitrary field preservation** – unmapped form fields and raw records are safely preserved in `custom_fields` and `raw_data`.
- **Extensible signal extraction** – pluggable analyzers for GitHub activity, academics, and future data sources.
- **Selective signal execution** – organizers can select broad categories or individual signals without running unneeded analyzers.
- **Verifiable evidence & audit trails** – all extracted signals include provenance, raw inputs, timestamps, and confidence scores.
- **Fault-isolated multi-team evaluation** – failure or missing data for one member or signal never halts execution of others.
- **Variable team sizes** – handle teams of any size without hard-coded member limits.
- **Scoring separation** – extraction remains cleanly decoupled from scoring rules, weighting, and ranking.

## 🛠️ Technology Stack

| Layer     | Technology                       |
| --------- | -------------------------------- |
| Backend   | Python 3.10+ · FastAPI · Pydantic v2 |
| Server    | Uvicorn                          |
| Data      | Pandas                           |
| HTTP / API| HTTPX                            |
| Testing   | Pytest · Starlette TestClient    |
| Frontend  | React + Vite *(planned)*         |
| Database  | PostgreSQL *(planned)*           |

## 📐 High-Level Processing Workflow

```
Registration Data (CSV/JSON)
        │
        ▼
   ┌──────────┐
   │ Ingestion │  ──▶  Parse & map dynamic form columns
   └──────────┘
        │
        ▼
   ┌────────────┐
   │ Validation  │  ──▶  Structural integrity checks & presence tracking
   └────────────┘
        │
        ▼
   ┌──────────────────┐
   │ Signal Extraction │  ──▶  Selective analyzer execution per member
   └──────────────────┘
        │
        ▼
   ┌────────────────┐
   │ Eligibility Rules │  ──▶  Apply configurable pass/fail criteria (Milestone 3)
   └────────────────┘
        │
        ▼
   ┌─────────┐
   │ Scoring  │  ──▶  Weighted scoring per member (Milestone 4)
   └─────────┘
        │
        ▼
   ┌─────────────┐
   │ Aggregation  │  ──▶  Combine member signals → team score (Milestone 5)
   └─────────────┘
        │
        ▼
   ┌─────────┐
   │ Ranking  │  ──▶  Sort & select top X teams (Milestone 6)
   └─────────┘
        │
        ▼
   ┌─────────────┐
   │ Explanation  │  ──▶  Generate human-readable score breakdowns (Milestone 7)
   └─────────────┘
        │
        ▼
   ┌────────┐
   │ Export  │  ──▶  CSV / JSON download (Milestone 8)
   └────────┘
```

## 📦 Current Implementation Status

| Component            | Status          | Details |
| -------------------- | --------------- | ------- |
| Project structure    | ✅ Done          | Clean architectural layer separation |
| FastAPI app skeleton | ✅ Done          | Application instance & health check |
| Ingestion & Discovery| ✅ Done          | CSV/JSON upload, field discovery, schema mapping |
| Dynamic form mapping | ✅ Done          | Preserves arbitrary custom fields, tracks missing states |
| Signal Extraction    | ✅ Implemented   | Extensible registry, selective signals, GitHub & Academic analyzers |
| GitHub Analyzer      | ✅ Implemented   | Public repo count, repo metadata, recent activity, verification |
| Academic Analyzer    | ✅ Implemented   | CGPA/CPI, academic year/batch, scale checks, column mapping |
| Resume Analyzer      | 🔲 Staged Contract | ResumeParserContract registered for Milestone 3 |
| Portfolio Analyzer   | 🔲 Staged Contract | PortfolioAnalyzerContract registered |
| Eligibility rules    | 🔲 Staged Schema | Boundary contracts in place |
| Scoring engine       | 🔲 Staged Schema | Criteria schemas defined; evaluation planned |
| Aggregation          | 🔲 Not started  | Planned after scoring engine |
| Ranking              | 🔲 Not started  | Planned after aggregation |
| React frontend       | 🔲 Not started  | Planned after backend completion |

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

### How to Register a Future Analyzer

To add a new analyzer (such as the upcoming Resume parser):

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

All external HTTP calls in the test suite are mocked; no real GitHub API tokens or network access are required.

---

## ⚠️ Current Limitations & Next Steps

1. **Resume Analysis**: Staged as `ResumeParserContract`. Resume PDF/Word text parsing will be implemented in the next milestone using the extraction framework.
2. **Scoring Engine**: Composite weighted scoring and threshold evaluation are maintained as contracts in `app.scoring.schemas`. Scoring rules and team ranking are deliberately decoupled from extraction.
3. **Database Persistence**: Currently in-memory / response-based. Relational database persistence will be introduced in a future milestone.
4. **GitHub Unauthenticated Rate Limits**: Unauthenticated calls to GitHub API are limited to 60 requests per hour per IP. Set `GITHUB_TOKEN` in `.env` for production workloads to achieve 5,000 req/hr.
