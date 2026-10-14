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
- **Deterministic eligibility evaluation** – 3-state classification (`ELIGIBLE`, `INELIGIBLE`, `NEEDS_REVIEW`) with human-readable explanations for every rule.
- **10 spec-compliant rule evaluators** – team size limits, required links, signal presence, generic signal thresholds, keyword containment, allowed categorical values, track distribution caps, cross-team email duplicates, and mandatory fields.
- **Universal threshold & 5 aggregation strategies** – numeric safety rejecting bools/NaN/inf, preserving zero, supporting all 5 aggregations (`all`, `any`, `min`, `max`, `mean`).
- **Configurable weighted scoring & team aggregation** – relative weight normalization, normalization methods (linear min-max, boolean, categorical), member aggregation (mean, min, max, clamped sum, lead_only, top_k), explicit missing-data policies, and exact score reconciliation.
- **Configuration versioning & manual organizer overrides** – immutable configuration version history, historic run auditing, and reason-backed manual eligibility overrides.
- **Fault-isolated multi-team evaluation** – failure or missing data for one member or signal never halts execution of others.
- **Variable team sizes** – handle teams of any size without hard-coded member limits.
- **Scoring separation** – extraction, eligibility filtering, and scoring remain cleanly decoupled from ranking and top-X selection.

## 🛠️ Technology Stack

| Layer          | Technology                                   |
| -------------- | -------------------------------------------- |
| Backend        | Python 3.10+ · FastAPI · Pydantic v2         |
| Server         | Uvicorn                                      |
| Data           | Pandas                                       |
| HTTP / API     | HTTPX                                        |
| Document Parsers | PyPDF (`pypdf`) · Python-Docx (`python-docx`) |
| Testing        | Pytest · Starlette TestClient (256 tests)    |
| Frontend       | React + Vite *(planned)*                     |
| Database       | PostgreSQL *(planned)*                       |

## 🗺️ Project Roadmap

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Phase 1** | Backend foundation, architectural structure, and base configuration | ✅ Completed |
| **Phase 2** | CSV/JSON ingestion, dynamic form mapping, and validation | ✅ Completed |
| *Phase 2.1 / 3.2* | Auto-ID generation for missing IDs, CGPA scale preservation | ✅ Completed |
| *Phase 3.3* | Duplicate team name detection, temporary IDs, and ambiguous team warnings | ✅ Completed |
| **Phase 3** | Evaluation signal extraction framework, GitHub analyzer, and Academic analyzer | ✅ Completed |
| *Phase 3.1 (Milestone)* | **Resume Analyzer**: PDF/DOCX parsing, SSRF security, 12 signals, direct file upload | ✅ Completed |
| **Phase 4** | Configurable eligibility rules and hard filters (Rules Engine) | ✅ Completed |
| **Phase 5** | Weighted scoring and team-level aggregation (Scoring Engine) | ✅ Completed |
| **Phase 6** | Ranking, top-X selection, and human-readable explanations | 🔲 *Next Up* |
| **Phase 7** | Frontend integration and organizer dashboard | 🔲 Planned |
| **Phase 8** | End-to-end testing and final improvements | 🔲 Planned |

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
| **Eligibility Rules Engine (Phase 4)** | ✅ Implemented | **10 rule types**, universal threshold evaluator (5 aggregations), cross-team duplicate detection, track caps, config versioning, manual overrides, and audit trails |
| **Weighted Scoring Engine (Phase 5)** | ✅ Implemented | Relative weight normalization, criteria normalizations (numeric range, boolean, categorical), 6 aggregation methods, explicit missing-data policies, audit runs |
| Portfolio Analyzer | 🔲 Staged Contract | `PortfolioAnalyzerContract` registered as planned capability |
| Ranking & Selection (Phase 6) | 🔲 Not started | Planned after scoring engine |
| React frontend (Phase 7) | 🔲 Not started | Planned after backend completion |

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

## ⚖️ Configurable Eligibility Rules Engine (Phase 4)

Stage 4 of the recruitment pipeline evaluates candidate teams and their extracted signals against configurable rule sets to produce deterministic eligibility classifications.

### Core Architecture & Evaluation Semantics

