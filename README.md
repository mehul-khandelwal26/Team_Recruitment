# Team Recruitment Automation Tool

Configurable and explainable hackathon team shortlisting system.

---

## 🎯 Problem

Hackathon organizers receive hundreds of team registrations and need to **shortlist the top X teams** fairly and transparently. Manual review is slow, inconsistent, and opaque. This tool automates the process with dynamic registration form support, selective signal extraction, configurable eligibility rules, weighted scoring, and human-readable explanations for every decision.

## ✨ Key Features

- **CSV / JSON ingestion** – upload registration data in common formats (JSON root must be an array of team objects: `[{"team_name": ..., "members": [...]}]`, not a bare object) with dynamic form discovery.
- **Dynamic schema mapping & custom signals** – map organizer column names to canonical target fields or custom signal identifiers (`custom:<signal_name>`) with zero code changes.
- **Smart multi-candidate discovery & alias confidence ranking** – two-pass confidence-ranked column discovery disambiguates competing candidates (e.g., `github_url` vs `github_id`), prioritizing exact link targets (1.0 confidence) over handles (0.8 confidence) and supporting aliases (`github_link`, `cv_link`) at 0.9 confidence with zero false conflicts.
- **Custom mapping & miscellaneous signals engine** – lifts custom CSV fields (e.g. `skills`, `track`, `certifications`) into first-class `ExtractedSignal` objects, enabling direct rule evaluation (`signal_contains`, `signal_threshold`, `required_signal_present`) and multi-criteria scoring rubrics (categorical mappings, weights, and shares).
- **Context-aware ingestion warnings filter** – suppresses false-alarm warnings for uncollected optional profile fields (e.g., `portfolio_url` when no portfolio column was provided) while surfacing true format anomalies with a collapsible "Show all (X)" viewer.
- **Enterprise numeric input UX** – all numeric form fields (rules parameters, scoring weights, scale max, and shortlist cutoffs) support seamless backspacing without snapping to 1, and automatically strip leading zeros (`09` -> `9`).
- **Missing ID generation & duplicate team handling** – autogenerates missing member/team IDs, detects ambiguous duplicate team names, assigns non-merging temporary IDs (`temp_team_...`), disambiguates colliding cross-team member IDs, and surfaces actionable organizer warnings.
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
- **Deterministic Top-X ranking & explainable shortlisting (Phase 6)** – 3-level deterministic ranking, tiebreak criteria, boundary cutoff tie protection, shortage diagnostics, review candidate suggestions, and full scoring breakdown preservation.
- **Interactive web dashboard & evaluation workflow (Phase 7)** – full React 18 + Vite frontend with Editorial Enterprise design system, live metrics dashboard, 5-stage evaluation wizard, interactive results leaderboard with manual reviewer overrides, scoring weight editors with dynamic share calculations, and immutable configuration version history.

## 🛠️ Technology Stack

| Layer          | Technology                                   |
| -------------- | -------------------------------------------- |
| Backend        | Python 3.10+ · FastAPI · Pydantic v2         |
| Server         | Uvicorn                                      |
| Data           | Pandas                                       |
| HTTP / API     | HTTPX                                        |
| Document Parsers | PyPDF (`pypdf`) · Python-Docx (`python-docx`) |
| Testing        | Pytest · Starlette TestClient (459 tests, 100% pass) |
| Database       | PostgreSQL (Neon Cloud) · SQLAlchemy 2.0 · Alembic · Psycopg 3 |
| Frontend       | React 18 · TypeScript · Vite · Tailwind CSS · shadcn/ui · React Router v6 · TanStack Query v5 · Lucide React |

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
| **Phase 6** | Ranking, top-X selection, and human-readable explanations | ✅ Completed |
| **Database Phase** | Persistent PostgreSQL storage on Neon (8 stores, Alembic migration, safety checks, ID-only pipeline, CSV export) | ✅ Completed |
| **Phase 7** | Frontend integration, live dashboard, evaluation wizard, results leaderboard & reviewer workflow, configuration manager | ✅ Completed |
| **Phase 8** | End-to-end testing, production deployment containerization, and authentication gateway | ✅ Completed |

---

## 📦 Current Implementation Status

