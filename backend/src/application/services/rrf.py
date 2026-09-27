from __future__ import annotations

from src.domain.ports.vector_store_port import SearchResult


def reciprocal_rank_fusion(rankings: list[list[SearchResult]], k: int = 60) -> list[SearchResult]:
    """Merges multiple rankings of SearchResult using Reciprocal Rank Fusion.

    For each chunk, sums 1/(k + rank) across every ranking it appears in.
    Results are returned ordered by that fused score, descending. When a chunk
    appears in more than one ranking, the SearchResult with the highest raw
    score is kept as the representative instance.
    """
    scores: dict[str, float] = {}
    best_result: dict[str, SearchResult] = {}

    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            chunk_id = result.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

            current_best = best_result.get(chunk_id)
            if current_best is None or result.score > current_best.score:
                best_result[chunk_id] = result

    ordered_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [best_result[chunk_id] for chunk_id in ordered_ids]