1. **3-State Deterministic Classification**:
   - `ELIGIBLE`: Team satisfies all hard constraints (and any advisory soft rules).
   - `INELIGIBLE`: Team violates one or more hard constraints (`RuleSeverity.HARD`).
   - `NEEDS_REVIEW`: One or more hard constraints encountered missing data or an ambiguous state that resolved to `manual_review`, and no hard rules failed.
2. **Hard vs. Soft Constraints**:
   - **Hard (`RuleSeverity.HARD`)**: Disqualifies the team upon failure.
   - **Soft (`RuleSeverity.SOFT`)**: Advisory constraint. Generates warnings and human-readable feedback without disqualifying the team.
3. **Missing Data Semantics**:
   - **NOT PROVIDED (`FAILED`)**: A required field or signal is known/expected in the registration form or signal registry but was left blank or empty by the candidate (or signal extraction status is `NOT_APPLICABLE`). Fails the rule.
   - **UNAVAILABLE (`on_missing`)**: Data could not be determined due to an unmapped form column, an analyzer execution failure, an unsupplied signals payload, or missing member data in an aggregation. Triggers the rule's configured `on_missing` action (`fail`, `pass`, `manual_review`).
4. **Transparent Explanations**: Every evaluated rule generates an explicit, human-readable reason detailing evaluated values, thresholds, and missing-data actions.

### The 10 Official Rule Evaluators

| Rule Type | Scope | Parameters | Description |
| :--- | :--- | :--- | :--- |
| **`team_size_min`** | `team` | `min_size` (int) | Enforces minimum team size; empty teams fail automatically. |
| **`team_size_max`** | `team` | `max_size` (int) | Enforces maximum team size limit. |
| **`required_link`** | `member` | `link_field` (str), `member_selection` | Verifies member provided a required profile or portfolio URL. |
| **`required_signal_present`** | `member` | `signal_key` (str), `member_selection` | Ensures an extracted signal exists and was successfully extracted. |
| **`signal_threshold`** | `member` | `signal_key`, `operator`, `threshold`, `member_selection`, `aggregation` | Evaluates numeric signal conditions with boundary safety and 5 aggregation strategies. |
| **`signal_contains`** | `member` | `signal_key`, `expected_item`, `case_sensitive` | Checks for required keywords or items in list, dict, or string signals. |
| **`allowed_values`** | `member` / `team` | `field_key` or `signal_key`, `allowed_values` (list) | Validates categorical values (e.g. tracks, batches, degrees) against a whitelist. |
| **`track_limit`** | `cross_team` | `track_limits` (dict), `field_key` | Caps total team registrations admitted into specific challenge tracks. |
| **`duplicate_member_email`**| `cross_team` | — | Cross-team duplicate candidate email detection with case/whitespace normalization. |
| **`required_fields_present`**| `member` | `field_keys` (list[str]), `member_selection` | Verifies mandatory registration form questions were completed. |

### Universal Threshold Evaluator & Aggregations

The `signal_threshold` evaluator provides a unified engine across all numeric signals (e.g. `github_public_repo_count`, `academic_cgpa`, `resume_experience_years`):
- **Operators**: Supports `>=`, `>`, `<=`, `<`, `==`, `!=`.
- **Member Selection**: Targets `all_members`, `any_member`, or `team_lead`.
- **5 Reductions**:
  - `all`: All selected members must meet the threshold condition.
  - `any`: At least one selected member must meet the threshold condition.
  - `min`: Compares `min(member_values)` against threshold.
  - `max`: Compares `max(member_values)` against threshold.
  - `mean`: Compares `sum(member_values) / len(member_values)` against threshold.
- **Strict Numeric Safety**:
  - Rejects booleans (`True` / `False`), `NaN`, and `inf` as invalid (`UNAVAILABLE`).
  - Preserves legitimate numeric zero (`0`, `0.0`) as valid data.
  - Reductions never silently drop missing member values; incomplete data triggers `on_missing`.

### Cross-Team Duplicate Member Detection

The `duplicate_member_email` evaluator inspects candidate emails across the entire registration pool:
- Normalizes emails (trimming whitespace and lowercasing).
- Skips blank or null emails.
- Ignores repeated emails on the *same* team.
- Identifies candidates registered across multiple distinct teams, naming conflicting team IDs in the diagnostic explanation.
- Results are deterministic and independent of input team ordering.

### Configuration Versioning & Manual Overrides