| Component | Status | Details |
| :--- | :--- | :--- |
| Project structure | ✅ Done | Clean architectural layer separation |
| FastAPI app skeleton | ✅ Done | Application instance, health check, CORS, router mounts |
| Ingestion & Discovery | ✅ Done | CSV/JSON upload, dynamic header discovery, schema mapping |
| Missing ID generation | ✅ Done | Generates missing Team/Member IDs without overwriting explicit IDs |
| Duplicate team detection | ✅ Done | Detects same-name teams, assigns temporary IDs (`temp_team_...`), preserves separation |
| Dynamic form mapping | ✅ Done | Preserves arbitrary custom fields, tracks missing states |
| **Custom Signals & Misc Engine** | ✅ Implemented | `custom:*` prefix mapping, dynamic extraction to `ExtractedSignal`, rule validation, and scoring integration |
| **Confidence-Ranked Discovery** | ✅ Implemented | Two-pass candidate disambiguation (`github_url` vs `github_id`), alias support (`github_link`), 0 false conflicts |
| **Warning Filter & Viewer** | ✅ Implemented | Suppresses phantom warnings for uncollected profile links; collapsible "Show all (X)" review toggle |
| Signal Extraction Framework | ✅ Implemented | Extensible registry, selective signals, catalog APIs |
| GitHub Analyzer | ✅ Implemented | Public repo count, repo metadata, recent activity, profile verification |
| Academic Analyzer | ✅ Implemented | CGPA/CPI normalization, academic year/batch, scale checks |
| **Resume Analyzer** | ✅ Implemented | **12 signals**, PDF & DOCX extraction, SSRF security, direct upload API |
| **Eligibility Rules Engine (Phase 4)** | ✅ Implemented | **10 rule types**, universal threshold evaluator (5 aggregations), cross-team duplicate detection, track caps, config versioning, manual overrides, and audit trails |
| **Weighted Scoring Engine (Phase 5)** | ✅ Implemented | Relative weight normalization, criteria normalizations (numeric range, boolean, categorical), 6 aggregation methods, explicit missing-data policies, audit runs |
| **Ranking & Top-X Selection (Phase 6)** | ✅ Implemented | Deterministic 3-level ordering, tiebreak criteria, cutoff tie handling, shortage diagnostics, review suggestions, and run persistence |
| **PostgreSQL Persistence** | ✅ Implemented | **8 PostgreSQL stores**, Alembic migrations, Neon SSL connection pooling, centralized `StorageFactory` with delegating proxies |
| **Safety Guards & ID-Only Flow** | ✅ Implemented | Reset guard (`assert_safe_test_database`), ID-only evaluation pipeline (`dataset_id`, `extraction_run_id`), provenance inheritance, and UTF-8 BOM CSV export |
| **React Frontend Foundation & Design System** | ✅ Implemented | Editorial Enterprise styling, Tailwind CSS, Lucide icons, shadcn/ui components, generated OpenAPI types |
| **Live Dashboard (`/`)** | ✅ Implemented | Real-time backend integration, dataset/signals/ranking summaries, system health, and fault-isolated cards |
| **Evaluation Wizard (`/evaluate`)** | ✅ Implemented | 5-stage interactive pipeline (Dataset &rarr; Extraction &rarr; Rules &rarr; Scoring &rarr; Execution) using real backend APIs |
| **Results Leaderboard & Reviewer Workflow (`/results`)** | ✅ Implemented | Top-X shortlist, cutoff tie warnings, shortage diagnostics, manual overrides with reason modal, and UTF-8 BOM CSV export |
| **Configuration Manager (`/configurations`)** | ✅ Implemented | Versioned eligibility rules, scoring models & weights editor, immutable snapshot inspector, and preset cloning |
| Portfolio Analyzer | 🔲 Staged Contract | `PortfolioAnalyzerContract` registered as planned capability |

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
| `POST` | `/api/signals/flatten` | Flatten an `ExtractionRunResponse` into a list of member-signals dictionaries (`list[MemberSignals]`) for direct input to rules or scoring |
| `POST` | `/api/signals/extract-file` | Upload CSV/JSON and run selective signal extraction in one step |
| `POST` | `/api/signals/extract-resume` | Direct upload of a candidate's PDF or DOCX resume document |

---

### Custom Signals & Miscellaneous Field Ingestion (`custom:*`)

Hackathon and recruitment registration forms frequently contain non-standard or event-specific columns—such as `candidate_skills`, `track_preference`, `certifications`, or `work_domain`—that do not map directly to built-in system fields.

The Recruitment Engine natively supports **arbitrary custom signal mapping**:

1. **Dataset Discovery & Mapping**:
   - In Step 1 of the Evaluation Wizard or via the `/api/ingestion/upload` API, select `⭐ Map as Custom Signal (custom:<column>)`.
   - The ingestion parser preserves the values in each candidate's `custom_fields` dictionary under both `custom:<key>` and `<key>`.
2. **First-Class Signal Lift**:
   - During signal extraction, the engine dynamically synthesizes an `ExtractedSignal` for each requested `custom:*` key directly from `custom_fields`, assigning a default confidence of `0.85` and tracking provenance to the uploaded CSV file.
3. **Deterministic Eligibility Rules**:
   - Evaluator rules (`signal_contains`, `signal_threshold`, `required_signal_present`, `allowed_values`) accept any `custom:*` signal identifier.
   - Example: Require at least one team member to possess `Python` in `custom:skills`:
     ```json
     {
       "rule_id": "r_custom_python",
       "name": "Has Python Skill",
       "rule_type": "signal_contains",
       "severity": "hard",
       "scope": "member",
       "member_selection": "any_member",
       "parameters": {
         "signal_key": "custom:skills",
         "expected_value": "Python"
       }
     }
     ```
