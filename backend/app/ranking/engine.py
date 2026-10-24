"""Core ranking and Top-X selection engine.

Implements:
- Deterministic ordinal ranking (descending score -> tiebreak criterion -> team_id ascending).
- Top-X shortlist selection with cutoff tie detection.
- Explicit status handling (ELIGIBLE, INELIGIBLE, NEEDS_REVIEW, NO_SCORE, DISQUALIFIED, UNRESOLVED).
- Explainable audit results preserving upstream scoring breakdowns and completeness metrics.
- Candidate recommendations for shortage without automatic approval.
"""

from __future__ import annotations

import datetime
import math
import uuid
from typing import Any, Optional

from app.ranking.schemas import (
    ExcludedTeamResult,
    ExclusionReason,
    RankedTeamResult,
    RankingRunResponse,
    RankingRunSummary,
    SelectionStatus,
)
from app.rules.schemas import EligibilityRunResponse, EligibilityStatus
from app.rules.store import get_effective_run
from app.scoring.schemas import ScoreStatus, TeamScoringResult


def extract_tiebreak_score(
    team: TeamScoringResult,
    criterion_id: Optional[str],
) -> Optional[float]:
    """Extract a team's score for the specified tiebreak criterion, if available.

    Matches against criterion_id or target_signal_key. Returns None if uncalculated or missing.
    """
    if not criterion_id:
        return None
    for b in team.criteria_breakdowns:
        if b.criterion_id == criterion_id or b.target_signal_key == criterion_id:
            if b.is_applicable and b.team_criterion_score is not None:
                return float(b.team_criterion_score)
    return None


def is_unresolved_team(
    team: TeamScoringResult | dict[str, Any],
    unresolved_team_ids: Optional[set[str]] = None,
) -> bool:
    """Check whether a team has a temporary or ambiguous duplicate identity."""
    if isinstance(team, dict):
        if team.get("is_unresolved") or team.get("is_temporary_id"):
            return True
        t_id = str(team.get("team_id", ""))
    else:
        if getattr(team, "is_unresolved", False) or getattr(team, "is_temporary_id", False):
            return True
        t_id = str(team.team_id)

    if unresolved_team_ids and t_id in unresolved_team_ids:
        return True

    lower_id = t_id.lower()
    return lower_id.startswith("temp_team_") or "_unresolved_" in lower_id


def build_ranking_sort_key(
    team: TeamScoringResult,
    tiebreak_criterion_id: Optional[str],
) -> tuple[float, tuple[int, float], str]:
    """Deterministic 3-level sort key for candidate ranking.

    1. Primary final_score (descending)
    2. Configured tiebreak criterion (descending; available scores before missing)
    3. team_id (ascending string comparison)
    """
    score = team.final_score if team.final_score is not None else -math.inf
    primary_key = -score

    if tiebreak_criterion_id:
        tb_score = extract_tiebreak_score(team, tiebreak_criterion_id)
        if tb_score is not None:
            tb_key = (0, -tb_score)
        else:
            tb_key = (1, 0.0)
    else:
        tb_key = (0, 0.0)

    id_key = str(team.team_id)
    return (primary_key, tb_key, id_key)


