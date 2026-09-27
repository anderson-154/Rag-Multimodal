# backend/tests/unit/application/test_query_use_case.py
from __future__ import annotations

from src.application.prompts.rag_prompt import NO_INFO_MARKER
from src.application.services.rrf import reciprocal_rank_fusion
from src.application.use_cases.query_use_case import QueryUseCase
from src.domain.entities.answer import Query
from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import Chunk, ChunkType
from src.domain.ports.vector_store_port import SearchResult
from tests.unit.application.fakes import FakeEmbedder, FakeLLM, FakeReranker, FakeVectorStore


def _chunk_payload(chunk: Chunk) -> dict[str, object]:
    return {
        "content": chunk.content,
        "hierarchy_path": chunk.hierarchy_path,
        "document_id": chunk.document_id,
        "page": chunk.page,
        "bbox": chunk.bbox,
        "chunk_type": chunk.chunk_type,
        "parent_id": chunk.parent_id,
        "image_ids": list(chunk.image_ids),
    }


class TestQueryUseCaseEmptyResults:
    def test_no_results_does_not_call_llm_and_returns_no_info(self) -> None:
        embedder = FakeEmbedder()
        vector_store = FakeVectorStore()
        reranker = FakeReranker()
        llm = FakeLLM()

        use_case = QueryUseCase(embedder, vector_store, reranker, llm, top_k=5, top_n=3)
        answer = use_case.execute(Query(text="que pasa?", top_k=5))

        assert answer.text == NO_INFO_MARKER
        assert answer.is_grounded is False
        assert answer.citations == []
        assert llm.message_logs == []
        assert reranker.calls == []