4. **Multi-Criteria Scoring Rubrics**:
   - Custom signals can be added directly to any Scoring Model configuration using the `✨ Custom Signal / Misc Field` builder in the frontend or via `/api/scoring/configs`.
   - Supports categorical scoring mappings (e.g., `Python: 1.0`, `JavaScript: 0.8`, `C++: 0.9`), relative weights, member aggregations (`mean`, `max`, `lead_only`), and explicit missing-data policies.

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
| `POST` | `/api/rules/runs/{run_id}/teams/{team_id}/override` | Apply an organizer manual override to a team result |

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

## 🏆 Ranking, Top-X Selection & Explainable Shortlisting (Phase 6)

Stage 6 of the recruitment pipeline consumes evaluation outputs from the eligibility and scoring engines to generate an explainable, deterministic shortlist of the Top-X teams.

### Core Architecture & Ranking Rules

1. **Deterministic 3-Level Ordering**:
   - **Level 1**: Higher composite final score first (descending). Legitimate numerical `0.0` scores are valid and distinguishable from `NO_SCORE`.
   - **Level 2 (Optional Tiebreak Criterion)**: If primary scores are equal, compare the configured `tiebreak_criterion_id` score in descending order. Teams with an available criterion score appear before teams lacking data for that criterion. Missing data never invents scores.
   - **Level 3 (Deterministic Tiebreaker)**: If still tied (or when no tiebreak criterion is configured), sort deterministically by `team_id` in ascending alphabetical order.
2. **Top-X Shortlist Selection**:
   - Requires a positive integer `top_x > 0` (zero, negative, or invalid values are rejected with HTTP 422).
   - Shortlists up to `top_x` qualifying teams.
   - **Cutoff Tie Handling**: If multiple teams share the identical primary final score at the `top_x` cutoff boundary, the shortlist never silently expands beyond `top_x`. `tie_at_cutoff: True` is flagged and a transparent cutoff warning explains the tie-breaking decision.
   - **Shortage Diagnostics**: When fewer than `top_x` teams qualify, a clear shortage warning is emitted. If scored `NEEDS_REVIEW` teams are available, the highest-ranked review candidates are surfaced as recommendations for organizer review without automatically approving them.
3. **Strict Status Handling**:
   - `ELIGIBLE`: Scored eligible teams participate in automatic ranking and selection.
   - `INELIGIBLE`: Excluded from automatic selection with `INELIGIBLE` reason code; original eligibility failure reasons are preserved.
   - `NEEDS_REVIEW`: Kept in a dedicated `needs_review_teams` section by default with provisional rankings and review explanations. When `include_needs_review: False` (the default), `NEEDS_REVIEW` teams also appear in `excluded_teams` and are included in `summary.excluded_count`. When `include_needs_review: True` is configured, scored review teams participate in selection without mutating their underlying `NEEDS_REVIEW` status.
   - `NO_SCORE`: Excluded with `NO_SCORE` reason code.
   - `DISQUALIFIED`: Excluded with `DISQUALIFIED` reason code; cannot be bypassed by general inclusion flags.
   - `UNRESOLVED`: Teams with temporary or ambiguous duplicate-name registrations (`is_unresolved: True`) are isolated with `UNRESOLVED` reason code.
   - **Missing Eligibility Data**: If run without upstream eligibility, teams are scored and ranked with a warning explicitly noting that eligibility was unverified.

---

## 📡 Ranking & Shortlisting API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/ranking/evaluate` | Execute Top-X ranking and selection from scoring run, explicit results, or end-to-end evaluation |
| `GET` | `/api/ranking/runs/{run_id}` | Retrieve a recorded ranking run with all shortlisted teams, breakdowns, and exclusions |
| `GET` | `/api/ranking/runs` | List all historical recorded ranking evaluation runs |

---

## 💻 Frontend Application (Phase 7)

The frontend is a single-page application built with **React 18**, **TypeScript**, **Vite**, **Tailwind CSS**, and **shadcn/ui-inspired primitives**, typed against the FastAPI OpenAPI contract via generated TypeScript models (`openapi-typescript`).

### 🎨 Editorial Enterprise Design System

The application adheres to an **Editorial Enterprise** aesthetic:
- **Palette**: Warm off-white backgrounds (`#FAFAF8`), deep forest green accents (`#1b4332`), and dark charcoal typography (`#1f2937`).
- **Information Density**: Information-rich data tables, distinct monospace identifier chips, clear badge statuses, and responsive form cards without purple gradients, decorative charts, or heavy animations.
- **Accessibility & Feedback**: Keyboard-navigable modal dialogs, loading skeletons, independent section error recovery, and explicit two-step confirmation prompts.

### 🧭 Page Architecture & Routes

The application exposes 4 primary routes wrapped in a unified layout with global navigation and live backend health monitoring:

| Route | View | Description |
| :--- | :--- | :--- |
| `/` | **Dashboard** | Real-time overview of ingested datasets, extraction runs, and evaluation history. |
| `/evaluate` | **Evaluation Wizard** | 5-stage interactive workflow guiding organizers from upload to shortlist. |
| `/results` | **Results & Overrides** | Top-X shortlist leaderboard, score breakdowns, reviewer manual overrides, and CSV export. |
| `/configurations` | **Configuration Manager** | Interactive rule and scoring model inspector, weight editor, and version audit timeline. |

