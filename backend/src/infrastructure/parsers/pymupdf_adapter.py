# backend/src/infrastructure/parsers/pymupdf_adapter.py
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from src.domain.entities.bounding_box import BoundingBox
from src.domain.exceptions import ParsingError
from src.domain.ports.document_parser_port import (
    DocumentParserPort,
    ParsedBlock,
    ParsedDocument,
    ParsedImage,
)

logger = logging.getLogger(__name__)

_CAPTION_PREFIXES = ("figura", "fig.", "diagrama", "tabla", "esquema")
_MIN_IMAGE_WIDTH_PX = 100
_MIN_IMAGE_HEIGHT_PX = 100


class PyMuPDFParserAdapter(DocumentParserPort):
    def __init__(self, storage_path: str, image_proximity_margin: float = 100.0) -> None:
        try:
            import fitz  # noqa: F401
        except ImportError as exc:
            raise ParsingError(
                "PyMuPDF (fitz) is not installed. Install pymupdf to use PyMuPDFParserAdapter."
            ) from exc
        self._storage_path = Path(storage_path)
        self._images_dir = self._storage_path / "images"
        self._image_proximity_margin = image_proximity_margin

    def parse(self, file_path: str) -> ParsedDocument:
        import fitz

        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise ParsingError(f"File not found: {file_path}")

        self._images_dir.mkdir(parents=True, exist_ok=True)

        document_id = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]

        try:
            doc = fitz.open(str(path))
        except Exception as exc:  # noqa: BLE001
            raise ParsingError(f"Failed to open PDF {file_path}: {exc!s}") from exc

        blocks: list[ParsedBlock] = []
        tables: list[ParsedBlock] = []
        images: list[ParsedImage] = []
        try:
            total_pages = doc.page_count
            for page_index in range(total_pages):
                page = doc.load_page(page_index)
                page_number = page_index + 1
                page_blocks = self._extract_text_blocks(page, page_number)
                blocks.extend(page_blocks)

                page_images = self._extract_page_images(
                    page,
                    page_number,
                    document_id,
                    page_blocks,
                )
                images.extend(page_images)

                page_tables = self._extract_tables(page, page_number)
                tables.extend(page_tables)
        finally:
            try:
                doc.close()
            except Exception:  # pragma: no cover
                pass

        return ParsedDocument(
            filename=path.name,
            total_pages=total_pages,
            blocks=blocks,
            tables=tables,
            images=images,
        )

    def _extract_text_blocks(self, page: Any, page_number: int) -> list[ParsedBlock]:
        blocks: list[ParsedBlock] = []
        try:
            raw = page.get_text("dict")
        except Exception as exc:  # noqa: BLE001
            raise ParsingError(f"Failed to extract text for page {page_number}: {exc!s}") from exc

        for raw_block in raw.get("blocks", []) or []:
            if raw_block.get("type") != 0:
                continue
            lines = raw_block.get("lines") or []
            if not lines:
                continue
            block_bbox = raw_block.get("bbox")
            if not isinstance(block_bbox, (list, tuple)) or len(block_bbox) != 4:
                continue
            x0, y0, x1, y1 = (float(v) for v in block_bbox)
            text_parts: list[str] = []
            max_font_size = 0.0
            for line in lines:
                for span in line.get("spans") or []:
                    span_text = span.get("text") or ""
                    if span_text:
                        text_parts.append(span_text)
                    font_size = float(span.get("size") or 0.0)
                    if font_size > max_font_size:
                        max_font_size = font_size
            text = " ".join(part.strip() for part in text_parts).strip()
            if not text:
                continue
            bbox = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
            blocks.append(
                ParsedBlock(
                    text=text,
                    page=page_number,
                    bbox=bbox,
                    block_type="text",
                    font_size=max_font_size,
                    hierarchy_level=0,
                )
            )
        return blocks

    def _extract_page_images(
        self,
        page: Any,
        page_number: int,
        document_id: str,
        page_blocks: list[ParsedBlock],
    ) -> list[ParsedImage]:
        import fitz

        out: list[ParsedImage] = []
        doc = page.parent
        page_images = page.get_images(full=True) or []
        for idx, img in enumerate(page_images):
            if len(img) < 7:
                continue
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:  # Convert CMYK or alpha variants to RGB
                    converted = fitz.Pixmap(fitz.csRGB, pix)
                    pix = converted
            except Exception:  # noqa: BLE001
                continue

            if pix.width < _MIN_IMAGE_WIDTH_PX or pix.height < _MIN_IMAGE_HEIGHT_PX:
                pix = None
                continue

            try:
                rects = page.get_image_rects(xref)
            except Exception:  # noqa: BLE001
                rects = []
            if not rects:
                continue
            rect = rects[0]
            bbox = BoundingBox(
                x0=float(rect.x0),
                y0=float(rect.y0),
                x1=float(rect.x1),
                y1=float(rect.y1),
            )

            image_id = f"{document_id}_p{page_number}_{idx}"
            image_filename = f"{image_id}.png"
            save_path = self._images_dir / image_filename
            try:
                pix.save(str(save_path))
            except Exception as exc:  # noqa: BLE001
                raise ParsingError(f"Failed to save image {image_filename}: {exc!s}") from exc

            caption = self._find_caption(bbox, page_blocks)
            out.append(
                ParsedImage(
                    id=image_id,
                    page=page_number,
                    bbox=bbox,
                    file_path=str(save_path),
                    caption=caption,
                )
            )
            pix = None
        return out

    def _find_caption(
        self,
        image_bbox: BoundingBox,
        page_blocks: list[ParsedBlock],
    ) -> str | None:
        candidates: list[tuple[float, ParsedBlock]] = []
        for block in page_blocks:
            if not block.bbox.is_below(image_bbox, self._image_proximity_margin):
                continue
            if not block.bbox.overlaps_horizontally(image_bbox):
                continue
            stripped = block.text.strip()
            if not stripped:
                continue
            lowered = stripped.lower()
            if not lowered.startswith(_CAPTION_PREFIXES):
                continue
            distance = block.bbox.vertical_distance_to(image_bbox)
            candidates.append((distance, block))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1].text.strip()

    def _extract_tables(self, page: Any, page_number: int) -> list[ParsedBlock]:
        try:
            tables = page.find_tables()
        except Exception:  # noqa: BLE001
            return []

        out: list[ParsedBlock] = []
        items = getattr(tables, "tables", None) or tables or []
        for table in items:
            try:
                md = table.to_markdown() or ""
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(md, str) or not md.strip():
                continue
            bbox_obj = getattr(table, "bbox", None)
            if isinstance(bbox_obj, (list, tuple)) and len(bbox_obj) == 4:
                x0, y0, x1, y1 = (float(v) for v in bbox_obj)
                page_rect = page.rect
                if hasattr(page_rect, "x0"):
                    x0 = max(float(page_rect.x0), x0)
                    y0 = max(float(page_rect.y0), y0)
                    x1 = min(float(page_rect.x1), x1)
                    y1 = min(float(page_rect.y1), y1)
            else:
                rect = getattr(page, "rect", None)
                if rect is not None and hasattr(rect, "x0"):
                    x0 = float(rect.x0)
                    y0 = float(rect.y0)
                    x1 = float(rect.x1)
                    y1 = float(rect.y1)
                else:
                    x0 = y0 = 0.0
                    x1 = y1 = 1.0
            bbox = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
            out.append(
                ParsedBlock(
                    text=md,
                    page=page_number,
                    bbox=bbox,
                    block_type="table",
                    font_size=0.0,
                    hierarchy_level=0,
                )
            )
        return out
