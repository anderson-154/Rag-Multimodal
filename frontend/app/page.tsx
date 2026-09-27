// frontend/app/page.tsx
import { UploadPanel } from "@/components/UploadPanel";
import { ChatPanel } from "@/components/ChatPanel";

export default function HomePage() {
  return (
    <main className="h-screen w-screen overflow-hidden">
      <div className="h-full w-full flex flex-col lg:flex-row gap-4 p-4">
        <aside className="w-full lg:w-80 shrink-0 h-auto lg:h-full overflow-y-auto bg-white border border-slate-200 rounded-xl p-4">
          <UploadPanel />
        </aside>
        <section className="flex-1 min-h-0 min-w-0">
          <ChatPanel />
        </section>
      </div>
    </main>
  );
}
