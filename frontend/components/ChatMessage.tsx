// frontend/components/ChatMessage.tsx
"use client";

import { useState } from "react";
import type { MouseEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getImageUrl, type Citation } from "@/lib/api";

export type ChatRole = "user" | "assistant";

export interface ChatMessageData {
  id: string;
  role: ChatRole;
  content: string;
  citations?: Citation[];
  isGrounded?: boolean;
}

function citationKey(citation: Citation): string {
  return `${citation.document_name}|${citation.page}|${citation.chunk_id}`;
}

function mergeImages(
  citations: Citation[],
): Array<{ citation: Citation; images: string[]; key: string }> {
  const map = new Map<string, { citation: Citation; images: string[] }>();
  for (const c of citations) {
    const key = citationKey(c);
    const existing = map.get(key);
    if (existing) {
      const imageSet = new Set(existing.images);
      for (const id of c.image_ids) {
        imageSet.add(id);
      }
      existing.images = Array.from(imageSet);
    } else {
      map.set(key, {
        citation: c,
        images: Array.from(new Set(c.image_ids)),
      });
    }
  }
  return Array.from(map.entries()).map(([key, value]) => ({
    key,
    ...value,
  }));
}

function ImageModal({
  src,
  alt,
  onClose,
}: {
  src: string;
  alt: string;
  onClose: () => void;
}) {
  const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Imagen ampliada"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={handleBackdropClick}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          onClose();
        }
      }}
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 text-white hover:text-slate-200 focus:outline-none"
        aria-label="Cerrar imagen ampliada"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-8 w-8"
        >
          <path d="M18 6 6 18" />
          <path d="m6 6 12 12" />
        </svg>
      </button>
      <img
        src={src}
        alt={alt}
        onClick={onClose}
        className="max-h-full max-w-full rounded-lg object-contain shadow-xl"
      />
    </div>
  );
}

export function ChatMessage({ message }: { message: ChatMessageData }) {
  const { role, content, citations = [], isGrounded } = message;
  const [modalImage, setModalImage] = useState<{ src: string; alt: string } | null>(null);
  const uniqueCitations = role === "assistant" ? mergeImages(citations) : [];

  const isAssistant = role === "assistant";
  const containerClasses = isAssistant
    ? "bg-white border border-slate-200"
    : "bg-blue-600 text-white";

  return (
    <div className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${containerClasses}`}
      >
        <div className="flex items-center justify-between gap-3 mb-2">
          <p className={`text-xs font-semibold ${isAssistant ? "text-slate-500" : "text-blue-100"}`}>
            {isAssistant ? "Asistente" : "Tú"}
          </p>
          {isAssistant && isGrounded === false && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-xs font-medium">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-3.5 w-3.5"
              >
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                <path d="M12 9v4" />
                <path d="M12 17h.01" />
              </svg>
              Respuesta no fundamentada en los documentos
            </span>
          )}
        </div>

        <div
          className={
            "prose prose-sm max-w-none break-words " +
            (isAssistant
              ? "text-slate-800 prose-a:text-blue-600 prose-code:text-slate-900 prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded"
              : "text-white prose-invert prose-a:text-blue-200")
          }
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>

        {isAssistant && uniqueCitations.length > 0 && (
          <div className="mt-4 border-t border-slate-200 pt-4 flex flex-col gap-3">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
              Fuentes
            </p>
            {uniqueCitations.map(({ key, citation, images }) => (
              <div
                key={key}
                className="rounded-lg border border-slate-200 bg-slate-50 p-3"
              >
                <p className="text-sm text-slate-800">
                  <span className="font-medium">Fuente:</span> {citation.document_name},{" "}
                  <span className="font-medium">Página {citation.page}</span>
                </p>
                {citation.chunk_id && (
                  <p className="text-xs text-slate-500 mt-0.5 truncate">
                    Fragmento: {citation.chunk_id}
                  </p>
                )}
                {images.length > 0 && (
                  <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {images.map((imageId) => {
                      const url = getImageUrl(imageId);
                      return (
                        <button
                          key={imageId}
                          type="button"
                          onClick={() => setModalImage({ src: url, alt: imageId })}
                          className="group relative block overflow-hidden rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                          aria-label={`Abrir imagen ${imageId}`}
                        >
                          <img
                            src={url}
                            alt={imageId}
                            loading="lazy"
                            className="h-28 w-full object-cover transition-transform group-hover:scale-105"
                          />
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {modalImage && (
        <ImageModal
          src={modalImage.src}
          alt={modalImage.alt}
          onClose={() => setModalImage(null)}
        />
      )}
    </div>
  );
}

export default ChatMessage;
