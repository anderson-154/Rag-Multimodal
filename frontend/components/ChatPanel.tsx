// frontend/components/ChatPanel.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { ApiError, query, type QueryResponse } from "@/lib/api";
import {
  ChatMessage,
  type ChatMessageData,
} from "@/components/ChatMessage";

function createId(): string {
  return (
    (typeof crypto !== "undefined" &&
      "randomUUID" in crypto &&
      typeof crypto.randomUUID === "function" &&
      crypto.randomUUID()) ||
    `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
  );
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessageData[]>([
    {
      id: createId(),
      role: "assistant",
      content:
        "Hola. Sube un documento PDF a la izquierda y luego hazme preguntas sobre su contenido.",
      citations: [],
      isGrounded: true,
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [messages, isLoading]);

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || isLoading) {
      return;
    }

    const userMessage: ChatMessageData = {
      id: createId(),
      role: "user",
      content: question,
    };

    const placeholderId = createId();
    const placeholder: ChatMessageData = {
      id: placeholderId,
      role: "assistant",
      content: "",
      citations: [],
      isGrounded: true,
    };

    setMessages((prev) => [...prev, userMessage, placeholder]);
    setInput("");
    setIsLoading(true);

    let response: QueryResponse;
    try {
      response = await query(question);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Error desconocido.";
      const errorMessage: ChatMessageData = {
        id: createId(),
        role: "assistant",
        content: `⚠️ **Error de red**\n\n${message}`,
        citations: [],
        isGrounded: false,
      };
      setMessages((prev) =>
        prev.map((m) => (m.id === placeholderId ? errorMessage : m)),
      );
      setIsLoading(false);
      return;
    }

    const assistantMessage: ChatMessageData = {
      id: createId(),
      role: "assistant",
      content: response.answer,
      citations: response.citations ?? [],
      isGrounded: response.is_grounded,
    };

    setMessages((prev) =>
      prev.map((m) => (m.id === placeholderId ? assistantMessage : m)),
    );
    setIsLoading(false);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void sendMessage();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void sendMessage();
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col bg-white border border-slate-200 rounded-xl overflow-hidden">
      <header className="flex items-center justify-between px-5 py-3 border-b border-slate-200 bg-slate-50">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Chat con documentos</h2>
          <p className="text-xs text-slate-500">
            Pregunta por el contenido de los PDFs indexados.
          </p>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-5 space-y-4 bg-slate-50/60"
      >
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl px-4 py-3 shadow-sm bg-white border border-slate-200">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <div className="flex gap-1">
                  <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.3s]" />
                  <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.15s]" />
                  <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce" />
                </div>
                <span>escribiendo...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} className="border-t border-slate-200 bg-white p-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Escribe tu pregunta... (Enter para enviar, Shift + Enter para salto de línea)"
            disabled={isLoading}
            className="flex-1 resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <path d="m22 2-7 20-4-9-9-4 20-7Z" />
              <path d="M22 2 11 13" />
            </svg>
            Enviar
          </button>
        </div>
      </form>
    </section>
  );
}

export default ChatPanel;