class TestQueryUseCaseWithChunks:
    def test_prompt_sent_contains_chunk_contents(self) -> None:
        bb = BoundingBox(0, 0, 1, 1)
        chunk_a = Chunk(
            id="c1",
            content="Contenido del chunk A",
            hierarchy_path="1/2",
            document_id="manual.pdf",
            page=3,
            bbox=bb,
            chunk_type=ChunkType.TEXT,
            image_ids=["img1"],
        )
        chunk_b = Chunk(
            id="c2",
            content="Contenido del chunk B",
            hierarchy_path="1/3",
            document_id="manual.pdf",
            page=5,
            bbox=bb,
            chunk_type=ChunkType.TEXT,
            image_ids=[],
        )

        embedder = FakeEmbedder()
        vector_store = FakeVectorStore(
            semantic_results=[
                SearchResult(chunk_id="c1", score=0.9, source="semantic"),
                SearchResult(chunk_id="c2", score=0.8, source="semantic"),
            ],
            keyword_results=[
                SearchResult(chunk_id="c2", score=0.7, source="keyword"),
            ],
            chunks_data={
                "c1": _chunk_payload(chunk_a),
                "c2": _chunk_payload(chunk_b),
            },
        )
        reranker = FakeReranker()
        llm = FakeLLM(response_text="Respuesta citada. [manual.pdf, p.3]")

        use_case = QueryUseCase(embedder, vector_store, reranker, llm, top_k=5, top_n=3)
        use_case.execute(Query(text="¿qué dice el chunk A?", top_k=5))

        assert len(llm.message_logs) == 1
        messages = llm.message_logs[0]
        assert messages[0].role == "system"
        user_prompt = messages[1].content
        assert "Contenido del chunk A" in user_prompt
        assert "Contenido del chunk B" in user_prompt
        assert "[manual.pdf, p.3]" in user_prompt
        assert "[manual.pdf, p.5]" in user_prompt
        assert "1/2" in user_prompt
        assert "1/3" in user_prompt

    def test_citations_include_document_page_and_image_ids(self) -> None:
        bb = BoundingBox(0, 0, 1, 1)
        chunk_a = Chunk(
            id="c1",
            content="a",
            hierarchy_path="1",
            document_id="manual.pdf",
            page=3,
            bbox=bb,
            chunk_type=ChunkType.TEXT,
            image_ids=["img1", "img2"],
        )
        chunk_b = Chunk(
            id="c2",
            content="b",
            hierarchy_path="2",
            document_id="manual.pdf",
            page=3,
            bbox=bb,
            chunk_type=ChunkType.TEXT,
            image_ids=["img3"],
        )

        embedder = FakeEmbedder()
        vector_store = FakeVectorStore(
            semantic_results=[
                SearchResult(chunk_id="c1", score=0.9),
                SearchResult(chunk_id="c2", score=0.85),
            ],
            keyword_results=[],
            chunks_data={
                "c1": _chunk_payload(chunk_a),
                "c2": _chunk_payload(chunk_b),
            },
        )
        reranker = FakeReranker()
        llm = FakeLLM(response_text="Respuesta.")

        use_case = QueryUseCase(embedder, vector_store, reranker, llm, top_k=5, top_n=3)
        answer = use_case.execute(Query(text="pregunta", top_k=5))

        doc_pages = {(c.document_name, c.page) for c in answer.citations}
        assert (chunk_a.document_id, chunk_a.page) in doc_pages
        citation = next(
            c for c in answer.citations if c.document_name == "manual.pdf" and c.page == 3
        )
        assert "img1" in citation.image_ids
        assert "img2" in citation.image_ids
        assert "img3" in citation.image_ids
        assert len(answer.citations) == 1

    def test_answer_with_no_info_marker_is_not_grounded(self) -> None:
        bb = BoundingBox(0, 0, 1, 1)
        chunk = Chunk(
            id="c1",
            content="irrelevante",
            hierarchy_path="1",
            document_id="a.pdf",
            page=1,
            bbox=bb,
            chunk_type=ChunkType.TEXT,
            image_ids=[],
        )

        embedder = FakeEmbedder()
        vector_store = FakeVectorStore(
            semantic_results=[SearchResult(chunk_id="c1", score=0.5)],
            keyword_results=[],
            chunks_data={"c1": _chunk_payload(chunk)},
        )
        reranker = FakeReranker()
        llm = FakeLLM(response_text=NO_INFO_MARKER)

        use_case = QueryUseCase(embedder, vector_store, reranker, llm, top_k=5, top_n=3)
        answer = use_case.execute(Query(text="q", top_k=5))

        assert answer.text == NO_INFO_MARKER
        assert answer.is_grounded is False


class TestReciprocalRankFusion:
    def test_rrf_merges_and_orders_by_sum(self) -> None:
        r1 = [
            SearchResult(chunk_id="a", score=0.9, source="semantic"),
            SearchResult(chunk_id="b", score=0.8, source="semantic"),
            SearchResult(chunk_id="c", score=0.1, source="semantic"),
        ]
        r2 = [
            SearchResult(chunk_id="c", score=0.95, source="keyword"),
            SearchResult(chunk_id="a", score=0.7, source="keyword"),
            SearchResult(chunk_id="d", score=0.6, source="keyword"),
        ]
        fused = reciprocal_rank_fusion([r1, r2], k=60)
        ids = [h.chunk_id for h in fused]
        # a = 1/61 + 1/62 ~ 0.032524
        # c = 1/63 + 1/61 ~ 0.032288
        # b = 1/62 ~ 0.016129
        # d = 1/63 ~ 0.015873
        assert ids[0] == "a"
        assert ids[1] == "c"
        assert ids[2] == "b"
        assert ids[3] == "d"

    def test_rrf_empty_rankings(self) -> None:
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []

    def test_rrf_single_ranking_preserves_order(self) -> None:
        r = [
            SearchResult(chunk_id="x", score=1.0),
            SearchResult(chunk_id="y", score=0.9),
            SearchResult(chunk_id="z", score=0.8),
        ]
        fused = reciprocal_rank_fusion([r])
        assert [h.chunk_id for h in fused] == ["x", "y", "z"]