---

### 1. Live Dashboard (`/`)

Connects directly to the FastAPI backend with fault-isolated TanStack Query hooks:
- **System Metrics**: Surfaces active storage engine (`PostgreSQL` or `Memory`), API health, total datasets count, extraction runs, and ranking evaluations.
- **Recent Ranking Runs**: Displays top evaluation runs with shortlist size, cutoff criteria, evaluated timestamps, and one-click navigation to inspect results.
- **Recent Ingested Datasets**: Summary cards showing dataset filename, file type, total teams and members count, upload dates, and validation warning badges.
- **Section Fault Isolation**: If an individual endpoint fails or the database is waking up, that specific section displays an error state with an inline **Retry** button without degrading other dashboard cards.

---

### 2. Multi-Stage Evaluation Wizard (`/evaluate`)

An end-to-end guided workflow that replaces manual API requests or cURL commands:

```
[ Stage 1: Dataset Selection ] ➔ [ Stage 2: Signal Extraction ] ➔ [ Stage 3: Eligibility Rules ] ➔ [ Stage 4: Scoring Model ] ➔ [ Stage 5: Execution & Results ]
```

1. **Stage 1 (Dataset Selection)**: Upload new CSV or JSON registration files (with immediate server-side validation and warning counters) or select from previously ingested datasets.
2. **Stage 2 (Signal Extraction)**: Select an existing extraction run for the dataset, or trigger a new selective extraction run across Academics, Technical GitHub, and Resume analyzers.
3. **Stage 3 (Eligibility Rules)**: Choose the active rule configuration (`demo_mixed_review`, `basic`, `strict`, `open_solo`, or custom rule sets) with an instant preview of evaluator counts and severity standards.
4. **Stage 4 (Scoring Model & Parameters)**: Select the scoring rubric (`balanced`, `technical_heavy`, `academic_heavy`, or custom) and configure the desired `top_x` shortlist count and review inclusion flags.
5. **Stage 5 (Pipeline Execution)**: Triggers the backend evaluation using ID-only references (`dataset_id`, `extraction_run_id`, `config_id`) and immediately redirects to the Results Leaderboard.

---

### 3. Results Leaderboard & Reviewer Workflow (`/results`)

Comprehensive candidate team review and decision audit interface:

- **Leaderboard Navigation**: Filterable tabs for `All Teams`, `Shortlisted (Selected)`, `Not Selected`, `Needs Review`, and `Excluded`.
- **Rank & Cutoff Warnings**:
  - Highlights Top-X selected candidates with ranked badge positions and tie indicators (`is_tied`).
  - **Cutoff Tie Alert**: Emits an alert banner when multiple teams tie at the `top_x` cutoff boundary (`tie_at_cutoff: True`).
  - **Shortage Diagnostics**: Displays actionable shortage alerts when fewer than `top_x` teams qualify, surfacing highest-ranked `NEEDS_REVIEW` candidates as recommendations.
- **Detailed Score Breakdowns**: Per-team score inspection showing exact criterion weights, normalized scores, member-to-team aggregations, and individual criterion score contributions reconciling to the composite score.
- **Reviewer Manual Overrides**:
  - Organizers can manually override a team's status (`ELIGIBLE`, `INELIGIBLE`, `NEEDS_REVIEW`).
  - Requires a mandatory justification note recorded in the audit trail.
  - Dynamically updates the effective run and recalculates the leaderboard without mutating the historical evaluation run snapshot.
- **One-Click RFC 4180 CSV Export**: Downloads the complete shortlist with UTF-8 BOM encoding and formula-injection security directly to the organizer's machine.

---

### 4. Configuration Manager & Immutable Version Audit (`/configurations`)

Provides centralized management and auditability across both evaluation engines:

- **Eligibility Rules Tab**:
  - Browse registered presets (`demo_mixed_review`, `basic`, `strict`, `open_solo`) and custom rule configurations.
  - Inspect global parameters (team lead field, lead values, academic scale) and evaluator definitions (rule type, scope, member selection, severity `hard`/`soft`, on-missing policies, and parameters).
  - Version switcher allows loading any historical snapshot via `GET /api/rules/configs/{id}?version={v}` in read-only mode with an immutability banner.
  - Edit rules modal creates an incremented immutable version (`v + 1`) with two-step confirmation.
  - Create custom rule configs starting at `v1` with preset cloning.
- **Scoring Weights & Models Tab**:
  - Browse scoring models (`balanced`, `technical_heavy`, `academic_heavy`) and custom rubrics.
  - Prominent weight display with real-time relative percentage shares (`(weight / total) * 100`) and visual proportion bars.
  - Clarifies that weights represent relative importance and do not need to sum to 100 (dynamic normalization supported).
  - Edit weights modal allows adjusting weights (`weight >= 0`), toggling criteria, and modifying `scale_max` with two-step confirmation creating Version `v + 1`.
  - Create custom scoring models starting at `v1`.