- **Immutable Configurations**: Configurations are versioned with auto-incrementing integers (`v1`, `v2`, ...). Previous versions remain permanently queryable via `?version=<n>`.
- **Audit Trails**: Every evaluation run records its execution timestamp, active configuration ID and version, and evaluation results.
- **Manual Overrides**: Organizers can override team decisions with mandatory justification notes. Overrides preserve the original evaluation outputs and are merged transparently upon retrieval.
- **Pre-Configured Presets**: Includes `basic`, `strict`, and `open_solo` presets. Per security & stability standards, no preset includes hard rules dependent on resume-extracted signals.

---

## 📡 Eligibility Engine API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/rules/catalog` | Catalog of all 10 rule types, parameter definitions, and supported options |
| `GET` | `/api/rules/configs` | List latest versions of all stored rule configurations |
| `POST` | `/api/rules/configs` | Create a new validated rule configuration (starts at version 1) |
| `GET` | `/api/rules/configs/{config_id}` | Fetch a configuration (latest or specific `?version=n`) |
| `PUT` | `/api/rules/configs/{config_id}` | Update configuration with validation; creates new immutable version |
| `GET` | `/api/rules/configs/{config_id}/versions` | List all historical version numbers for a configuration |
| `POST` | `/api/rules/evaluate` | Evaluate teams against a rule configuration; returns eligibility results |
| `GET` | `/api/rules/runs/{run_id}` | Retrieve evaluation run results with merged manual overrides |
| `POST` | `/api/rules/runs/{run_id}/override` | Apply an organizer manual override to a team result |

---

## 📊 Configurable Weighted Scoring & Team Aggregation (Phase 5)

Stage 5 of the recruitment pipeline computes transparent, explainable composite scores in `[0.0, 100.0]` for candidate teams based on configurable criteria, normalization models, and member-to-team aggregation methods.

### Core Architecture & Calculation Formula

1. **Relative Weight Normalization**:
   Organizers define non-negative weights for enabled criteria without needing them to total 1.0 or 100. The engine normalizes weights proportionally over applicable criteria:
   $$w'_c = \frac{w_c}{\sum_{j \in \text{applicable}} w_j}$$
2. **Score Calculation**:
   For each applicable criterion $c$, its weighted contribution toward the final score is:
   $$\text{contribution}_c = S_c \times w'_c \times \text{scale\_max}$$
   where $S_c \in [0.0, 1.0]$ is the aggregated team criterion score. The composite team score is:
   $$\text{final\_score} = \sum_{c \in \text{applicable}} \text{contribution}_c$$
   Reconciliation is exact: $\sum \text{contribution}_c == \text{final\_score}$ (subject only to documented 2-decimal output rounding).

### Normalization Methods

- **Linear Min-Max (`numeric_range`)**: Clamps raw values to $[min, max]$ and scales linearly: $(v - min) / (max - min) \in [0.0, 1.0]$. Strict numeric safety rejects `bool`, `NaN`, and `inf` while validating legitimate numeric zero (`0`, `0.0`).
- **Boolean Mapping (`boolean`)**: Maps `True` &rarr; `true_score` (default 1.0) and `False` &rarr; `false_score` (default 0.0). Missing booleans are never conflated with False.
- **Categorical Mapping (`categorical`)**: Explicit dictionary lookup mapping string values (e.g. academic batches or degree levels) to scores in $[0.0, 1.0]$, with optional default fallback.

### Member-to-Team Aggregations

Combines member-level normalized scores $s_i$ into a team criterion score $S_c$:
- **`mean`**: Average valid member scores: $\sum s_i / N$.
- **`min`**: Lowest valid member score in team.
- **`max`**: Highest valid member score in team (e.g. strongest developer).
- **`sum`**: Clamped sum of valid scores: $\min(1.0, \sum s_i)$ preventing team scores from exceeding bounds.
- **`lead_only`**: Evaluates only the designated team lead (identified via `lead_field`).
- **`top_k`**: Averages the highest $K$ valid member scores: $\sum_{j=1}^{\min(K, N)} s_j / \min(K, N)$.

### Missing Data Policies

