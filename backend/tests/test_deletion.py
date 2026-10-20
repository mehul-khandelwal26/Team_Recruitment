"""Comprehensive tests for atomic and cascade deletion of datasets, ranking runs, and extraction runs."""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.ingestion.store import default_dataset_store
from app.ranking.store import default_ranking_run_store
from app.signals.store import default_extraction_run_store
from app.schemas.ingestion import DatasetRecord
from app.ranking.schemas import RankingRunResponse, RankingRunSummary
from app.signals.schemas import ExtractionRunResponse


@pytest.fixture(autouse=True)
def clean_stores():
    """Reset stores before and after each test."""
    default_dataset_store.reset()
    default_ranking_run_store.reset()
    default_extraction_run_store.reset()
    yield
    default_dataset_store.reset()
    default_ranking_run_store.reset()
    default_extraction_run_store.reset()


@pytest.fixture
def client():
    return TestClient(app)


def test_delete_ranking_run_success(client: TestClient):
    """Verify deleting a ranking run succeeds and subsequent GET returns 404."""
    run = RankingRunResponse(
        run_id="rank_del_test_1",
        top_x=3,
        selected_teams=[],
        ranked_teams=[],
        needs_review_teams=[],
        recommended_review_candidates=[],
        unresolved_teams=[],
        excluded_teams=[],
        summary=RankingRunSummary(
            top_x=3,
            selected_teams_count=0,
            shortage=3,
            needs_review_count=0,
            excluded_count=0,
            unresolved_count=0,
            tie_at_cutoff=False,
        ),
        evaluated_at="2026-10-20T00:00:00Z",
    )
    default_ranking_run_store.save(run)
    assert default_ranking_run_store.get("rank_del_test_1") is not None

    # Delete run
    res = client.delete("/api/ranking/runs/rank_del_test_1")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["run_id"] == "rank_del_test_1"

    # Verify gone
    assert default_ranking_run_store.get("rank_del_test_1") is None
    get_res = client.get("/api/ranking/runs/rank_del_test_1")
    assert get_res.status_code == 404


def test_delete_ranking_run_not_found(client: TestClient):
    """Verify deleting a non-existent ranking run returns 404."""
    res = client.delete("/api/ranking/runs/non_existent_run_999")
    assert res.status_code == 404


def test_delete_standalone_dataset_success(client: TestClient):
    """Verify deleting a dataset without any dependent runs succeeds cleanly."""
    rec = DatasetRecord(
        dataset_id="ds_del_test_standalone",
        filename="standalone.csv",
        file_type="csv",
        teams_count=5,
        members_count=15,
        uploaded_at="2026-10-20T00:00:00Z",
        created_at="2026-10-20T00:00:00Z",
        payload={"teams": []},
    )
    default_dataset_store.save(rec)

    # Check dependencies count endpoint
    dep_res = client.get("/api/ingestion/datasets/ds_del_test_standalone/dependencies")
    assert dep_res.status_code == 200
    dep_data = dep_res.json()
    assert dep_data["has_dependencies"] is False
    assert dep_data["dependencies"]["total"] == 0

    # Delete dataset without cascade
    res = client.delete("/api/ingestion/datasets/ds_del_test_standalone")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert default_dataset_store.get("ds_del_test_standalone") is None