- **Version History & Audit Tab**:
  - Timeline of all version iterations recorded for any selected configuration.
  - Distinguishes current active version from preserved historical snapshots.
  - One-click "Inspect Snapshot" button to view the exact criteria that scored past evaluation runs.
- **Cache Synchronization**: Automatically invalidates both local configuration queries and wizard query caches (`['wizard', 'rules', 'configs']`, `['wizard', 'scoring', 'configs']`) so updates are instantly reflected throughout the application without page reloads.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+ (tested with Python 3.12)
- Node.js 18+ and npm (for the React frontend)

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

### Frontend Setup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Environment configuration (optional)
# Vite proxies /api to http://localhost:8000 by default.
# To specify an external backend:
# echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

# 4. Run Vite development server
npm run dev
# The dashboard opens at http://localhost:5173

# 5. Typecheck & production build
npm run typecheck      # Type verification (zero errors)
npm run build          # Builds production bundle to dist/
```

### Environment Variables

Configuration is loaded from environment variables or `.env`:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `APP_ENV` | `development` | Application environment (`development` / `production`). In production, `STORAGE_BACKEND=postgres` and `DATABASE_URL` are strictly required. |
| `APP_DEBUG` | `true` | Debug mode |
| `APP_HOST` | `0.0.0.0` | Host binding |
| `APP_PORT` | `8000` | Port binding |
| `STORAGE_BACKEND` | `memory` | Active storage engine (`memory` for in-memory development or `postgres` for persistent PostgreSQL). |
| `DATABASE_URL` | *None* | Connection URL for Neon/PostgreSQL database and migrations. Scheme is normalized to `postgresql+psycopg://` with `sslmode=require`. |
| `DATABASE_URL_POOLED` | *None* | Optional transaction-pooled connection URL (e.g. Neon PgBouncer) with server-side prepared statements disabled (`prepare_threshold=None`). |
| `TEST_DATABASE_URL` | *None* | Dedicated test database URL strictly enforced for PostgreSQL integration tests. Validated by `assert_safe_test_database`. |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum upload file size |
| `GITHUB_TOKEN` | *None* | Optional GitHub Personal Access Token (increases rate limit from 60 to 5,000 req/hr) |
| `GITHUB_API_BASE_URL` | `https://api.github.com` | GitHub API base URL (overridable for testing) |
| `GITHUB_REQUEST_TIMEOUT`| `10.0` | Request timeout in seconds for GitHub API calls |

---

## 🗄️ Database Setup & Persistent Storage

The application supports persistent storage powered by **Neon serverless PostgreSQL** with **SQLAlchemy 2.0**, **Alembic**, and the **Psycopg 3** driver.

### 1. Database Configuration & Neon Setup

Configure your Neon connection strings in `.env` (never commit real credentials to version control):

```env
# Application & Migration Database (Direct connection)
DATABASE_URL=postgresql://user:password@ep-calm-rice-xxx.neon.tech/neondb?sslmode=require

# Optional Pooled Connection (PgBouncer)
DATABASE_URL_POOLED=postgresql://user:password@ep-calm-rice-xxx-pooler.neon.tech/neondb?sslmode=require

# Separate Dedicated Test Database (Used exclusively for test suite migrations and isolation)
TEST_DATABASE_URL=postgresql://user:password@ep-calm-rice-xxx-test.neon.tech/test_db?sslmode=require

# Active Backend ('memory' for fast local testing, 'postgres' for persistent deployment)
STORAGE_BACKEND=postgres
```

### 2. Alembic Migrations

The database schema is managed via Alembic. Apply the initial migration defining all 8 persistence tables, indexes, and foreign keys:

```bash
# From the backend directory
alembic upgrade head
```

The initial schema (`001_initial_schema`) creates:
- `rule_configurations`: Versioned rule sets with soft-delete flags.
- `scoring_configurations`: Versioned scoring criteria, weightings, and snapshots.
- `datasets`: Ingested team registration snapshots and raw payloads.
- `extraction_runs`: Candidate signal extraction runs and audit logs.
- `eligibility_runs`: Immutable eligibility evaluation snapshots.
- `manual_overrides`: Organizer manual overrides on `(run_id, team_id)`.
- `scoring_runs`: Calculated team scores, weights, and criteria breakdowns.
- `ranking_runs`: Top-X shortlisted candidates, cutoff boundary ties, and shortage metrics.

### 3. Startup Preset Upsert & Current-Only Overrides

- **Startup Preset Seeding**: When `STORAGE_BACKEND=postgres`, the application automatically and idempotently upserts standard built-in presets (`basic`, `strict`, `open_solo`, `demo_mixed_review`, `balanced`, `technical_heavy`, `academic_heavy`) into PostgreSQL during server lifespan startup. User configurations are never overwritten.
- **Current-Only Overrides**: Organizer manual overrides (`POST /api/rules/runs/{run_id}/teams/{team_id}/override`) are stored as independent audit records without mutating historical evaluation run snapshots. Effective runs dynamically merge manual overrides.

### 4. ID-Only Evaluation Pipeline & Provenance Inheritance

