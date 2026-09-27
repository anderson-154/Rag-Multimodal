# backend/src/infrastructure/reranker/noop_reranker.py
from __future__ import annotations

from src.domain.ports.reranker_port import RerankHit, RerankerPort


class NoopReranker(RerankerPort):
    def rerank(
        self,
        query: str,
        chunk_ids: list[str],
        chunk_texts: list[str],
        top_n: int,
    ) -> list[RerankHit]:
        hits = [
            RerankHit(chunk_id=cid, score=float(len(chunk_ids) - i))
            for i, cid in enumerate(chunk_ids)
        ]
        return hits[:top_n]
