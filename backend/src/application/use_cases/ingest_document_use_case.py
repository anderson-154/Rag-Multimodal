# backend/src/application/use_cases/ingest_document_use_case.py
from __future__ import annotations

from collections.abc import Callable
from math import ceil

from src.domain.entities.chunk import Chunk
from src.domain.entities.document import ExtractedImage
from src.domain.ports.chunker_port import ChunkerPort
from src.domain.ports.document_parser_port import (
    DocumentParserPort,
    ParsedImage,
)
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.vector_store_port import VectorStorePort
from src.domain.services.image_linker import link_images_to_chunks

_EMBED_BATCH = 100

_STAGE_PARSE_END = 20
_STAGE_CHUNK_END = 40
_STAGE_LINK_END = 50
_STAGE_EMBED_END = 90
_STAGE_UPSERT_END = 100


def _to_extracted_image(parsed_image: ParsedImage) -> ExtractedImage:
    """Maps the parser's DTO (ParsedImage) to the domain entity (ExtractedImage).

    Both carry the same information, but ParsedImage lives at the parser
    port boundary while ExtractedImage is the domain entity consumed by
    domain services like link_images_to_chunks. Keeping the conversion here
    preserves the hexagonal boundary between infrastructure DTOs and domain
    entities.
    """
    return ExtractedImage(
        id=parsed_image.id,
        file_path=parsed_image.file_path,
        page=parsed_image.page,
        bbox=parsed_image.bbox,
        caption=parsed_image.caption,
    )


class IngestDocumentUseCase:
    def __init__(
        self,
        parser: DocumentParserPort,
        chunker: ChunkerPort,
        embedder: EmbeddingPort,
        vector_store: VectorStorePort,
        image_proximity_margin: float,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._vector_store = vector_store
        self._image_proximity_margin = image_proximity_margin

    def execute(
        self,
        file_path: str,
        document_id: str,
        on_progress: Callable[[int], None] | None = None,
    ) -> None:
        def report(pct: int) -> None:
            if on_progress is not None:
                on_progress(max(0, min(100, int(pct))))

        parsed = self._parser.parse(file_path)
        report(_STAGE_PARSE_END)

        chunks = self._chunker.chunk(document_id=document_id, parsed=parsed)
        report(_STAGE_CHUNK_END)

        extracted_images = [_to_extracted_image(img) for img in parsed.images]
        link_images_to_chunks(
            chunks=chunks,
            images=extracted_images,
            margin=self._image_proximity_margin,
        )
        report(_STAGE_LINK_END)

        vectors = self._embed_chunks(chunks, report)

        self._vector_store.ensure_collection()
        self._vector_store.upsert(chunks=chunks, vectors=vectors)
        report(_STAGE_UPSERT_END)

    def _embed_chunks(
        self,
        chunks: list[Chunk],
        report: Callable[[int], None],
    ) -> list[list[float]]:
        if not chunks:
            return []
        embedding_texts = [c.embedding_text for c in chunks]
        total = len(embedding_texts)
        batch_count = ceil(total / _EMBED_BATCH) if total else 0
        start_pct = _STAGE_LINK_END
        end_pct = _STAGE_EMBED_END
        span = end_pct - start_pct
        all_vectors: list[list[float]] = []
        for i in range(batch_count):
            begin = i * _EMBED_BATCH
            end = begin + _EMBED_BATCH
            batch = embedding_texts[begin:end]
            vectors = self._embedder.embed_documents(batch)
            all_vectors.extend(vectors)
            done = min(end, total)
            progress = start_pct + span * (done / total)
            report(int(progress))
        return all_vectors