Evaluation endpoints support ID-only requests without re-submitting inline payloads:
- `POST /api/rules/evaluate`: Provide `dataset_id` and `extraction_run_id` to automatically load candidate teams and signals from persistent stores.
- `POST /api/scoring/evaluate`: Provide `eligibility_run_id` to inherit `dataset_id` and `extraction_run_id` automatically.
- `POST /api/ranking/evaluate`: Option C ID-only flow automatically evaluates scoring and ranking from stored snapshots.
- Existing payload mode (`teams` and `signals` provided inline) remains 100% backward compatible.

### 5. CSV Shortlist Export

Export Top-X ranking runs as an RFC 4180-compliant CSV file with formula-injection mitigation:
- **Endpoint**: `GET /api/ranking/runs/{run_id}/export`
- **Encoding**: UTF-8 with BOM (`\xef\xbb\xbf`) for automatic spreadsheet parsing.
- **Row Ordering**: `SELECTED` $\rightarrow$ `NOT_SELECTED` $\rightarrow$ `NEEDS_REVIEW` $\rightarrow$ `UNRESOLVED` $\rightarrow$ `EXCLUDED`.
- **Columns**: `selection_status`, `rank`, `team_id`, `team_name`, `final_score`, `eligibility_status`, `score_status`, `is_tied`, `criteria_evaluated` (e.g. `"1 of 4"`), `reason_code`, `explanation`.
- **Security**: Neutralizes CSV formula injection by prepending single quotes to text cells starting with `=`, `+`, `-`, or `@`.

### 6. Lightweight Summary List Endpoints (Frontend Ready)

List endpoints support lightweight pagination to power frontend dashboards without loading full payloads:
- `GET /api/ingestion/datasets?summary=true&limit=50`: Returns compact dataset summaries (`dataset_id`, `filename`, `file_type`, `teams_count`, `members_count`, `uploaded_at`, `warnings_count`).
- `GET /api/signals/runs?summary=true&limit=50`: Returns compact extraction run summaries (`run_id`, `dataset_id`, `created_at`, `selected_signals`, `total_teams`, `total_members`, `warnings_count`, `errors_count`).
- `GET /api/ranking/runs?summary=true&limit=50`: Returns compact ranking run summaries (`run_id`, `evaluated_at`, `dataset_id`, `extraction_run_id`, `scoring_run_id`, `eligibility_run_id`, `top_x`, `include_needs_review`, `tiebreak_criterion_id`, counts, and resolved nullable upstream config IDs and dataset filename).
- **Postgres Optimization**: Never selects full `payload` columns; queries typed columns and extracts payload subkeys (`payload['summary']`) directly in SQL with single batched outerjoins for upstream metadata.
- **Default Preservation**: `summary=false` retains default full record behavior for full backward compatibility.

### 7. CORS Configuration for Frontends

- **Allowed Origins**: `CORS_ORIGINS` accepts comma-separated origins (default: `http://localhost:5173,http://127.0.0.1:5173`).
- **Allowed Methods**: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`.
- **Allowed Headers**: `Content-Type`.
- **Credential Protection**: Wildcard `*` is never combined with `allow_credentials=True`.
- **Exposed Headers**: Exposes `Content-Disposition` so frontend clients can read the suggested CSV export filename.

### 8. Known Differences (Memory vs. PostgreSQL Backend)

| Behavior | Memory Backend (`STORAGE_BACKEND=memory`) | PostgreSQL Backend (`STORAGE_BACKEND=postgres`) |
| :--- | :--- | :--- |
| **Duplicate Run IDs** | Overwrites previous run snapshot in memory. | Returns HTTP 409 Conflict on primary key conflict. |
| **Foreign Key Labels** | Accepts arbitrary or unknown `dataset_id` strings. | Enforces relational foreign keys (returns HTTP 409/404 if parent does not exist). |
| **Deleted Presets** | Deleted presets remain deleted until process restart. | Deleted built-in presets are re-seeded on server restart. |
| **Data Persistence** | Cleared upon process exit. | Persisted in Neon cloud storage. |
| **Security Note** | Local testing only. | Datasets contain candidate emails; deploy behind authentication gateway (e.g. API key / OAuth) before public production use. |

---

### Running Tests

Run the complete automated test suite locally:

```bash
# From workspace root
.\backend\venv\Scripts\python.exe -m pytest backend -v

