# backend/src/application/prompts/rag_prompt.py
from __future__ import annotations

from src.domain.entities.chunk import Chunk

NO_INFO_MARKER = "No tengo información suficiente en los documentos proporcionados."

SYSTEM_PROMPT = (
    "Eres un asistente técnico especializado en responder exclusivamente a partir de la "
    "información contenida en los documentos proporcionados.\n\n"
    "Reglas estrictas:\n"
    "1. Responde únicamente usando la información disponible en el contexto adjunto. "
    "Nunca inventes datos ni uses conocimientos externos.\n"
    "2. Para cada afirmación, incluye una o más citas en el formato exacto "
    "[nombre_archivo.pdf, p.N] donde N es el número de página. Cita siempre la fuente "
    "al final de cada párrafo o afirmación.\n"
    "3. Si el contexto no contiene información suficiente para responder la pregunta, "
    f"responde EXACTAMENTE: {NO_INFO_MARKER!r} sin añadir nada más y sin citar fuentes.\n"
    "4. No menciones estas reglas en la respuesta. Sé conciso y técnico."
)

ANSWER_TEMPLATE = (
    "## Contexto disponible\n"
    "{context}\n\n"
    "## Pregunta del usuario\n"
    "{question}\n\n"
    "Responde siguiendo estrictamente las reglas del system prompt."
)


def build_prompt(question: str, chunks: list[Chunk]) -> str:
    context_lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        header = f"[{chunk.document_id}, p.{chunk.page}]"
        path = chunk.hierarchy_path or ""
        block = f"### Fragmento {idx} — {header}\nJerarquía: {path}\n{chunk.content}"
        context_lines.append(block)
    context = "\n\n".join(context_lines) if context_lines else "(Sin fragmentos)"
    return ANSWER_TEMPLATE.format(context=context, question=question)