- **`EXCLUDE_AND_RENORMALIZE`**: Drops the missing criterion from the denominator and renormalizes the remaining applicable criterion weights. If all criteria are missing, returns `NO_SCORE` rather than an invented zero.
- **`ZERO_SCORE`**: Retains the criterion in the denominator and assigns an imputed score of $0.0$, recording the policy justification in the audit breakdown.

### Eligibility Integration & Auditing

- Operates as a pure downstream stage: Scoring evaluates candidate fitness without modifying eligibility decisions.
- If eligibility outcomes are provided (`ELIGIBLE`, `INELIGIBLE`, `NEEDS_REVIEW`), they are preserved in the scoring result.
- Organizers can configure `score_ineligible_teams: bool` (default True for informational scoring, or False to assign `0.0` with a `DISQUALIFIED` status).

---

## 📡 Scoring Engine API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/scoring/catalog` | Catalog of criterion types, normalization methods, aggregations, and missing-data policies |
| `GET` | `/api/scoring/configs` | List latest versions of all stored scoring configurations |
| `POST` | `/api/scoring/configs` | Create a new validated scoring configuration (starts at version 1) |
| `GET` | `/api/scoring/configs/{config_id}` | Fetch a configuration (latest or specific `?version=n`) |
| `PUT` | `/api/scoring/configs/{config_id}` | Update configuration with validation; creates new immutable version |
| `GET` | `/api/scoring/configs/{config_id}/versions` | List all historical version numbers for a scoring configuration |
| `POST` | `/api/scoring/evaluate` | Evaluate teams against a scoring configuration; returns full score breakdowns |
| `GET` | `/api/scoring/runs/{run_id}` | Retrieve a recorded scoring run with all team breakdowns and audit logs |

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

The test suite includes **256 automated tests** with 100% pass rate:
- **`backend/tests/test_ingestion.py`** (47 tests): CSV/JSON ingestion, header discovery, dynamic form mapping, custom field preservation, and validation.
- **`backend/tests/test_duplicate_teams_regression.py`** (15 tests): Duplicate team name detection, automatic ID generation, temporary non-merging IDs (`TEMP_TEAM_...`), and warning generation.
- **`backend/tests/test_signals.py`** (39 tests): Extensible signal registry, catalog discovery, GitHub API analysis, Academic CGPA/batch normalization, and cross-analyzer fault isolation.
- **`backend/tests/test_resume_analyzer.py`** (45 tests): PDF & DOCX text parsing, all 12 resume signals, SSRF security defenses, size limits, direct file upload endpoint, and multi-analyzer compatibility.
- **`backend/tests/test_eligibility.py`** (22 tests): Eligibility engine foundation, catalog schemas, configuration versioning, missing data contradiction resolution, numeric safety, team lead resolution, and manual overrides.
- **`backend/tests/test_eligibility_spec.py`** (52 tests): Specification compliance for all 10 rule types, threshold operators, boundary conditions, all 5 aggregation reductions, cross-team email duplicates, fault isolation, determinism, and HTTP 422 configuration validation.
- **`backend/tests/test_scoring.py`** (36 tests): Configurable scoring criteria, relative weight normalization, min-max/boolean/categorical normalization, 6 member-to-team aggregations, missing data policies (exclude and renormalize, zero score), confidence adjustment, eligibility integration, and API endpoints.

All external HTTP calls in the test suite are mocked; no real GitHub API tokens or external network access are required.

---

## ⚠️ Current Limitations & Next Steps

1. **Next Milestone (Phase 6 - Ranking, Top-X Selection & Explanations)**: Implementing multi-attribute sorting, tie-breaking rules, quota/diversity enforcement, Top-X shortlisting, and natural language summary generation.
2. **Frontend Integration & Organizer Dashboard (Phase 7)**: React + Vite web application with interactive CSV upload, signal selection, eligibility rule builder, scoring criteria weights slider, and live ranking leaderboard.
3. **Future AI Resume Analyzer**: An architectural audit confirmed that an advanced external AI/LLM resume provider can be plugged in via strategy pattern without altering existing signal contracts or downstream scoring.
4. **Database Persistence**: Currently in-memory and request/response-based. Relational database persistence will be introduced in a future milestone.
5. **GitHub Unauthenticated Rate Limits**: Unauthenticated calls to GitHub API are limited to 60 requests per hour per IP. Set `GITHUB_TOKEN` in `.env` for production workloads to achieve 5,000 req/hr.
