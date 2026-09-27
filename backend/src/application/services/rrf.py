# backend/src/application/services/rrf.py
from __future__ import annotations

from src.domain.ports.vector_store_port import SearchResult


def reciprocal_rank_fusion(
    rankings: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    scores: dict[str, float] = {}
    best_source: dict[str, str] = {}

    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            s = 1.0 / (k + rank + 1)
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + s
            if hit.chunk_id not in best_source:
                best_source[hit.chunk_id] = hit.source

    ordered_ids = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [
        SearchResult(chunk_id=cid, score=score, source=best_source[cid])
        for cid, score in ordered_ids
    ]
