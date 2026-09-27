# backend/tests/unit/infrastructure/test_layout_aware_chunker.py
from __future__ import annotations

from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import ChunkType
from src.domain.ports.document_parser_port import ParsedBlock, ParsedDocument
from src.infrastructure.chunking.layout_aware_chunker import LayoutAwareChunker


def _bbox(y: int, h: int = 10) -> BoundingBox:
    return BoundingBox(x0=0, y0=y, x1=100, y1=y + h)


class TestLayoutAwareChunkerTitles:
    def test_hierarchy_path_from_nested_titles(self) -> None:
        title_1 = ParsedBlock(
            text="Introducción", page=1, bbox=_bbox(0, 20), block_type="text", font_size=20.0
        )
        sub_1 = ParsedBlock(
            text="Objetivos",
            page=1,
            bbox=_bbox(30, 16),
            block_type="text",
            font_size=16.0,
        )
        body = ParsedBlock(
            text="Cuerpo normal pequeño.",
            page=1,
            bbox=_bbox(60, 12),
            block_type="text",
            font_size=10.0,
        )
        parsed = ParsedDocument(
            filename="a.pdf", total_pages=1, blocks=[title_1, sub_1, body], tables=[], images=[]
        )

        chunker = LayoutAwareChunker(max_tokens=500, overlap=10)
        chunks = chunker.chunk(document_id="doc1", parsed=parsed)

        text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]
        assert len(text_chunks) == 1
        assert text_chunks[0].hierarchy_path == "Introducción > Objetivos"

        title_chunks = [c for c in chunks if c.chunk_type == ChunkType.TITLE]
        assert [c.content for c in title_chunks] == ["Introducción", "Objetivos"]
        assert title_chunks[0].hierarchy_path == "Introducción"
        assert title_chunks[1].hierarchy_path == "Introducción > Objetivos"


class TestLayoutAwareChunkerMaxTokens:
    def test_respects_max_tokens_on_block_boundary(self) -> None:
        max_chars_per_chunk = 4 * 40  # 40 tokens aprox
        block_1 = ParsedBlock(
            text="a " * (max_chars_per_chunk // 2),
            page=1,
            bbox=_bbox(0),
            block_type="text",
            font_size=10.0,
        )
        block_2 = ParsedBlock(
            text="b " * (max_chars_per_chunk // 2),
            page=1,
            bbox=_bbox(20),
            block_type="text",
            font_size=10.0,
        )
        block_3 = ParsedBlock(
            text="c " * (max_chars_per_chunk // 2),
            page=1,
            bbox=_bbox(40),
            block_type="text",
            font_size=10.0,
        )
        parsed = ParsedDocument(
            filename="big.pdf",
            total_pages=1,
            blocks=[block_1, block_2, block_3],
            tables=[],
            images=[],
        )

        chunker = LayoutAwareChunker(max_tokens=40, overlap=0)
        chunks = chunker.chunk(document_id="doc-big", parsed=parsed)
        for chunk in chunks:
            tokens_est = len(chunk.content) // 4
            assert tokens_est <= 40 or len(chunks) == 1
        assert len(chunks) >= 2


class TestLayoutAwareChunkerTables:
    def test_table_never_splits_and_has_own_chunk(self) -> None:
        table_md = "| Col | Col2 |\n|---|---|\n" + "\n".join(
            [f"| V{i} | X{i} |" for i in range(200)]
        )
        table = ParsedBlock(
            text=table_md,
            page=1,
            bbox=_bbox(0, 500),
            block_type="table",
            font_size=0.0,
        )
        parsed = ParsedDocument(
            filename="tbl.pdf", total_pages=1, blocks=[], tables=[table], images=[]
        )
        chunker = LayoutAwareChunker(max_tokens=10, overlap=0)
        chunks = chunker.chunk(document_id="doc-tbl", parsed=parsed)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == ChunkType.TABLE
        assert chunks[0].content == table_md


class TestLayoutAwareChunkerBbox:
    def test_bbox_is_union_of_blocks(self) -> None:
        b1 = ParsedBlock(
            text="uno",
            page=1,
            bbox=BoundingBox(x0=10, y0=20, x1=80, y1=40),
            block_type="text",
            font_size=10.0,
        )
        b2 = ParsedBlock(
            text="dos",
            page=1,
            bbox=BoundingBox(x0=5, y0=50, x1=90, y1=70),
            block_type="text",
            font_size=10.0,
        )
        parsed = ParsedDocument(
            filename="bbox.pdf", total_pages=1, blocks=[b1, b2], tables=[], images=[]
        )
        chunker = LayoutAwareChunker(max_tokens=500, overlap=0)
        chunks = chunker.chunk(document_id="doc-bbox", parsed=parsed)
        assert len(chunks) == 1
        bb = chunks[0].bbox
        assert bb.x0 == 5
        assert bb.y0 == 20
        assert bb.x1 == 90
        assert bb.y1 == 70
