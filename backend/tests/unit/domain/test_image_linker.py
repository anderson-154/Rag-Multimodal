# backend/tests/unit/domain/test_image_linker.py
from __future__ import annotations

from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import Chunk, ChunkType
from src.domain.entities.document import ExtractedImage
from src.domain.services.image_linker import link_images_to_chunks


def _chunk(
    chunk_id: str,
    content: str,
    page: int,
    bbox: BoundingBox,
    image_ids: list[str] | None = None,
) -> Chunk:
    return Chunk(
        id=chunk_id,
        content=content,
        hierarchy_path="h",
        document_id="d",
        page=page,
        bbox=bbox,
        chunk_type=ChunkType.TEXT,
        parent_id=None,
        image_ids=list(image_ids or []),
    )


def _img(img_id: str, page: int, bbox: BoundingBox, caption: str | None = None) -> ExtractedImage:
    return ExtractedImage(
        id=img_id, file_path=f"/tmp/{img_id}.png", page=page, bbox=bbox, caption=caption
    )


class TestImageLinkerByProximity:
    def test_links_only_within_margin_and_overlap(self) -> None:
        chunk_a = _chunk(
            "c1",
            "texto chunk a",
            page=1,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        )
        within_margin_overlap = _img(
            "img1",
            page=1,
            bbox=BoundingBox(x0=10, y0=15, x1=90, y1=25),
        )
        outside_margin = _img(
            "img2",
            page=1,
            bbox=BoundingBox(x0=0, y0=200, x1=100, y1=220),
        )
        same_page_no_overlap = _img(
            "img3",
            page=1,
            bbox=BoundingBox(x0=200, y0=15, x1=300, y1=25),
        )
        different_page = _img(
            "img4",
            page=2,
            bbox=BoundingBox(x0=10, y0=15, x1=90, y1=25),
        )

        link_images_to_chunks(
            [chunk_a],
            [within_margin_overlap, outside_margin, same_page_no_overlap, different_page],
            margin=100.0,
        )

        assert set(chunk_a.image_ids) == {"img1"}

    def test_image_above_chunk_not_linked(self) -> None:
        chunk = _chunk(
            "c1",
            "texto",
            page=1,
            bbox=BoundingBox(x0=0, y0=50, x1=100, y1=60),
        )
        above = _img(
            "img-above",
            page=1,
            bbox=BoundingBox(x0=0, y0=10, x1=100, y1=20),
        )
        link_images_to_chunks([chunk], [above], margin=100.0)
        assert chunk.image_ids == []


class TestImageLinkerByCaptionNumber:
    def test_caption_matches_figure_number_in_chunk(self) -> None:
        chunk = _chunk(
            "c1",
            "En la Figura 3 se muestra el diagrama de flujo.",
            page=2,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        )
        # Fuera de margen por proximidad, pero coincide por caption number.
        distant = _img(
            "fig3",
            page=2,
            bbox=BoundingBox(x0=0, y0=500, x1=100, y1=510),
            caption="Figura 3: diagrama de flujo.",
        )
        link_images_to_chunks([chunk], [distant], margin=10.0)
        assert "fig3" in chunk.image_ids

    def test_caption_number_mismatch_not_linked(self) -> None:
        chunk = _chunk(
            "c1",
            "Ver Figura 7.",
            page=1,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        )
        img = _img(
            "fig3",
            page=1,
            bbox=BoundingBox(x0=0, y0=500, x1=100, y1=510),
            caption="Figura 3: otra cosa.",
        )
        link_images_to_chunks([chunk], [img], margin=10.0)
        assert chunk.image_ids == []


class TestImageLinkerCombined:
    def test_proximity_and_caption_both_apply_no_duplicates(self) -> None:
        chunk = _chunk(
            "c1",
            "Conforme a la Tabla 1 se observan resultados.",
            page=1,
            bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        )
        img = _img(
            "t1",
            page=1,
            bbox=BoundingBox(x0=0, y0=15, x1=100, y1=25),
            caption="Tabla 1: resultados.",
        )
        link_images_to_chunks([chunk], [img], margin=100.0)
        assert chunk.image_ids == ["t1"]
