# backend/src/domain/services/image_linker.py
from __future__ import annotations

import re

from src.domain.entities.chunk import Chunk
from src.domain.entities.document import ExtractedImage

_FIGURE_NUMBER_RE = re.compile(r"(?:figura|fig\.?|diagrama|esquema)\s*[:#]?\s*(\d+)", re.IGNORECASE)


def _extract_figure_numbers(text: str) -> set[str]:
    if not text:
        return set()
    return {match.group(1) for match in _FIGURE_NUMBER_RE.finditer(text)}


def link_images_to_chunks(
    chunks: list[Chunk],
    images: list[ExtractedImage],
    margin: float,
) -> None:
    chunk_associations: dict[str, set[str]] = {chunk.id: set(chunk.image_ids) for chunk in chunks}

    for image in images:
        image_figure_numbers = _extract_figure_numbers(image.caption or "")

        linked_by_proximity: list[Chunk] = []
        for chunk in chunks:
            if chunk.page != image.page:
                continue
            if image.bbox.is_below(chunk.bbox, margin) and image.bbox.overlaps_horizontally(
                chunk.bbox
            ):
                linked_by_proximity.append(chunk)
                chunk_associations[chunk.id].add(image.id)

        if image_figure_numbers:
            for chunk in chunks:
                chunk_numbers = _extract_figure_numbers(chunk.content)
                if image_figure_numbers & chunk_numbers:
                    chunk_associations[chunk.id].add(image.id)

        if (not linked_by_proximity) and image.caption:
            caption_text = image.caption
            for chunk in chunks:
                if chunk.page != image.page:
                    continue
                if caption_text in chunk.content or chunk.content in caption_text:
                    chunk_associations[chunk.id].add(image.id)

    for chunk in chunks:
        associated = list(chunk_associations.get(chunk.id, set()))
        existing = list(chunk.image_ids)
        combined = existing + [iid for iid in associated if iid not in existing]
        chunk.image_ids.clear()
        chunk.image_ids.extend(combined)
