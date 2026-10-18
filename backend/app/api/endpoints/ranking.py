"""FastAPI endpoints for ranking, Top-X selection, and explainable shortlist auditing."""

from __future__ import annotations

import csv
import io
from typing import Any, Optional, Union

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.ingestion.store import default_dataset_store
from app.ranking.engine import evaluate_ranking
from app.ranking.schemas import (
    RankingEvaluationRequest,
    RankingRunResponse,
    RankingRunSummaryItem,
)
from app.ranking.store import default_ranking_run_store
from app.rules.store import get_effective_run
from app.scoring.config_store import default_scoring_config_store
from app.scoring.engine import evaluate_scoring
from app.scoring.schemas import ScoringConfiguration
from app.scoring.store import default_scoring_run_store
from app.signals.flatten import flatten_extraction_signals
from app.signals.store import default_extraction_run_store

router = APIRouter(prefix="/api/ranking", tags=["Ranking"])


@router.post("/evaluate", response_model=RankingRunResponse)
def evaluate_ranking_endpoint(request: RankingEvaluationRequest) -> RankingRunResponse:
    """Execute deterministic Top-X ranking and selection from scoring results or end-to-end evaluation."""
    # 1. Provenance inheritance from Option A (scoring_run_id)
    if request.scoring_run_id:
        scoring_run = default_scoring_run_store.get(request.scoring_run_id)
        if scoring_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scoring run '{request.scoring_run_id}' not found.",
            )
        if request.dataset_id is None and getattr(scoring_run, "dataset_id", None):
            request.dataset_id = scoring_run.dataset_id
        if request.extraction_run_id is None and getattr(scoring_run, "extraction_run_id", None):
            request.extraction_run_id = scoring_run.extraction_run_id
        if request.eligibility_run_id is None and getattr(scoring_run, "eligibility_run_id", None):
            request.eligibility_run_id = scoring_run.eligibility_run_id

    # 2. Provenance inheritance from eligibility_run_id (supplied or inherited)
    effective_elig_run = None
    if request.eligibility_run_id:
        effective_elig_run = get_effective_run(request.eligibility_run_id)
        if effective_elig_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Eligibility run '{request.eligibility_run_id}' not found.",
            )
        if request.dataset_id is None and getattr(effective_elig_run, "dataset_id", None):
            request.dataset_id = effective_elig_run.dataset_id
        if request.extraction_run_id is None and getattr(effective_elig_run, "extraction_run_id", None):
            request.extraction_run_id = effective_elig_run.extraction_run_id

    # Validate extraction_run_id consistency if present
    if request.extraction_run_id:
        ext_run = default_extraction_run_store.get(request.extraction_run_id)
        if ext_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extraction run '{request.extraction_run_id}' not found.",
            )
        if request.dataset_id and getattr(ext_run, "dataset_id", None) and ext_run.dataset_id != request.dataset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction run dataset_id '{ext_run.dataset_id}' does not match supplied dataset_id '{request.dataset_id}'.",
            )

    scoring_results = None
    derived_scoring_run_id = request.scoring_run_id

    # Option A: Loaded from existing scoring run
    if request.scoring_run_id:
        scoring_run = default_scoring_run_store.get(request.scoring_run_id)
        scoring_results = scoring_run.teams

    # Option B: Explicit scoring results payload
    elif request.scoring_results is not None:
        scoring_results = request.scoring_results

    # Option C: Evaluate scoring on the fly from teams & signals (or dataset_id / extraction_run_id)
    else:
        teams_to_use = request.teams
        if teams_to_use is None and request.dataset_id:
            ds = default_dataset_store.get(request.dataset_id)
            if ds is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dataset '{request.dataset_id}' not found.",
                )
            teams_to_use = ds.payload.get("teams", [])
        elif teams_to_use is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either scoring_run_id, scoring_results, teams, or dataset_id.",
            )

        signals_to_use = request.signals
        if signals_to_use is None and request.extraction_run_id:
            ext_run = default_extraction_run_store.get(request.extraction_run_id)
            signals_to_use = flatten_extraction_signals(ext_run)

        scoring_config: Optional[ScoringConfiguration] = None
        is_inline_scoring = False
        if request.inline_scoring_config is not None:
            scoring_config = request.inline_scoring_config
            is_inline_scoring = True
        else:
            cfg_id = request.scoring_config_id or "balanced"
            scoring_config = default_scoring_config_store.get(
                cfg_id, version=request.scoring_config_version
            )
            if scoring_config is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scoring configuration '{cfg_id}' not found.",
                )

        scoring_run = evaluate_scoring(
            teams=teams_to_use,
            signals=signals_to_use,
            config=scoring_config,
            eligibility_run_id=request.eligibility_run_id,
            eligibility_results=request.eligibility_results,
        )
        scoring_run.config_source = "inline" if is_inline_scoring else "stored"
        scoring_run.config_snapshot = scoring_config.model_copy(deep=True) if is_inline_scoring else None
        scoring_run.eligibility_run_id = request.eligibility_run_id
        if request.dataset_id:
            scoring_run.dataset_id = request.dataset_id
        if request.extraction_run_id:
            scoring_run.extraction_run_id = request.extraction_run_id
        default_scoring_run_store.save(scoring_run)
        scoring_results = scoring_run.teams
        derived_scoring_run_id = scoring_run.run_id

    # 4. Execute ranking and Top-X selection
    ranking_run = evaluate_ranking(
        scoring_results=scoring_results,
        top_x=request.top_x,
        tiebreak_criterion_id=request.tiebreak_criterion_id,
        include_needs_review=request.include_needs_review,
        scoring_run_id=derived_scoring_run_id,
        eligibility_run_id=request.eligibility_run_id,
        evaluated_at=request.evaluated_at,
        run_id=request.run_id,
        effective_eligibility_run=effective_elig_run,
    )

    if request.dataset_id:
        ranking_run.dataset_id = request.dataset_id
    if request.extraction_run_id:
        ranking_run.extraction_run_id = request.extraction_run_id

    # 5. Persist run record
    default_ranking_run_store.save(ranking_run)
    return ranking_run


