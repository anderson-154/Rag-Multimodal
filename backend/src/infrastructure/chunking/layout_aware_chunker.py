# backend/src/infrastructure/chunking/layout_aware_chunker.py
from __future__ import annotations

import uuid

from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import Chunk, ChunkType
from src.domain.ports.chunker_port import ChunkerPort
from src.domain.ports.document_parser_port import ParsedBlock, ParsedDocument

_TOKENS_PER_CHAR = 4
_TITLE_MAX_CHARS = 120
_TITLE_FONT_MULTIPLIER = 1.15


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _TOKENS_PER_CHAR)


def _union_bbox(boxes: list[BoundingBox]) -> BoundingBox:
    x0 = min(b.x0 for b in boxes)
    y0 = min(b.y0 for b in boxes)
    x1 = max(b.x1 for b in boxes)
    y1 = max(b.y1 for b in boxes)
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _words(text: str) -> list[str]:
    return text.split()


def _join_words(words: list[str]) -> str:
    return " ".join(words)


def _last_n_words(text: str, n: int) -> list[str]:
    parts = _words(text)
    if n <= 0 or not parts:
        return []
    return parts[-n:]


def _is_title(block: ParsedBlock, body_font: float) -> bool:
    if body_font <= 0:
        return False
    if block.font_size < body_font * _TITLE_FONT_MULTIPLIER:
        return False
    stripped = block.text.strip()
    if len(stripped) == 0:
        return False
    if len(stripped) > _TITLE_MAX_CHARS:
        return False
    if stripped.endswith((".", ":", ",", ";")):
        return False
    return True


class _TitleStack:
    """Maintains the current heading path (e.g. "Cap.1 > Sec 1.2").

    Larger font size means a shallower (more important) heading level.
    Pushing a new title pops every entry whose font size is smaller than
    or equal to the new one, since those represent the same level or a
    deeper nested level that the new title supersedes.
    """

    def __init__(self) -> None:
        self._titles: list[tuple[float, str]] = []

    def push(self, font_size: float, title: str) -> None:
        while self._titles and self._titles[-1][0] <= font_size:
            self._titles.pop()
        self._titles.append((font_size, title))

    def path(self) -> str:
        return " > ".join(title for _, title in self._titles)


class LayoutAwareChunker(ChunkerPort):
    def __init__(self, max_tokens: int, overlap: int) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= max_tokens:
            raise ValueError("overlap must be smaller than max_tokens")
        self._max_tokens = max_tokens
        self._overlap_words = overlap

    def chunk(self, document_id: str, parsed: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        body_font = self._body_font_size(parsed.blocks)

        title_stack = _TitleStack()
        pending_blocks: list[ParsedBlock] = []

        def flush_pending() -> None:
            if not pending_blocks:
                return
            text_blocks = list(pending_blocks)
            chunks.extend(self._build_text_chunks(document_id, title_stack.path(), text_blocks))
            pending_blocks.clear()

        for block in parsed.blocks:
            if _is_title(block, body_font):
                flush_pending()
                title_stack.push(block.font_size, block.text.strip())
                chunks.append(
                    Chunk(
                        id=self._chunk_id(document_id, len(chunks)),
                        content=block.text,
                        hierarchy_path=title_stack.path(),
                        document_id=document_id,
                        page=block.page,
                        bbox=block.bbox,
                        chunk_type=ChunkType.TITLE,
                        parent_id=None,
                        image_ids=[],
                    )
                )
                continue
            pending_blocks.append(block)

        flush_pending()

        for table in parsed.tables:
            path = title_stack.path()
            chunks.append(
                Chunk(
                    id=self._chunk_id(document_id, len(chunks)),
                    content=table.text,
                    hierarchy_path=path,
                    document_id=document_id,
                    page=table.page,
                    bbox=table.bbox,
                    chunk_type=ChunkType.TABLE,
                    parent_id=None,
                    image_ids=[],
                )
            )

        return chunks

    def _body_font_size(self, blocks: list[ParsedBlock]) -> float:
        """Approximates the body-text font size as the smallest font used.

        Titles are then detected as anything sufficiently larger than this
        baseline, which allows multiple nested heading levels to be
        recognized (unlike comparing against the median, which fails when
        a subtitle's font size is close to or equal to the median itself).
        """
        sizes = [b.font_size for b in blocks if b.font_size > 0]
        if not sizes:
            return 0.0
        return float(min(sizes))

    def _build_text_chunks(
        self,
        document_id: str,
        hierarchy_path: str,
        blocks: list[ParsedBlock],
    ) -> list[Chunk]:
        if not blocks:
            return []

        by_page: dict[int, list[ParsedBlock]] = {}
        for block in blocks:
            by_page.setdefault(block.page, []).append(block)

        out: list[Chunk] = []
        for page in sorted(by_page.keys()):
            page_blocks = by_page[page]
            page_chunks = self._split_page_blocks_into_chunks(
                document_id=document_id,
                hierarchy_path=hierarchy_path,
                blocks=page_blocks,
                start_index=len(out),
            )
            out.extend(page_chunks)
        return out

    def _split_page_blocks_into_chunks(
        self,
        document_id: str,
        hierarchy_path: str,
        blocks: list[ParsedBlock],
        start_index: int,
    ) -> list[Chunk]:
        """Greedily packs words from consecutive blocks into chunks.

        Every word from every block is guaranteed to end up in exactly one
        chunk: a new chunk starts only when adding the next word would push
        the current chunk over max_tokens, never by silently skipping
        content. A configurable word-based overlap is carried into the next
        chunk to preserve context across the split boundary.
        """
        chunks: list[Chunk] = []
        current_words: list[str] = []
        current_bboxes: list[BoundingBox] = []
        page = blocks[0].page

        def finalize() -> None:
            if not current_words:
                return
            content = _join_words(current_words)
            bbox = _union_bbox(current_bboxes) if current_bboxes else blocks[0].bbox
            chunks.append(
                Chunk(
                    id=self._chunk_id(document_id, start_index + len(chunks)),
                    content=content,
                    hierarchy_path=hierarchy_path,
                    document_id=document_id,
                    page=page,
                    bbox=bbox,
                    chunk_type=ChunkType.TEXT,
                    parent_id=None,
                    image_ids=[],
                )
            )

        for block in blocks:
            page = block.page
            words_in_block = _words(block.text)
            if not words_in_block:
                if block.bbox not in current_bboxes:
                    current_bboxes.append(block.bbox)
                continue

            for word in words_in_block:
                candidate_words = current_words + [word]
                candidate_tokens = _estimate_tokens(_join_words(candidate_words))

                if candidate_tokens > self._max_tokens and current_words:
                    finalize()
                    overlap = _last_n_words(_join_words(current_words), self._overlap_words)
                    current_words = list(overlap)
                    current_bboxes = [block.bbox] if overlap else []

                current_words.append(word)
                if block.bbox not in current_bboxes:
                    current_bboxes.append(block.bbox)

        finalize()
        return chunks

    def _chunk_id(self, document_id: str, index: int) -> str:
        return f"{document_id}-{index}-{uuid.uuid4().hex[:8]}"
