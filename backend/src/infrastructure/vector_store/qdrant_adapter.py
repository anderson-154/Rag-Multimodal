from __future__ import annotations

import logging
from math import ceil
from typing import TYPE_CHECKING, Any

from src.domain.entities.bounding_box import BoundingBox
from src.domain.entities.chunk import Chunk, ChunkType
from src.domain.exceptions import VectorStoreError
from src.domain.ports.vector_store_port import SearchResult, VectorStorePort

if TYPE_CHECKING:
    from qdrant_client.http.models import PointStruct

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


class QdrantVectorStoreAdapter(VectorStorePort):
    def __init__(self, url: str, collection_name: str, dimensions: int) -> None:
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise VectorStoreError(
                "qdrant-client is not installed. Install it to use QdrantVectorStoreAdapter."
            ) from exc

        self._url = url
        self._collection_name = collection_name
        self._dimensions = dimensions
        self._models = models
        try:
            self._client = QdrantClient(url=url)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to connect to Qdrant at {url}: {exc!s}") from exc

    def ensure_collection(self) -> None:
        models = self._models
        distance = models.Distance
        vector_params = models.VectorParams
        try:
            exists = self._client.collection_exists(collection_name=self._collection_name)
            if exists:
                return
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=vector_params(
                    size=self._dimensions,
                    distance=distance.COSINE,
                ),
            )
            logger.info(
                "qdrant_collection_created",
                extra={
                    "extra_data": {
                        "collection": self._collection_name,
                        "dimensions": self._dimensions,
                    }
                },
            )
        except VectorStoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(
                f"Failed to ensure Qdrant collection {self._collection_name!r}: {exc!s}"
            ) from exc

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise VectorStoreError("chunks and vectors length mismatch")
        if not chunks:
            return

        try:
            total_batches = ceil(len(chunks) / _BATCH_SIZE)
            for batch_idx in range(total_batches):
                start = batch_idx * _BATCH_SIZE
                end = start + _BATCH_SIZE
                batch_chunks = chunks[start:end]
                batch_vectors = vectors[start:end]
                points: list[PointStruct] = [
                    self._to_point(chunk, vector)
                    for chunk, vector in zip(batch_chunks, batch_vectors, strict=True)
                ]
                self._client.upsert(
                    collection_name=self._collection_name,
                    points=points,
                )
            logger.info(
                "qdrant_upsert_done",
                extra={
                    "extra_data": {
                        "collection": self._collection_name,
                        "chunks": len(chunks),
                        "batches": total_batches,
                    }
                },
            )
        except VectorStoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant upsert failed: {exc!s}") from exc

    def search_semantic(
        self,
        query_vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        models = self._models
        try:
            query_filter = None
            if document_ids:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchAny(any=document_ids),
                        )
                    ]
                )
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False,
            )
            search_results: list[SearchResult] = []
            for point in response.points:
                chunk = self._to_chunk(point.payload or {})
                if chunk is None:
                    continue
                search_results.append(
                    SearchResult(chunk=chunk, score=point.score, source="semantic")
                )
            return search_results
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant semantic search failed: {exc!s}") from exc

    def search_keyword(
        self,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        models = self._models
        if not query:
            return []
        try:
            must_conditions: list[object] = [
                models.FieldCondition(
                    key="content",
                    match=models.MatchText(text=query),
                )
            ]
            if document_ids:
                must_conditions.append(
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchAny(any=document_ids),
                    )
                )
            query_filter = models.Filter(must=must_conditions)
            # Use scroll with payload to get matches, then rank by a dummy 1.0 score
            records, _next_page = self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=query_filter,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
            hits: list[SearchResult] = []
            for record in records:
                if len(hits) >= top_k:
                    break
                chunk = self._to_chunk(record.payload or {})
                if chunk is not None and chunk.content and chunk.id:
                    hits.append(SearchResult(chunk=chunk, score=1.0, source="keyword"))
            return hits
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant keyword search failed: {exc!s}") from exc

    def delete_by_document(self, document_id: str) -> int:
        models = self._models
        try:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
            result = self._client.delete(
                collection_name=self._collection_name,
                points_selector=models.FilterSelector(filter=query_filter),
            )
            operation_id = getattr(result, "operation_id", None)
            status = getattr(result, "status", None)
            logger.info(
                "qdrant_delete_by_document",
                extra={
                    "extra_data": {
                        "collection": self._collection_name,
                        "document_id": document_id,
                        "operation_id": operation_id,
                        "status": str(status),
                    }
                },
            )
            # Qdrant delete API does not return a count; approximate via points-deleted is not exposed
            return 0
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant delete_by_document failed: {exc!s}") from exc

    def list_documents(self) -> list[str]:
        try:
            seen: set[str] = set()
            offset: Any = None
            while True:
                records, next_page_offset = self._client.scroll(
                    collection_name=self._collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=["document_id"],
                    with_vectors=False,
                )
                for record in records:
                    payload = record.payload or {}
                    doc_id = payload.get("document_id") if payload else None
                    if isinstance(doc_id, str):
                        seen.add(doc_id)
                if not next_page_offset:
                    break
                offset = next_page_offset
            return sorted(seen)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant list_documents failed: {exc!s}") from exc

    def _to_point(self, chunk: Chunk, vector: list[float]) -> PointStruct:
        models = self._models
        payload: dict[str, object] = {
            "id": chunk.id,
            "content": chunk.content,
            "hierarchy_path": chunk.hierarchy_path,
            "document_id": chunk.document_id,
            "page": chunk.page,
            "chunk_type": chunk.chunk_type.value,
            "parent_id": chunk.parent_id,
            "image_ids": list(chunk.image_ids),
            "bbox": {
                "x0": chunk.bbox.x0,
                "y0": chunk.bbox.y0,
                "x1": chunk.bbox.x1,
                "y1": chunk.bbox.y1,
            },
        }
        point: PointStruct = models.PointStruct(id=chunk.id, vector=vector, payload=payload)
        return point

    def _to_chunk(self, payload: dict[str, object]) -> Chunk | None:
        try:
            raw_bbox = payload.get("bbox") or None
            bbox = None
            if isinstance(raw_bbox, dict):
                bbox = BoundingBox(
                    x0=float(raw_bbox["x0"]),
                    y0=float(raw_bbox["y0"]),
                    x1=float(raw_bbox["x1"]),
                    y1=float(raw_bbox["y1"]),
                )
            else:
                return None

            raw_chunk_type = payload.get("chunk_type")
            chunk_type = None
            if isinstance(raw_chunk_type, str):
                try:
                    chunk_type = ChunkType(raw_chunk_type)
                except ValueError:
                    return None
            else:
                return None

            raw_image_ids = payload.get("image_ids") or []
            if not isinstance(raw_image_ids, list):
                raw_image_ids = []
            image_ids = [str(x) for x in raw_image_ids]

            raw_parent_id = payload.get("parent_id")
            parent_id: str | None = str(raw_parent_id) if isinstance(raw_parent_id, str) else None

            return Chunk(
                id=str(payload.get("id", "")),
                content=str(payload.get("content", "")),
                hierarchy_path=str(payload.get("hierarchy_path", "")),
                document_id=str(payload.get("document_id", "")),
                page=int(str(payload.get("page", 0))),
                bbox=bbox,
                chunk_type=chunk_type,
                parent_id=parent_id,
                image_ids=image_ids,
            )
        except (KeyError, TypeError, ValueError):
            return None