@router.get("/runs/{run_id}", response_model=RankingRunResponse)
def get_ranking_run(run_id: str) -> RankingRunResponse:
    """Retrieve a recorded ranking run with all shortlisted teams, breakdowns, and exclusions."""
    record = default_ranking_run_store.get(run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ranking run '{run_id}' not found.",
        )
    return record


@router.get("/runs", response_model=Union[list[RankingRunResponse], list[RankingRunSummaryItem]])
def list_ranking_runs(
    summary: bool = Query(default=False, description="Return lightweight summary objects without team lists"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of items to return (1-200)"),
) -> Union[list[RankingRunResponse], list[RankingRunSummaryItem]]:
    """List all recorded ranking evaluation runs."""
    if summary:
        return default_ranking_run_store.list_summaries(limit=limit)
    return default_ranking_run_store.list_runs()



@router.get("/runs/{run_id}/export")
def export_ranking_run_csv(run_id: str) -> Response:
    """Export a recorded ranking run as a CSV file with formula-injection mitigation."""
    record = default_ranking_run_store.get(run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ranking run '{run_id}' not found.",
        )

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "selection_status",
        "rank",
        "team_id",
        "team_name",
        "final_score",
        "eligibility_status",
        "score_status",
        "is_tied",
        "criteria_evaluated",
        "reason_code",
        "explanation",
    ]
    writer.writerow(headers)

    def sanitize(val: Any) -> Any:
        if val is None:
            return ""
        if isinstance(val, bool):
            return "True" if val else "False"
        val_str = str(val)
        if val_str and val_str[0] in ("=", "+", "-", "@"):
            return "'" + val_str
        return val_str

    def format_score(score: Optional[float]) -> str:
        if score is None:
            return ""
        return f"{score:.2f}"

    def format_criteria(team: Any) -> str:
        breakdowns = getattr(team, "criteria_breakdowns", []) or []
        if not breakdowns:
            return ""
        total = len(breakdowns)
        evaluated = sum(
            1 for c in breakdowns
            if getattr(c, "is_applicable", False) and getattr(c, "team_criterion_score", None) is not None
        )
        return f"{evaluated} of {total}"

    # 1. Selected teams
    for team in record.selected_teams:
        writer.writerow([
            sanitize("SELECTED"),
            sanitize(team.rank),
            sanitize(team.team_id),
            sanitize(team.team_name),
            sanitize(format_score(team.final_score)),
            sanitize(team.eligibility_status.value if team.eligibility_status else ""),
            sanitize(team.score_status.value if team.score_status else ""),
            sanitize(team.is_tied),
            sanitize(format_criteria(team)),
            sanitize(""),
            sanitize(team.explanation),
        ])

    # 2. Other ranked teams
    selected_ids = {t.team_id for t in record.selected_teams}
    for team in record.ranked_teams:
        if team.team_id in selected_ids:
            continue
        sel_label = team.selection_status.value if hasattr(team.selection_status, "value") else str(team.selection_status)
        writer.writerow([
            sanitize(sel_label),
            sanitize(team.rank),
            sanitize(team.team_id),
            sanitize(team.team_name),
            sanitize(format_score(team.final_score)),
            sanitize(team.eligibility_status.value if team.eligibility_status else ""),
            sanitize(team.score_status.value if team.score_status else ""),
            sanitize(team.is_tied),
            sanitize(format_criteria(team)),
            sanitize(""),
            sanitize(team.explanation),
        ])

    # 3. Needs-review teams
    for team in record.needs_review_teams:
        writer.writerow([
            sanitize("NEEDS_REVIEW"),
            sanitize(team.rank if getattr(team, "rank", None) is not None else ""),
            sanitize(team.team_id),
            sanitize(team.team_name),
            sanitize(format_score(team.final_score)),
            sanitize(team.eligibility_status.value if team.eligibility_status else ""),
            sanitize(team.score_status.value if team.score_status else ""),
            sanitize(team.is_tied if getattr(team, "is_tied", None) is not None else ""),
            sanitize(format_criteria(team)),
            sanitize(""),
            sanitize(team.explanation),
        ])

    # 4. Unresolved teams
    unresolved_ids = set()
    for team in record.unresolved_teams:
        unresolved_ids.add(team.team_id)
        rc = team.reason_code.value if hasattr(team.reason_code, "value") else str(team.reason_code)
        writer.writerow([
            sanitize("UNRESOLVED"),
            sanitize(""),
            sanitize(team.team_id),
            sanitize(team.team_name),
            sanitize(format_score(team.final_score)),
            sanitize(team.eligibility_status.value if team.eligibility_status else ""),
            sanitize(team.score_status.value if team.score_status else ""),
            sanitize(""),
            sanitize(""),
            sanitize(rc),
            sanitize(team.explanation),
        ])

    # 5. Excluded teams
    for team in record.excluded_teams:
        if team.team_id in unresolved_ids:
            continue
        rc = team.reason_code.value if hasattr(team.reason_code, "value") else str(team.reason_code)
        writer.writerow([
            sanitize("EXCLUDED"),
            sanitize(""),
            sanitize(team.team_id),
            sanitize(team.team_name),
            sanitize(format_score(team.final_score)),
            sanitize(team.eligibility_status.value if team.eligibility_status else ""),
            sanitize(team.score_status.value if team.score_status else ""),
            sanitize(""),
            sanitize(""),
            sanitize(rc),
            sanitize(team.explanation),
        ])

    csv_content = output.getvalue()
    bom_content = csv_content.encode("utf-8-sig")

    return Response(
        content=bom_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ranking_run_{run_id}.csv"',
        },
    )
