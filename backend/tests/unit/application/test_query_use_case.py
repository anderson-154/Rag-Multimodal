# backend/tests/unit/application/test_query_use_case.py
from __future__ import annotations

from src.application.prompts.rag_prompt import NO_INFO_MARKER, SYSTEM_PROMPT
from src.application.services.rrf import reciprocal_rank_fusion
from src.application.use_cases.query_use_case import QueryUseCase
from src.domain.entities.answer import Query
from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import Chunk, ChunkType
from src.domain.ports.vector_store_port import SearchResult
from tests.unit.application.fakes import FakeEmbedder, FakeLLM, FakeReranker, FakeVectorStore

_BBOX = BoundingBox(0, 0, 1, 1)


def _make_chunk(
    chunk_id: str,
    content: str = "contenido",
    document_id: str = "manual.pdf",
    page: int = 1,
    hierarchy_path: str = "1",
    image_ids: list[str] | None = None,
) -> Chunk:
    return Chunk(
        id=chunk_id,
        content=content,
        hierarchy_path=hierarchy_path,
        document_id=document_id,
        page=page,
        bbox=_BBOX,
        chunk_type=ChunkType.TEXT,
        image_ids=list(image_ids or []),
    )


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
        assert llm.call_log == []
        assert reranker.calls == []
        assert len(embedder.called_queries) == 1
        assert embedder.called_queries[0] == "que pasa?"


class TestQueryUseCaseWithChunks:
    def test_prompt_sent_contains_chunk_contents_and_system_prompt(self) -> None:
        chunk_a = _make_chunk(
            "c1",
            content="Contenido del chunk A",
            page=3,
            hierarchy_path="1/2",
            image_ids=["img1"],
        )
        chunk_b = _make_chunk(
            "c2",
            content="Contenido del chunk B",
            page=5,
            hierarchy_path="1/3",
        )

        embedder = FakeEmbedder()
        vector_store = FakeVectorStore(
            semantic_results=[
                SearchResult(chunk=chunk_a, score=0.9, source="semantic"),
                SearchResult(chunk=chunk_b, score=0.8, source="semantic"),
            ],
            keyword_results=[
                SearchResult(chunk=chunk_b, score=0.7, source="keyword"),
            ],
        )
        reranker = FakeReranker()
        llm = FakeLLM(response_text="Respuesta citada. [manual.pdf, p.3]")

        use_case = QueryUseCase(embedder, vector_store, reranker, llm, top_k=5, top_n=3)
        use_case.execute(Query(text="¿qué dice el chunk A?", top_k=5))

        assert len(llm.call_log) == 1
        messages = llm.call_log[0]
        system_messages = [m for m in messages if m.role == "system"]
        user_messages = [m for m in messages if m.role == "user"]
        assert system_messages and system_messages[0].content == SYSTEM_PROMPT
        user_prompt = user_messages[0].content
        assert "Contenido del chunk A" in user_prompt
        assert "Contenido del chunk B" in user_prompt
        assert "[manual.pdf, p.3]" in user_prompt
        assert "[manual.pdf, p.5]" in user_prompt
        assert "1/2" in user_prompt
        assert "1/3" in user_prompt

    def test_citations_include_document_page_and_image_ids(self) -> None:
        chunk_a = _make_chunk("c1", content="a", page=3, image_ids=["img1", "img2"])
        chunk_b = _make_chunk("c2", content="b", page=3, image_ids=["img3"])

        embedder = FakeEmbedder()
        vector_store = FakeVectorStore(
            semantic_results=[
                SearchResult(chunk=chunk_a, score=0.9),
                SearchResult(chunk=chunk_b, score=0.85),
            ],
            keyword_results=[],
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
        chunk = _make_chunk("c1", content="irrelevante", document_id="a.pdf", page=1)

        embedder = FakeEmbedder()
        vector_store = FakeVectorStore(
            semantic_results=[SearchResult(chunk=chunk, score=0.5)],
            keyword_results=[],
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
            SearchResult(chunk=_make_chunk("a"), score=0.9, source="semantic"),
            SearchResult(chunk=_make_chunk("b"), score=0.8, source="semantic"),
            SearchResult(chunk=_make_chunk("c"), score=0.1, source="semantic"),
        ]
        r2 = [
            SearchResult(chunk=_make_chunk("c"), score=0.95, source="keyword"),
            SearchResult(chunk=_make_chunk("a"), score=0.7, source="keyword"),
            SearchResult(chunk=_make_chunk("d"), score=0.6, source="keyword"),
        ]
        fused = reciprocal_rank_fusion([r1, r2], k=60)
        ids = [h.chunk.id for h in fused]
        assert ids[0] == "a"
        assert ids[1] == "c"
        assert ids[2] == "b"
        assert ids[3] == "d"

    def test_rrf_empty_rankings(self) -> None:
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []

    def test_rrf_single_ranking_preserves_order(self) -> None:
        r = [
            SearchResult(chunk=_make_chunk("x"), score=1.0),
            SearchResult(chunk=_make_chunk("y"), score=0.9),
            SearchResult(chunk=_make_chunk("z"), score=0.8),
        ]
        fused = reciprocal_rank_fusion([r])
        assert [h.chunk.id for h in fused] == ["x", "y", "z"]