def evaluate_ranking(
    scoring_results: list[TeamScoringResult | dict[str, Any]],
    top_x: int,
    tiebreak_criterion_id: Optional[str] = None,
    include_needs_review: bool = False,
    scoring_run_id: Optional[str] = None,
    eligibility_run_id: Optional[str] = None,
    evaluated_at: Optional[str] = None,
    run_id: Optional[str] = None,
    effective_eligibility_run: Optional[EligibilityRunResponse] = None,
) -> RankingRunResponse:
    """Execute deterministic Top-X ranking and selection from scoring results.

    Args:
        scoring_results: List of TeamScoringResult models or equivalent dicts.
        top_x: Mandatory positive integer specifying number of top teams to shortlist.
        tiebreak_criterion_id: Optional criterion ID to break final score ties.
        include_needs_review: If True, scored NEEDS_REVIEW teams may participate in selection.
        scoring_run_id: Optional linked scoring run ID.
        eligibility_run_id: Optional linked eligibility run ID.
        evaluated_at: Optional injected ISO timestamp for deterministic testing.
        run_id: Optional injected run ID for deterministic testing.
        effective_eligibility_run: Optional pre-loaded effective eligibility run with overrides applied.

    Returns:
        RankingRunResponse with shortlist, all ranked teams, review teams, and exclusions.
    """
    if isinstance(top_x, bool) or not isinstance(top_x, int) or top_x <= 0:
        raise ValueError(f"top_x must be a positive integer (> 0), got: {top_x}")

    now_ts = evaluated_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    final_run_id = run_id or f"rank_run_{uuid.uuid4().hex[:12]}"

    warnings: list[str] = []
    errors: list[str] = []

    # 1. Parse into TeamScoringResult instances (deep copy to avoid mutating stored records)
    parsed_teams: list[TeamScoringResult] = []
    for item in scoring_results:
        if isinstance(item, TeamScoringResult):
            parsed_teams.append(item.model_copy(deep=True))
        elif isinstance(item, dict):
            try:
                parsed_teams.append(TeamScoringResult.model_validate(item))
            except Exception as exc:
                errors.append(f"Failed to parse scoring result for team '{item.get('team_id', '?')}': {exc}")

    # 2. Deduplicate team_id: keep the first occurrence and emit a warning for duplicates
    seen_team_ids: set[str] = set()
    deduped_teams: list[TeamScoringResult] = []
    for t in parsed_teams:
        if t.team_id in seen_team_ids:
            warnings.append(
                f"Duplicate team_id '{t.team_id}' encountered in scoring results; keeping the first occurrence and ignoring subsequent ones."
            )
            continue
        seen_team_ids.add(t.team_id)
        deduped_teams.append(t)
    parsed_teams = deduped_teams

    # 3. Synchronize with effective eligibility run if provided or resolvable
    eff_run = effective_eligibility_run
    if eff_run is None and eligibility_run_id:
        eff_run = get_effective_run(eligibility_run_id)

    unresolved_team_ids: set[str] = set()
    if eff_run is not None:
        eff_teams_by_id = {team.team_id: team for team in eff_run.teams}
        for t in parsed_teams:
            if t.team_id in eff_teams_by_id:
                elig_t = eff_teams_by_id[t.team_id]
                t.eligibility_status = elig_t.status
                t.eligibility_summary = "; ".join(elig_t.reasons) if elig_t.reasons else None
                if elig_t.status in (EligibilityStatus.ELIGIBLE, EligibilityStatus.NEEDS_REVIEW):
                    if t.score_status == ScoreStatus.DISQUALIFIED and t.final_score is not None and getattr(t, "criteria_breakdowns", None):
                        t.score_status = ScoreStatus.CALCULATED
                if getattr(elig_t, "is_unresolved", False) or getattr(elig_t, "is_temporary_id", False):
                    unresolved_team_ids.add(t.team_id)
            else:
                warnings.append(
                    f"Team '{t.team_id}' was not found in eligibility run '{eff_run.run_id}'; retaining existing eligibility status."
                )

    # 4. Categorize candidates
    qualifying_candidates: list[TeamScoringResult] = []
    needs_review_candidates: list[TeamScoringResult] = []
    unresolved_candidates: list[ExcludedTeamResult] = []
    excluded_candidates: list[ExcludedTeamResult] = []

    has_missing_eligibility = False

    for t in parsed_teams:
        # A. Check unresolved team identity
        if is_unresolved_team(t, unresolved_team_ids):
            excl = ExcludedTeamResult(
                team_id=t.team_id,
                team_name=t.team_name,
                reason_code=ExclusionReason.UNRESOLVED,
                explanation=(
                    "Team identity is unresolved due to duplicate team names or ambiguous registration; "
                    "excluded from automatic selection until resolved."
                ),
                eligibility_status=t.eligibility_status,
                score_status=t.score_status,
                final_score=t.final_score,
                warnings=list(t.warnings),
            )
            unresolved_candidates.append(excl)
            excluded_candidates.append(excl)
            continue

        # B. Check disqualified
        if t.score_status == ScoreStatus.DISQUALIFIED:
            excl = ExcludedTeamResult(
                team_id=t.team_id,
                team_name=t.team_name,
                reason_code=ExclusionReason.DISQUALIFIED,
                explanation="Team was disqualified during evaluation; excluded from automatic ranking and selection.",
                eligibility_status=t.eligibility_status,
                score_status=t.score_status,
                final_score=t.final_score,
                warnings=list(t.warnings),
            )
            excluded_candidates.append(excl)
            continue

        # C. Check NO_SCORE
        # Valid 0.0 scores must remain valid! Only None or NO_SCORE status is no-score.
        if t.score_status == ScoreStatus.NO_SCORE or t.final_score is None:
            excl = ExcludedTeamResult(
                team_id=t.team_id,
                team_name=t.team_name,
                reason_code=ExclusionReason.NO_SCORE,
                explanation="Team has no calculable score; missing data prevented score calculation.",
                eligibility_status=t.eligibility_status,
                score_status=t.score_status,
                final_score=t.final_score,
                warnings=list(t.warnings),
            )
            excluded_candidates.append(excl)
            continue

        # D. Check INELIGIBLE
        if t.eligibility_status == EligibilityStatus.INELIGIBLE:
            reasons = [t.eligibility_summary] if t.eligibility_summary else []
            expl = "Team failed mandatory eligibility criteria."
            if t.eligibility_summary:
                expl += f" Reasons: {t.eligibility_summary}"
            excl = ExcludedTeamResult(
                team_id=t.team_id,
                team_name=t.team_name,
                reason_code=ExclusionReason.INELIGIBLE,
                explanation=expl,
                eligibility_status=t.eligibility_status,
                eligibility_reasons=reasons,
                score_status=t.score_status,
                final_score=t.final_score,
                warnings=list(t.warnings),
            )
            excluded_candidates.append(excl)
            continue

        # E. Check NEEDS_REVIEW
        if t.eligibility_status == EligibilityStatus.NEEDS_REVIEW:
            if not include_needs_review:
                needs_review_candidates.append(t)
                reasons = [t.eligibility_summary] if t.eligibility_summary else []
                expl = "Team requires organizer manual review before shortlisting."
                if t.eligibility_summary:
                    expl += f" Review reasons: {t.eligibility_summary}"
                excl = ExcludedTeamResult(
                    team_id=t.team_id,
                    team_name=t.team_name,
                    reason_code=ExclusionReason.NEEDS_REVIEW,
                    explanation=expl,
                    eligibility_status=t.eligibility_status,
                    eligibility_reasons=reasons,
                    score_status=t.score_status,
                    final_score=t.final_score,
                    warnings=list(t.warnings),
                )
                excluded_candidates.append(excl)
                continue
            else:
                # include_needs_review is True: team qualifies for main selection
                qualifying_candidates.append(t)
                continue

        # F. ELIGIBLE or Missing Eligibility Data
        if t.eligibility_status is None:
            has_missing_eligibility = True

        qualifying_candidates.append(t)

    # 3. Add missing eligibility warning if applicable
    if has_missing_eligibility:
        warnings.append(
            "Eligibility was not evaluated for one or more teams; teams were ranked based on score without eligibility verification."
        )

    # 4. Check if tiebreak criterion exists across any team
    if tiebreak_criterion_id:
        found_criterion = any(
            extract_tiebreak_score(t, tiebreak_criterion_id) is not None
            for t in (qualifying_candidates + needs_review_candidates)
        )
        if not found_criterion:
            warnings.append(
                f"Configured tiebreak_criterion_id '{tiebreak_criterion_id}' was not available in candidate score breakdowns."
            )

    # 5. Deterministic Ranking of Qualifying Teams
    sorted_qualifying = sorted(
        qualifying_candidates,
        key=lambda team: build_ranking_sort_key(team, tiebreak_criterion_id),
    )

    # Compute score frequencies to identify ties on primary final_score
    score_counts: dict[float, int] = {}
    for t in sorted_qualifying:
        if t.final_score is not None:
            score_counts[t.final_score] = score_counts.get(t.final_score, 0) + 1

    ranked_teams: list[RankedTeamResult] = []
    for idx, t in enumerate(sorted_qualifying):
        rank_num = idx + 1
        is_tied = score_counts.get(t.final_score, 0) > 1
        tb_score = extract_tiebreak_score(t, tiebreak_criterion_id) if tiebreak_criterion_id else None

        is_selected = rank_num <= top_x
        sel_status = SelectionStatus.SELECTED if is_selected else SelectionStatus.NOT_SELECTED

        if is_selected:
            expl = f"Ranked #{rank_num} of {len(sorted_qualifying)} teams with score {t.final_score:.2f}. Selected for Top-{top_x} shortlist."
        else:
            expl = f"Ranked #{rank_num} of {len(sorted_qualifying)} teams with score {t.final_score:.2f}. Below Top-{top_x} cutoff."

        if t.eligibility_status == EligibilityStatus.NEEDS_REVIEW:
            expl += " (Ranked under include_needs_review=True policy; underlying eligibility remains NEEDS_REVIEW)."

        if is_tied and tiebreak_criterion_id and tb_score is not None:
            expl += f" (Tie on final score resolved using criterion '{tiebreak_criterion_id}': score={tb_score:.4f})."
        elif is_tied:
            expl += f" (Tied on final score {t.final_score:.2f}; sorted by team_id '{t.team_id}')."

        ranked_teams.append(
            RankedTeamResult(
                team_id=t.team_id,
                team_name=t.team_name,
                rank=rank_num,
                final_score=t.final_score,
                score_status=t.score_status,
                eligibility_status=t.eligibility_status,
                eligibility_summary=t.eligibility_summary,
                is_tied=is_tied,
                tiebreak_score=tb_score,
                selection_status=sel_status,
                criteria_breakdowns=t.criteria_breakdowns,
                weight_renormalized=t.weight_renormalized,
                applicable_weight=t.applicable_weight,
                total_configured_weight=t.total_configured_weight,
                warnings=list(t.warnings),
                explanation=expl,
            )
        )

    # 6. Top-X Selection and Cutoff Tie Detection
    selected_teams = ranked_teams[:top_x]

    tie_at_cutoff = False
    if len(ranked_teams) > top_x and top_x > 0:
        last_selected = ranked_teams[top_x - 1]
        first_unselected = ranked_teams[top_x]
        if last_selected.final_score == first_unselected.final_score:
            tie_at_cutoff = True
            cutoff_warning = (
                f"Tie at Top-{top_x} cutoff: Team '{last_selected.team_id}' (rank {top_x}) and "
                f"team '{first_unselected.team_id}' (rank {top_x + 1}) share the same primary final score "
                f"({last_selected.final_score:.2f}). Teams were separated by the configured tie-breaking policy."
            )
            warnings.append(cutoff_warning)

    # 7. Shortage & Review Candidates Recommendation
    shortage = max(0, top_x - len(selected_teams))
    if shortage > 0:
        warnings.append(
            f"Shortage: Requested top_x={top_x}, but only {len(selected_teams)} qualifying team(s) met selection criteria (shortage of {shortage})."
        )

    # Calculate provisional ranks for needs_review teams across all scored candidates
    needs_review_teams: list[RankedTeamResult] = []
    recommended_review_candidates: list[RankedTeamResult] = []

    if needs_review_candidates:
        sorted_review = sorted(
            needs_review_candidates,
            key=lambda team: build_ranking_sort_key(team, tiebreak_criterion_id),
        )

        # Provisional ranking among all scored candidates
        all_scored = sorted(
            qualifying_candidates + needs_review_candidates,
            key=lambda team: build_ranking_sort_key(team, tiebreak_criterion_id),
        )
        provisional_rank_map = {t.team_id: idx + 1 for idx, t in enumerate(all_scored)}

        for rev_t in sorted_review:
            p_rank = provisional_rank_map.get(rev_t.team_id, 0)
            tb_score = extract_tiebreak_score(rev_t, tiebreak_criterion_id) if tiebreak_criterion_id else None
            expl = f"Flagged for manual review (provisional rank #{p_rank} with score {rev_t.final_score:.2f})."
            if rev_t.eligibility_summary:
                expl += f" Review reasons: {rev_t.eligibility_summary}"

            needs_review_teams.append(
                RankedTeamResult(
                    team_id=rev_t.team_id,
                    team_name=rev_t.team_name,
                    rank=p_rank,
                    final_score=rev_t.final_score,
                    score_status=rev_t.score_status,
                    eligibility_status=rev_t.eligibility_status,
                    eligibility_summary=rev_t.eligibility_summary,
                    is_tied=False,
                    tiebreak_score=tb_score,
                    selection_status=SelectionStatus.NEEDS_REVIEW,
                    criteria_breakdowns=rev_t.criteria_breakdowns,
                    weight_renormalized=rev_t.weight_renormalized,
                    applicable_weight=rev_t.applicable_weight,
                    total_configured_weight=rev_t.total_configured_weight,
                    warnings=list(rev_t.warnings),
                    explanation=expl,
                )
            )

        if shortage > 0:
            recommended_review_candidates = needs_review_teams[:shortage]
            warnings.append(
                f"{len(recommended_review_candidates)} highest-ranked NEEDS_REVIEW candidate(s) are recommended for organizer review to potentially fill remaining position(s)."
            )
    elif shortage > 0:
        warnings.append("No scored review candidates available to recommend for remaining positions.")

    # 8. Summary statistics
    cutoff_score = selected_teams[-1].final_score if selected_teams else None

    summary = RankingRunSummary(
        total_teams_evaluated=len(parsed_teams),
        qualifying_teams_count=len(ranked_teams),
        selected_teams_count=len(selected_teams),
        shortage=shortage,
        requested_top_x=top_x,
        tie_at_cutoff=tie_at_cutoff,
        cutoff_score=cutoff_score,
        excluded_count=len(excluded_candidates),
        needs_review_count=len(needs_review_candidates),
        unresolved_count=len(unresolved_candidates),
        ineligible_count=sum(1 for e in excluded_candidates if e.reason_code == ExclusionReason.INELIGIBLE),
        no_score_count=sum(1 for e in excluded_candidates if e.reason_code == ExclusionReason.NO_SCORE),
        disqualified_count=sum(1 for e in excluded_candidates if e.reason_code == ExclusionReason.DISQUALIFIED),
    )

    return RankingRunResponse(
        run_id=final_run_id,
        scoring_run_id=scoring_run_id,
        eligibility_run_id=eligibility_run_id,
        evaluated_at=now_ts,
        top_x=top_x,
        include_needs_review=include_needs_review,
        tiebreak_criterion_id=tiebreak_criterion_id,
        selected_teams=selected_teams,
        ranked_teams=ranked_teams,
        needs_review_teams=needs_review_teams,
        recommended_review_candidates=recommended_review_candidates,
        unresolved_teams=unresolved_candidates,
        excluded_teams=excluded_candidates,
        summary=summary,
        warnings=warnings,
        errors=errors,
    )
