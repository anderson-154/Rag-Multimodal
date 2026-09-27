// frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Multimodal",
  description: "Interfaz para el sistema RAG multimodal de PDFs.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="font-sans">{children}</body>
    </html>
  );
}
