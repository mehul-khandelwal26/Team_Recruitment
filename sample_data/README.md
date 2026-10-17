# Sample Recruitment Dataset (`demo_teams.csv`)

This directory contains realistic sample registration data for testing the Team Recruitment Automation Tool pipeline, alongside the exact observed evaluation outcomes across all evaluation stages.

## File Overview

- **Dataset File**: [`demo_teams.csv`](file:///sample_data/demo_teams.csv)
- **Total Teams**: 15 teams
- **Total Members**: 29 candidate members
- **Privacy Compliance**: All candidate names are fictional; all email addresses use RFC 2606 `example.com`.

---

## Required Signals & Presets

- **Extracted Signals**: Academic signals only (`academic_cgpa`, `academic_year`). External GitHub API lookups are omitted to preserve test determinism and prevent external rate-limiting.
- **Rule Presets**:
  - `basic`: Evaluates team sizing ($\ge 2$ and $\le 4$ members, hard), technical profile presence (at least one member with `github_url`, hard), and minimum CGPA $\ge 6.0$ (soft advisory).
  - `strict`: Evaluates team sizing (2–4 members, hard), all members provide `github_url` (hard), all members CGPA $\ge 7.0$ (hard), and active public repository presence (hard, triggers `manual_review` if unavailable).
- **Scoring Preset**:
  - `balanced`: Default balanced multi-criteria weighting across academic and technical signals.
- **Ranking Policy**:
  - Top-X shortlist size: `top_x = 5`.
  - Scored `NEEDS_REVIEW` teams are excluded from automatic selection (`include_needs_review = false`).

---

## Exact Request Order & Execution Steps

To reproduce these observed outcomes, execute the pipeline in the following sequence:

1. **Ingest CSV Dataset**:
   - `POST /api/ingestion/upload` with `demo_teams.csv` as multipart file.
   - Generates and stores dataset (e.g. `dataset_id = "ds_demo_001"`).
2. **Execute Signal Extraction**:
   - `POST /api/signals/extract` with payload:
     ```json
     {
       "dataset_id": "ds_demo_001",
       "selected_signals": ["academic_cgpa", "academic_year"]
     }
     ```
   - Stores extraction run and returns `run_id` (e.g. `extraction_run_id`).
3. **Evaluate Eligibility (Basic Preset)**:
   - `POST /api/rules/evaluate` with ID-only payload:
     ```json
     {
       "dataset_id": "ds_demo_001",
       "extraction_run_id": "<extraction_run_id>",
       "config_id": "basic"
     }
     ```
   - Persists eligibility run (e.g. `eligibility_run_id`).
4. **Evaluate Eligibility (Strict Preset - Optional Diagnostic)**:
   - `POST /api/rules/evaluate` with ID-only payload:
     ```json
     {
       "dataset_id": "ds_demo_001",
       "extraction_run_id": "<extraction_run_id>",
       "config_id": "strict"
     }
     ```
5. **Evaluate Team Scoring (Balanced Preset)**:
   - `POST /api/scoring/evaluate` with ID-only payload inheriting provenance:
     ```json
     {
       "dataset_id": "ds_demo_001",
       "extraction_run_id": "<extraction_run_id>",
       "eligibility_run_id": "<eligibility_run_id>",
       "config_id": "balanced"
     }
     ```
   - Persists scoring run and returns `run_id` (e.g. `scoring_run_id`).
6. **Evaluate Ranking & Top-5 Selection**:
   - `POST /api/ranking/evaluate` with ID-only payload:
     ```json
     {
       "scoring_run_id": "<scoring_run_id>",
       "top_x": 5
     }
     ```
   - Returns shortlisted teams, other ranked teams, unresolved teams, and excluded teams.
7. **Export Ranking Run CSV**:
   - `GET /api/ranking/runs/<ranking_run_id>/export`
   - Returns UTF-8 with BOM CSV containing all 15 evaluated teams ordered by selection category.

---

## Actual Observed Outcomes per Scenario Case

All outcomes below were directly observed from executing the live backend pipeline in memory mode:

| Scenario Case | Team ID | Team Name | Basic Eligibility | Strict Eligibility | Balanced Score | Top-5 Ranking Outcome | Actual Observed Details & Explanations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Clearly Eligible** | `T01` | Alpha Algorithmic | `ELIGIBLE` | `NEEDS_REVIEW` | 75.00 (`CALCULATED`) | **SELECTED (Rank #1)** | Meets all basic sizing and technical profile criteria. Academic CGPA 8.5/8.0. |
| **Clearly Eligible** | `T12` | Zeta Zealots | `ELIGIBLE` | `NEEDS_REVIEW` | 70.00 (`CALCULATED`) | **SELECTED (Rank #2)** | Valid 2-member team, CGPA 8.2/7.8, strong profile. |
| **Score Tie (Shortlisted)** | `T02` | Beta Builders | `ELIGIBLE` | `NEEDS_REVIEW` | 57.50 (`CALCULATED`) | **SELECTED (Rank #3)** | Tied on final score 57.50 with `T10`. Sorted deterministically by `team_id` (`'T02' < 'T10'`). |
| **Score Tie (Shortlisted)** | `T10` | Cross Member Alpha | `ELIGIBLE` | `NEEDS_REVIEW` | 57.50 (`CALCULATED`) | **SELECTED (Rank #4)** | Tied on final score 57.50 with `T02`. Sorted deterministically by `team_id`. |
| **Clearly Eligible** | `T11` | Cross Member Beta | `ELIGIBLE` | `NEEDS_REVIEW` | 55.00 (`CALCULATED`) | **SELECTED (Rank #5)** | Final qualifying team filling the requested Top-5 shortlist cutoff. |
| **Cutoff Boundary** | `T05` | Epsilon Engineers | `ELIGIBLE` | `NEEDS_REVIEW` | 52.50 (`CALCULATED`) | **NOT_SELECTED (Rank #6)** | Eligible and scored, but ranks directly below the requested Top-5 cutoff. |
| **Score Tie (Below Cutoff)** | `T03` | Gamma Guardians | `ELIGIBLE` | `NEEDS_REVIEW` | 37.50 (`CALCULATED`) | **NOT_SELECTED (Rank #7)** | Tied on final score 37.50 with `T04`. Sorted deterministically by `team_id` (`'T03' < 'T04'`). |
| **Score Tie (Below Cutoff)** | `T04` | Delta Dynamics | `ELIGIBLE` | `NEEDS_REVIEW` | 37.50 (`CALCULATED`) | **NOT_SELECTED (Rank #8)** | Tied on final score 37.50 with `T03`. Sorted deterministically by `team_id`. |
| **Clearly Eligible** | `T13` | Eta Explorers | `ELIGIBLE` | `NEEDS_REVIEW` | 27.50 (`CALCULATED`) | **NOT_SELECTED (Rank #9)** | Eligible team with low academic CGPA (6.2/6.0), ranked #9. |
| **Real CGPA of 0.0** | `T09` | Zero CGPA Heroes | `ELIGIBLE` | `INELIGIBLE` | 0.00 (`CALCULATED`) | **NOT_SELECTED (Rank #10)** | Valid numeric 0.0 is preserved as real data (not null or missing). Calculates valid score 0.00. |
| **Hard Filter Failure** | `T06` | Solo Flyers | `INELIGIBLE` | `INELIGIBLE` | 87.50 (`CALCULATED`) | **EXCLUDED (Reason: INELIGIBLE)** | Has 1 member; fails hard `team_size_min >= 2` rule. Informational score calculated, excluded from ranking. |
| **Missing GitHub Links** | `T07` | Strict Review Crew | `INELIGIBLE` | `INELIGIBLE` | 56.25 (`CALCULATED`) | **EXCLUDED (Reason: INELIGIBLE)** | Neither member provides GitHub URL; fails hard `basic_github_presence` and `strict_all_github` rules. Excluded from ranking. |
| **No Usable Data** | `T08` | Zero Data Zone | `ELIGIBLE` | `INELIGIBLE` | `None` (`NO_SCORE`) | **EXCLUDED (Reason: NO_SCORE)** | Has GitHub but no CGPA provided. Missing academic criterion prevents score calculation. |
| **Duplicate Names without IDs** | `temp_team_..._unresolved_1` | Shadow Clone Squad | `ELIGIBLE` | `NEEDS_REVIEW` | 53.75 (`CALCULATED`) | **UNRESOLVED (Excluded)** | Missing registration team ID and duplicate team name; parser generates temporary disambiguated ID. Excluded from shortlist. |
| **Duplicate Names without IDs** | `temp_team_..._unresolved_2` | Shadow Clone Squad | `ELIGIBLE` | `NEEDS_REVIEW` | 63.75 (`CALCULATED`) | **UNRESOLVED (Excluded)** | Second registration with same name; isolated with temporary ID. Excluded from shortlist until organizer resolves identity. |
| **Shared Member Across Teams** | `T10` & `T11` | Cross Member Alpha & Beta | `ELIGIBLE` | `NEEDS_REVIEW` | 57.50 & 55.00 | **SELECTED (Ranks #4 & #5)** | Member `M_SHARED_01` (Rachel Green) registered in both teams. Parser disambiguates IDs (`T10_M_SHARED_01`, `T11_M_SHARED_01`) enabling independent scoring. |

---

## Actual Observed CSV Export Output

Exported from `GET /api/ranking/runs/<run_id>/export` (encoded in UTF-8 with BOM `\xef\xbb\xbf`):

```csv
selection_status,rank,team_id,team_name,final_score,eligibility_status,score_status,is_tied,criteria_evaluated,reason_code,explanation
SELECTED,1,T01,Alpha Algorithmic,75.00,ELIGIBLE,CALCULATED,False,1 of 4,,Ranked #1 of 10 teams with score 75.00. Selected for Top-5 shortlist.
SELECTED,2,T12,Zeta Zealots,70.00,ELIGIBLE,CALCULATED,False,1 of 4,,Ranked #2 of 10 teams with score 70.00. Selected for Top-5 shortlist.
SELECTED,3,T02,Beta Builders,57.50,ELIGIBLE,CALCULATED,True,1 of 4,,Ranked #3 of 10 teams with score 57.50. Selected for Top-5 shortlist. (Tied on final score 57.50; sorted by team_id 'T02').
SELECTED,4,T10,Cross Member Alpha,57.50,ELIGIBLE,CALCULATED,True,1 of 4,,Ranked #4 of 10 teams with score 57.50. Selected for Top-5 shortlist. (Tied on final score 57.50; sorted by team_id 'T10').
SELECTED,5,T11,Cross Member Beta,55.00,ELIGIBLE,CALCULATED,False,1 of 4,,Ranked #5 of 10 teams with score 55.00. Selected for Top-5 shortlist.
NOT_SELECTED,6,T05,Epsilon Engineers,52.50,ELIGIBLE,CALCULATED,False,1 of 4,,Ranked #6 of 10 teams with score 52.50. Below Top-5 cutoff.
NOT_SELECTED,7,T03,Gamma Guardians,37.50,ELIGIBLE,CALCULATED,True,1 of 4,,Ranked #7 of 10 teams with score 37.50. Below Top-5 cutoff. (Tied on final score 37.50; sorted by team_id 'T03').
NOT_SELECTED,8,T04,Delta Dynamics,37.50,ELIGIBLE,CALCULATED,True,1 of 4,,Ranked #8 of 10 teams with score 37.50. Below Top-5 cutoff. (Tied on final score 37.50; sorted by team_id 'T04').
NOT_SELECTED,9,T13,Eta Explorers,27.50,ELIGIBLE,CALCULATED,False,1 of 4,,Ranked #9 of 10 teams with score 27.50. Below Top-5 cutoff.
NOT_SELECTED,10,T09,Zero CGPA Heroes,0.00,ELIGIBLE,CALCULATED,False,1 of 4,,Ranked #10 of 10 teams with score 0.00. Below Top-5 cutoff.
UNRESOLVED,,temp_team_shadow_clone_squad_3db6f2_unresolved_1,Shadow Clone Squad,53.75,ELIGIBLE,CALCULATED,,,UNRESOLVED,Team identity is unresolved due to duplicate team names or ambiguous registration; excluded from automatic selection until resolved.
UNRESOLVED,,temp_team_shadow_clone_squad_3db6f2_unresolved_2,Shadow Clone Squad,63.75,ELIGIBLE,CALCULATED,,,UNRESOLVED,Team identity is unresolved due to duplicate team names or ambiguous registration; excluded from automatic selection until resolved.
EXCLUDED,,T06,Solo Flyers,87.50,INELIGIBLE,CALCULATED,,,INELIGIBLE,"Team failed mandatory eligibility criteria. Reasons: Minimum Team Size (>= 2 Members): Team 'Solo Flyers' has 1 member(s), which is below minimum requirement of 2."
EXCLUDED,,T07,Strict Review Crew,56.25,INELIGIBLE,CALCULATED,,,INELIGIBLE,"Team failed mandatory eligibility criteria. Reasons: Technical Profile Link (Any Member) failed for all members: Laura Croft (Missing required github_url (not provided)), Michael Scott (Missing required github_url (not provided))"
EXCLUDED,,T08,Zero Data Zone,,ELIGIBLE,NO_SCORE,,,NO_SCORE,Team has no calculable score; missing data prevented score calculation.
```

---

## Mixed Eligibility & Reviewer Override Workflow Demo

To demonstrate a realistic review workflow where both `ELIGIBLE` and `NEEDS_REVIEW` candidates occur simultaneously, and where an organizer inspects and overrides a team's status, use the custom `demo_mixed_review` configuration.

### 1. Configuration Setup

Create a custom rule configuration `demo_mixed_review` via `POST /api/rules/configs`:

```json
{
  "config_id": "demo_mixed_review",
  "name": "Demo Mixed Review",
  "description": "Requires team lead academic verification (CGPA >= 7.0)",
  "global_config": {
    "lead_field": "role"
  },
  "rules": [
    {
      "rule_id": "min_size",
      "rule_type": "team_size_min",
      "name": "Minimum Team Size (>= 2 Members)",
      "severity": "hard",
      "scope": "team",
      "order": 1,
      "parameters": {"min_size": 2}
    },
    {
      "rule_id": "github_req",
      "rule_type": "required_link",
      "name": "Technical Profile Link (Any Member)",
      "severity": "hard",
      "scope": "member",
      "member_selection": "any_member",
      "order": 2,
      "parameters": {"link_field": "github_url", "member_selection": "any_member"}
    },
    {
      "rule_id": "lead_cgpa",
      "rule_type": "signal_threshold",
      "name": "Team Lead Academic Standing (CGPA >= 7.0)",
      "severity": "hard",
      "scope": "member",
      "member_selection": "team_lead",
      "order": 3,
      "on_missing": "manual_review",
      "parameters": {
        "signal_key": "academic_cgpa",
        "operator": ">=",
        "threshold": 7.0,
        "member_selection": "team_lead"
      }
    }
  ]
}
```

### 2. Eligibility Outcomes Under Mixed Review

Evaluating `demo_teams.csv` against `demo_mixed_review` produces:
- **Total Teams**: 15
- **Eligible Teams (10)**: `T01`, `T12`, `T10`, `T11`, `T05`, `T03`, `T04`, `T13`, and 2 duplicate unresolved teams.
- **Ineligible Teams (4)**: `T06` (size < 2), `T07` (missing GitHub), `T08` (missing CGPA), `T09` (lead CGPA 0.0 < 7.0).
- **Needs Review Teams (1)**: `T02 (Beta Builders)` – Charlie Brown and Diana Prince are both listed as `member`; the team has no designated team lead in the `role` field. Because `on_missing=manual_review`, this hard rule flags the team for organizer inspection instead of automatic rejection.

### 3. Initial Top-5 Ranking (Before Override)

When Top-5 ranking is executed (`top_x = 5`), `T02` is placed in `needs_review_teams` and excluded from automatic selection:
- **Selected Teams (5)**: `T01 (75.0)`, `T12 (70.0)`, `T10 (57.5)`, `T11 (55.0)`, `T05 (52.5)`.
- **Needs Review (1)**: `T02 (57.5)`.
- Notice that `T05` takes the 5th shortlist spot because `T02` is held in review.

### 4. Reviewer Manual Override Workflow

An organizer reviews `T02` and confirms Charlie Brown acts as the lead with CGPA 8.4:

`POST /api/rules/runs/{run_id}/teams/T02/override`

```json
{
  "override_status": "ELIGIBLE",
  "reason": "Team lead Charlie Brown verified manually; CGPA 8.4 meets threshold.",
  "overridden_by": "reviewer"
}
```

### 5. Subsequent Top-5 Ranking (After Override)

Evaluating Top-5 ranking referencing the same `eligibility_run_id` automatically reflects the manual override:
- **Selected Teams (5)**: `T01 (Rank #1, 75.0)`, `T12 (Rank #2, 70.0)`, `T02 (Rank #3, 57.5)`, `T10 (Rank #4, 57.5)`, `T11 (Rank #5, 55.0)`.
- **Cutoff Impact**: `T02` is restored to Rank #3 (breaking the 57.50 tie with `T10` via alphabetical team ID `'T02' < 'T10'`). `T05 (52.5)` is pushed down to Rank #6 (`NOT_SELECTED`).
- **Needs Review**: Empty (`[]`).

