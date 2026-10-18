"""In-memory storage and protocol interfaces for ranking and Top-X selection runs.

Ensures:
- Historical reproducibility of ranking and shortlist runs.
- Storage behind Protocol interface to facilitate future database persistence.
- Complete snapshot of input parameters, selected teams, excluded reasons, and warnings.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.ranking.schemas import RankingRunResponse


class RankingRunStoreProtocol(Protocol):
    """Protocol defining persistence interface for ranking runs."""

    def save(self, record: RankingRunResponse) -> None: ...
    def get(self, run_id: str) -> Optional[RankingRunResponse]: ...
    def list_runs(self) -> list[RankingRunResponse]: ...
    def list_summaries(self, limit: int = 50) -> list[RankingRunSummaryItem]: ...
    def reset(self) -> None: ...


class InMemoryRankingRunStore:
    """Thread-safe in-memory store for evaluation ranking runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RankingRunResponse] = {}

    def save(self, record: RankingRunResponse) -> None:
        self._runs[record.run_id] = record.model_copy(deep=True)

    def get(self, run_id: str) -> Optional[RankingRunResponse]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_runs(self) -> list[RankingRunResponse]:
        return [r.model_copy(deep=True) for r in self._runs.values()]

    def list_summaries(self, limit: int = 50) -> list[RankingRunSummaryItem]:
        from app.ranking.schemas import RankingRunSummaryItem
        from app.storage import default_storage_factory

        records = list(self._runs.values())
        records.sort(
            key=lambda r: (
                str(r.evaluated_at or ""),
                str(r.run_id or ""),
            ),
            reverse=True,
        )
        items = records[:limit]

        elig_store = default_storage_factory.get_eligibility_run_store()
        scoring_store = default_storage_factory.get_scoring_run_store()
        dataset_store = default_storage_factory.get_dataset_store()

        summaries = []
        for r in items:
            s = r.summary
            elig_cfg_id = None
            elig_cfg_ver = None
            if r.eligibility_run_id:
                try:
                    elig_run = elig_store.get(r.eligibility_run_id)
                    if elig_run:
                        elig_cfg_id = getattr(elig_run, "config_id", None)
                        elig_cfg_ver = getattr(elig_run, "config_version", None)
                except Exception:
                    pass

            score_cfg_id = None
            score_cfg_ver = None
            score_cfg_source = None
            if r.scoring_run_id:
                try:
                    score_run = scoring_store.get(r.scoring_run_id)
                    if score_run:
                        score_cfg_id = getattr(score_run, "config_id", None)
                        score_cfg_ver = getattr(score_run, "config_version", None)
                        score_cfg_source = getattr(score_run, "config_source", None)
                except Exception:
                    pass

            ds_filename = None
            if r.dataset_id:
                try:
                    ds = dataset_store.get(r.dataset_id)
                    if ds:
                        ds_filename = getattr(ds, "filename", None)
                except Exception:
                    pass

            selected_val = s.selected_teams_count if s else 0
            shortage_val = s.shortage if s else 0
            needs_review_val = s.needs_review_count if s else 0
            excluded_val = s.excluded_count if s else 0
            unresolved_val = s.unresolved_count if s else 0
            tie_val = s.tie_at_cutoff if s else False

            summaries.append(
                RankingRunSummaryItem(
                    run_id=r.run_id,
                    evaluated_at=str(r.evaluated_at or ""),
                    dataset_id=r.dataset_id,
                    extraction_run_id=r.extraction_run_id,
                    scoring_run_id=r.scoring_run_id,
                    eligibility_run_id=r.eligibility_run_id,
                    top_x=r.top_x,
                    include_needs_review=r.include_needs_review,
                    tiebreak_criterion_id=r.tiebreak_criterion_id,
                    selected_teams_count=selected_val,
                    selected=selected_val,
                    shortage=shortage_val,
                    needs_review_count=needs_review_val,
                    needs_review=needs_review_val,
                    excluded_count=excluded_val,
                    excluded=excluded_val,
                    unresolved_count=unresolved_val,
                    unresolved=unresolved_val,
                    tie_at_cutoff=tie_val,
                    eligibility_config_id=elig_cfg_id,
                    eligibility_config_version=elig_cfg_ver,
                    scoring_config_id=score_cfg_id,
                    scoring_config_version=score_cfg_ver,
                    scoring_config_source=score_cfg_source,
                    dataset_filename=ds_filename,
                )
            )
        return summaries


    def reset(self) -> None:
        self._runs.clear()


from app.storage import DelegatingRankingRunStore

default_ranking_run_store = DelegatingRankingRunStore()
