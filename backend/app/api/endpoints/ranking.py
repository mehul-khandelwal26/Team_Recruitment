"""FastAPI endpoints for ranking, Top-X selection, and explainable shortlist auditing."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.ranking.engine import evaluate_ranking
from app.ranking.schemas import RankingEvaluationRequest, RankingRunResponse
from app.ranking.store import default_ranking_run_store
from app.rules.store import get_effective_run
from app.scoring.config_store import default_scoring_config_store
from app.scoring.engine import evaluate_scoring
from app.scoring.schemas import ScoringConfiguration
from app.scoring.store import default_scoring_run_store

router = APIRouter(prefix="/api/ranking", tags=["Ranking"])


@router.post("/evaluate", response_model=RankingRunResponse)
def evaluate_ranking_endpoint(request: RankingEvaluationRequest) -> RankingRunResponse:
    """Execute deterministic Top-X ranking and selection from scoring results or end-to-end evaluation."""
    effective_elig_run = None
    if request.eligibility_run_id:
        effective_elig_run = get_effective_run(request.eligibility_run_id)
        if effective_elig_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Eligibility run '{request.eligibility_run_id}' not found.",
            )

    scoring_results = None
    derived_scoring_run_id = request.scoring_run_id

    # 1. Option A: Load from existing scoring run
    if request.scoring_run_id:
        scoring_run = default_scoring_run_store.get(request.scoring_run_id)
        if scoring_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scoring run '{request.scoring_run_id}' not found.",
            )
        scoring_results = scoring_run.teams

    # 2. Option B: Explicit scoring results payload
    elif request.scoring_results is not None:
        scoring_results = request.scoring_results

    # 3. Option C: Evaluate scoring on the fly from teams & signals
    elif request.teams is not None:
        scoring_config: Optional[ScoringConfiguration] = None
        if request.inline_scoring_config is not None:
            scoring_config = request.inline_scoring_config
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
            teams=request.teams,
            signals=request.signals,
            config=scoring_config,
            eligibility_run_id=request.eligibility_run_id,
            eligibility_results=request.eligibility_results,
        )
        default_scoring_run_store.save(scoring_run)
        scoring_results = scoring_run.teams
        derived_scoring_run_id = scoring_run.run_id

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either scoring_run_id, scoring_results, or teams.",
        )

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


@router.get("/runs", response_model=list[RankingRunResponse])
def list_ranking_runs() -> list[RankingRunResponse]:
    """List all recorded ranking evaluation runs."""
    return default_ranking_run_store.list_runs()