# Or from backend directory with activated venv:
pytest -v
```

The test suite includes **440+ automated tests** with a 100% pass rate across 19 test suites:
- **`backend/tests/test_audit_fixes_regression.py`** (22 tests): Regression tests for dynamic forms, team lead resolution, and scoring edge cases.
- **`backend/tests/test_audit_phase2_fixes.py`** (11 tests): Provenance cross-dataset validation, inactive configuration rejection, explicit dataset_id conflict checks, upload file size limits, and duplicate mapping validation across all fields.
- **`backend/tests/test_database_phase.py`** (28 tests): URL normalization, safety checks, startup configuration validation, typed column derivations, and schema integrity.
- **`backend/tests/test_dataset_extraction_persistence.py`** (22 tests): Persistent storage for datasets and signal extraction runs in PostgreSQL and memory modes.
- **`backend/tests/test_duplicate_teams_regression.py`** (13 tests): Duplicate team name detection, automatic ID generation, temporary non-merging IDs (`temp_team_...`), and warning generation.
- **`backend/tests/test_dynamic_forms.py`** (16 tests): Dynamic registration form parsing, field mapping, and raw data retention.
- **`backend/tests/test_eligibility.py`** (22 tests): Eligibility engine foundation, catalog schemas, configuration versioning, missing data contradiction resolution, numeric safety, team lead resolution, and manual overrides.
- **`backend/tests/test_eligibility_spec.py`** (52 tests): Specification compliance for all 10 rule types, threshold operators, boundary conditions, all 5 aggregation reductions, cross-team email duplicates, fault isolation, determinism, and HTTP 422 configuration validation.
- **`backend/tests/test_ingestion.py`** (27 tests): CSV/JSON ingestion, header discovery, dynamic form mapping, custom field preservation, and validation.
- **`backend/tests/test_phase5_integration_fixes.py`** (4 tests): Integration fixes for scoring with eligibility run IDs, manual overrides applied to scoring, cross-team member ID disambiguation in CSV/JSON ingestion, and signals extraction output flattening.
- **`backend/tests/test_postgres_stores.py`** (19 tests): PostgreSQL-backed store CRUD, versioning, manual overrides, error handlers, and transactional resets against `TEST_DATABASE_URL`.
- **`backend/tests/test_prompt5_features.py`** (25 tests): Reset security guard on all 8 stores (portable execution boundary testing), ID-only evaluation pipeline, explicit empty list edge-case handling (`teams: []`), ranking CSV export with 5 row categories and 4-prefix formula injection mitigation, and mixed eligibility demo scenario with reviewer manual override workflow.
- **`backend/tests/test_prompt7_features.py`** (14 tests): Lightweight summary listing contracts, limit/ordering validation, CORS wildcard credential invariant, and OpenAPI schema models.
- **`backend/tests/test_ranking.py`** (33 tests): Deterministic 3-level ranking, Top-X selection with strict boundary checks, shortage detection and recommendations, status and missing data handling, tie-breaking criteria, explainability audit trails, end-to-end pipeline evaluation, effective eligibility sync, manual override bidirectional ranking, balanced preset NO_SCORE handling, deduplication, and boolean top_x rejection.
- **`backend/tests/test_resume_analyzer.py`** (45 tests): PDF & DOCX text parsing, all 12 resume signals, SSRF security defenses, size limits, direct file upload endpoint, and multi-analyzer compatibility.
- **`backend/tests/test_scoring.py`** (36 tests): Configurable scoring criteria, relative weight normalization, min-max/boolean/categorical normalization, 6 member-to-team aggregations, missing data policies (exclude and renormalize, zero score), confidence adjustment, eligibility integration, and API endpoints.
- **`backend/tests/test_signals.py`** (23 tests): Extensible signal registry, catalog discovery, GitHub API analysis, Academic CGPA/batch normalization, and cross-analyzer fault isolation.
- **`backend/tests/test_custom_signals_e2e.py`** (1 test): Custom signal (`custom:*`) mapping, dynamic extraction to `ExtractedSignal`, rule validation (`signal_contains`), and multi-criteria scoring rubrics.
- **`backend/tests/test_user_dataset_e2e.py`** (3 tests): Full end-to-end multi-signal evaluation pipeline, column discovery conflict resolution, and ingestion warning filtering against real organizer CSV and companion resume ZIP.

#### Test Execution & Isolation Architecture

1. **Unit Tests (Memory Mode)**:
   - All 17 test suites execute completely in-memory by default (`STORAGE_BACKEND=memory`).
   - Requiring zero database credentials or live network connections; all external API calls (e.g. GitHub) are mocked.
   - The portable reset guard test (`TestResetGuard::test_reset_with_default_app_engine_raises_value_error`) uses execution-boundary instrumentation to verify that unsafe resets are rejected with `ValueError` before any SQL statement or connection attempt is made.
2. **PostgreSQL Integration Tests**:
   - PostgreSQL integration tests (`test_postgres_stores.py`, `test_dataset_extraction_persistence.py`, and `test_prompt5_features.py`) execute only against `TEST_DATABASE_URL` after `assert_safe_test_database` passes.
   - There is zero fallback to `DATABASE_URL`. If `TEST_DATABASE_URL` is unset, PostgreSQL integration tests are skipped safely without failure.
3. **Live Smoke Test**:
   - A dedicated verification script tests end-to-end PostgreSQL persistence across all 8 stores, verifying ingestion, extraction, eligibility, scoring, manual overrides, ranking, and CSV export.
4. **Mixed Eligibility Reviewer Workflow**:
   - Documented in detail with reproducible API calls in [`sample_data/README.md`](file:///sample_data/README.md#mixed-eligibility--reviewer-override-workflow-demo).

---

## 🚀 Production Deployment Guide

The Team Recruitment Automation Tool is containerized and deployment-ready for standard cloud infrastructure, container services, or self-hosted servers.

### Recommended Deployment Options

#### Option A: Docker & Docker Compose (Turn-Key / One-Command)

The repository includes production-ready Dockerfiles for both frontend (multi-stage Nginx) and backend (Python 3.12 slim), along with a coordinated `docker-compose.yml` including PostgreSQL 16.

1. **Clone and Configure**:
   ```bash
   git clone https://github.com/mehul-khandelwal26/Team_Recruitment.git
   cd Team_Recruitment
   cp .env.example .env
   # Edit .env with your production secrets (JWT_SECRET_KEY, POSTGRES_PASSWORD, etc.)
   ```

2. **Launch Services**:
   ```bash
   docker compose up --build -d
   ```
   * **Frontend UI**: http://localhost:5173 (or port 80 if mapped)
   * **Backend API & Swagger Docs**: http://localhost:8000/docs
   * **Health Check**: http://localhost:8000/api/health

3. **Database Migrations**:
   The backend container automatically applies all pending Alembic migrations (`alembic upgrade head`) and seeds default presets on startup when `STORAGE_BACKEND=postgres`.

---

#### Option B: Split PaaS Deployment (Vercel / Netlify + Render / Railway)

Ideal for managed cloud hosting with zero infrastructure maintenance.

##### 1. Backend + Database (Render / Railway)
* **Runtime**: Python 3.12
* **Database**: Managed PostgreSQL (or Neon / Supabase)
* **Build Command**: `pip install -r requirements.txt && alembic upgrade head`
* **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* **Environment Variables**:
  * `APP_ENV=production`
  * `STORAGE_BACKEND=postgres`
  * `DATABASE_URL=postgresql+psycopg://user:password@host/db?sslmode=require`
  * `CORS_ORIGINS=https://your-frontend.vercel.app`
  * `JWT_SECRET_KEY=<generate-secure-64-char-random-key>`
  * `AUTH_ENABLED=true`
  * `GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com` (optional)