def test_delete_dataset_with_dependencies_conflict_and_cascade(client: TestClient):
    """Verify deleting a dataset with dependent runs rejects with 409 without cascade, and succeeds with cascade=true."""
    ds_id = "ds_cascade_test_1"
    ext_id = "ext_cascade_test_1"
    rank_id = "rank_cascade_test_1"

    # 1. Dataset
    rec = DatasetRecord(
        dataset_id=ds_id,
        filename="candidates.csv",
        file_type="csv",
        teams_count=3,
        members_count=9,
        uploaded_at="2026-10-20T00:00:00Z",
        created_at="2026-10-20T00:00:00Z",
        payload={"teams": []},
    )
    default_dataset_store.save(rec)

    # 2. Extraction run
    ext = ExtractionRunResponse(
        run_id=ext_id,
        dataset_id=ds_id,
        teams=[],
        selected_signals=["academic_cgpa"],
        analyzers_executed=["academic"],
        total_teams=3,
        total_members=9,
        created_at="2026-10-20T00:00:00Z",
    )
    default_extraction_run_store.save(ext)

    # 3. Ranking run
    rank = RankingRunResponse(
        run_id=rank_id,
        dataset_id=ds_id,
        extraction_run_id=ext_id,
        top_x=3,
        selected_teams=[],
        ranked_teams=[],
        needs_review_teams=[],
        recommended_review_candidates=[],
        unresolved_teams=[],
        excluded_teams=[],
        summary=RankingRunSummary(
            top_x=3,
            selected_teams_count=0,
            shortage=3,
            needs_review_count=0,
            excluded_count=0,
            unresolved_count=0,
            tie_at_cutoff=False,
        ),
        evaluated_at="2026-10-20T00:00:00Z",
    )
    default_ranking_run_store.save(rank)

    # Check dependencies endpoint
    dep_res = client.get(f"/api/ingestion/datasets/{ds_id}/dependencies")
    assert dep_res.status_code == 200
    dep_data = dep_res.json()
    assert dep_data["has_dependencies"] is True
    assert dep_data["dependencies"]["extraction_runs"] == 1
    assert dep_data["dependencies"]["ranking_runs"] == 1
    assert dep_data["dependencies"]["total"] >= 2

    # Attempt delete without cascade -> expect 409 Conflict
    del_conflict = client.delete(f"/api/ingestion/datasets/{ds_id}")
    assert del_conflict.status_code == 409
    assert "Cannot delete dataset" in del_conflict.json()["detail"]["message"]

    # Verify nothing was deleted prematurely
    assert default_dataset_store.get(ds_id) is not None
    assert default_extraction_run_store.get(ext_id) is not None
    assert default_ranking_run_store.get(rank_id) is not None

    # Now delete with cascade=true
    del_cascade = client.delete(f"/api/ingestion/datasets/{ds_id}?cascade=true")
    assert del_cascade.status_code == 200
    assert del_cascade.json()["success"] is True

    # Verify dataset AND dependent runs are all cleanly purged
    assert default_dataset_store.get(ds_id) is None
    assert default_extraction_run_store.get(ext_id) is None
    assert default_ranking_run_store.get(rank_id) is None


def test_delete_extraction_run_conflict_and_cascade(client: TestClient):
    """Verify deleting an extraction run with dependent ranking run rejects with 409, and succeeds with cascade=true."""
    ext_id = "ext_alone_test"
    rank_id = "rank_linked_test"

    ext = ExtractionRunResponse(
        run_id=ext_id,
        teams=[],
        selected_signals=["academic_cgpa"],
        analyzers_executed=["academic"],
        total_teams=2,
        total_members=6,
        created_at="2026-10-20T00:00:00Z",
    )
    default_extraction_run_store.save(ext)

    rank = RankingRunResponse(
        run_id=rank_id,
        extraction_run_id=ext_id,
        top_x=2,
        selected_teams=[],
        ranked_teams=[],
        needs_review_teams=[],
        recommended_review_candidates=[],
        unresolved_teams=[],
        excluded_teams=[],
        summary=RankingRunSummary(
            top_x=2,
            selected_teams_count=0,
            shortage=2,
            needs_review_count=0,
            excluded_count=0,
            unresolved_count=0,
            tie_at_cutoff=False,
        ),
        evaluated_at="2026-10-20T00:00:00Z",
    )
    default_ranking_run_store.save(rank)

    # Check dependencies
    dep_res = client.get(f"/api/signals/runs/{ext_id}/dependencies")
    assert dep_res.status_code == 200
    assert dep_res.json()["dependencies"]["ranking_runs"] == 1

    # Conflict on cascade=false
    conf_res = client.delete(f"/api/signals/runs/{ext_id}")
    assert conf_res.status_code == 409

    # Delete with cascade=true
    del_res = client.delete(f"/api/signals/runs/{ext_id}?cascade=true")
    assert del_res.status_code == 200
    assert default_extraction_run_store.get(ext_id) is None
    assert default_ranking_run_store.get(rank_id) is None


def test_delete_non_existent_dataset_returns_404(client: TestClient):
    """Verify deleting a non-existent dataset returns 404."""
    res = client.delete("/api/ingestion/datasets/fake_id_12345")
    assert res.status_code == 404


def test_delete_non_existent_extraction_run_returns_404(client: TestClient):
    """Verify deleting a non-existent extraction run returns 404."""
    res = client.delete("/api/signals/runs/fake_run_12345")
    assert res.status_code == 404
