"""Helper utilities to flatten nested signal extraction results."""

from __future__ import annotations

from typing import Any

from app.signals.schemas import ExtractionRunResponse


def flatten_extraction_signals(run: ExtractionRunResponse | dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten an ExtractionRunResponse into a list of MemberSignals dictionaries.

    Converts:
        {teams: [{member_results: [{member_id: ..., signals: [...]}]}]}
    Into:
        [{"member_id": ..., "signals": [...]}]

    Args:
        run: An ExtractionRunResponse instance or equivalent dictionary.

    Returns:
        List of dicts with 'member_id' and 'signals' (serialized signal dicts).
    """
    flat: list[dict[str, Any]] = []

    if isinstance(run, ExtractionRunResponse):
        for team in run.teams:
            for mem_res in team.member_results:
                flat.append({
                    "member_id": mem_res.member_id,
                    "signals": [s.model_dump(mode="json") for s in mem_res.signals],
                })
    elif isinstance(run, dict):
        teams = run.get("teams", [])
        for team in teams:
            member_results = (
                team.get("member_results", [])
                if isinstance(team, dict)
                else getattr(team, "member_results", [])
            )
            for mem_res in member_results:
                if isinstance(mem_res, dict):
                    m_id = mem_res.get("member_id", "")
                    sigs = mem_res.get("signals", [])
                    serialized_sigs = []
                    for s in sigs:
                        if hasattr(s, "model_dump"):
                            serialized_sigs.append(s.model_dump(mode="json"))
                        else:
                            serialized_sigs.append(s)
                    flat.append({
                        "member_id": m_id,
                        "signals": serialized_sigs,
                    })
                elif hasattr(mem_res, "member_id"):
                    sigs = getattr(mem_res, "signals", [])
                    flat.append({
                        "member_id": mem_res.member_id,
                        "signals": [
                            s.model_dump(mode="json") if hasattr(s, "model_dump") else s
                            for s in sigs
                        ],
                    })

    return flat