##### 2. Frontend (Vercel / Netlify / Cloudflare Pages)
* **Framework Preset**: Vite
* **Root Directory**: `frontend`
* **Build Command**: `npm run build`
* **Output Directory**: `dist`
* **Environment Variables**:
  * `VITE_API_BASE_URL=https://your-backend.onrender.com`

---

#### Option C: Self-Hosted VPS (Ubuntu/Debian + Nginx + Systemd)

1. **System Dependencies**:
   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip nodejs npm postgresql nginx
   ```

2. **Backend Setup**:
   ```bash
   cd /var/www/team-recruitment/backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   ```

3. **Systemd Service (`/etc/systemd/system/recruitment-backend.service`)**:
   ```ini
   [Unit]
   Description=Team Recruitment FastAPI Service
   After=network.target postgresql.service

   [Service]
   User=www-data
   WorkingDirectory=/var/www/team-recruitment/backend
   EnvironmentFile=/var/www/team-recruitment/backend/.env
   ExecStart=/var/www/team-recruitment/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

4. **Frontend Build**:
   ```bash
   cd /var/www/team-recruitment/frontend
   npm ci
   npm run build
   # Outputs static assets to /var/www/team-recruitment/frontend/dist
   ```

5. **Nginx Reverse Proxy (`/etc/nginx/sites-available/recruitment.conf`)**:
   ```nginx
   server {
       listen 80;
       server_name recruitment.yourdomain.com;

       # Frontend SPA
       location / {
           root /var/www/team-recruitment/frontend/dist;
           try_files $uri $uri/ /index.html;
       }

       # Backend API Proxy
       location /api/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

---

## 🔒 Production Security & Operational Invariants

1. **Authentication Gateway**:
   - Google OAuth2 authentication is supported out of the box with zero credentials required for local dev (using the built-in Dev Mock Login).
   - In production, set `GOOGLE_CLIENT_ID` and specify `ALLOWED_EMAILS` or `ALLOWED_EMAIL_DOMAINS` to restrict access strictly to authorized organizers.
2. **PostgreSQL Relational Invariants**:
   - In `APP_ENV=production`, `STORAGE_BACKEND` must be `postgres` and `DATABASE_URL` must be set. The application startup (`lifespan`) automatically validates this and halts if unconfigured.
   - All connection pools use `pool_pre_ping=True` and `pool_recycle=300` to prevent stale connection dropouts from serverless or cloud compute auto-pausing.
3. **SSRF and File Upload Defenses**:
   - Resume downloads are protected against SSRF (loopback addresses, internal subnets, and cloud metadata endpoints `169.254.169.254` are rejected).
   - File uploads are capped at 10 MB by default (`MAX_UPLOAD_SIZE_MB`).
4. **GitHub API Rate Limits**:
   - For high-volume organizer workflows, supply a `GITHUB_TOKEN` to raise GitHub rate limits from 60 req/hr to 5,000 req/hr. If the rate limit is exceeded, the pipeline gracefully continues evaluation without crashing.

