// frontend/components/UploadPanel.tsx
"use client";

import { useCallback, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import {
  ApiError,
  getJobStatus,
  uploadDocument,
  type JobStatus,
} from "@/lib/api";

type JobState = {
  jobId: string;
  filename: string;
  status: JobStatus | string;
  progress: number;
  error: string | null;
};

const POLL_INTERVAL_MS = 2000;
const ALLOWED_EXT = ".pdf";
const ALLOWED_MIME = "application/pdf";

function statusLabel(status: JobStatus | string): string {
  switch (status) {
    case "PENDING":
      return "En cola";
    case "PROCESSING":
      return "Procesando";
    case "COMPLETED":
      return "Completado";
    case "FAILED":
      return "Fallido";
    default:
      return status;
  }
}

function isTerminal(status: JobStatus | string): boolean {
  return status === "COMPLETED" || status === "FAILED";
}

export function UploadPanel() {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobState | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);
  const pollActiveRef = useRef<boolean>(false);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    pollActiveRef.current = false;
  }, []);

  const pollJob = useCallback(async (jobId: string) => {
    if (!pollActiveRef.current) {
      return;
    }
    try {
      const latest = await getJobStatus(jobId);
      setJob((prev) =>
        prev
          ? {
              ...prev,
              status: latest.status,
              progress: latest.progress ?? prev.progress,
              error: latest.error ?? prev.error,
            }
          : prev,
      );
      if (isTerminal(latest.status)) {
        stopPolling();
        if (latest.status === "COMPLETED") {
          setError(null);
        } else if (latest.error) {
          setError(latest.error);
        }
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Error al consultar el estado del trabajo.";
      setError(message);
      stopPolling();
    }
  }, [stopPolling]);

  const startPolling = useCallback((jobId: string) => {
    stopPolling();
    pollActiveRef.current = true;
    pollRef.current = window.setInterval(() => {
      void pollJob(jobId);
    }, POLL_INTERVAL_MS);
    void pollJob(jobId);
  }, [pollJob, stopPolling]);

  const handleFile = useCallback(async (file: File | null | undefined) => {
    if (!file) {
      return;
    }
    if (isUploading) {
      return;
    }

    setError(null);
    setJob(null);

    const nameLower = file.name.toLowerCase();
    const isPdf = nameLower.endsWith(ALLOWED_EXT) || file.type === ALLOWED_MIME;
    if (!isPdf) {
      setError("Solo se permiten archivos PDF.");
      return;
    }

    setIsUploading(true);
    try {
      const uploadRes = await uploadDocument(file);
      const newJob: JobState = {
        jobId: uploadRes.job_id,
        filename: uploadRes.filename || file.name,
        status: uploadRes.status,
        progress: uploadRes.already_existed ? 100 : 0,
        error: null,
      };
      setJob(newJob);
      if (!isTerminal(newJob.status)) {
        startPolling(newJob.jobId);
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Error desconocido al subir el documento.";
      setError(message);
    } finally {
      setIsUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }, [isUploading, startPolling]);

  const onInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      void handleFile(file);
    },
    [handleFile],
  );

  const onSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const file = inputRef.current?.files?.[0];
      void handleFile(file);
    },
    [handleFile],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      if (isUploading) {
        return;
      }
      const file = event.dataTransfer.files?.[0];
      void handleFile(file);
    },
    [handleFile, isUploading],
  );

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const onDragEnter = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  }, []);

  const borderStyle = isDragging
    ? "border-blue-500 bg-blue-50"
    : "border-slate-300 hover:border-slate-400 bg-white";

  return (
    <div className="flex flex-col gap-4 h-full">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Subir documento</h2>
        <p className="text-sm text-slate-500 mt-1">
          Sube un PDF para indexarlo en el sistema RAG.
        </p>
      </div>

      <form onSubmit={onSubmit}>
        <div
          role="button"
          tabIndex={0}
          aria-disabled={isUploading}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !isUploading) {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          className={`relative flex flex-col items-center justify-center text-center rounded-xl border-2 border-dashed p-6 transition-colors cursor-pointer ${borderStyle} ${
            isUploading ? "opacity-70 cursor-not-allowed" : ""
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`h-10 w-10 ${isDragging ? "text-blue-600" : "text-slate-400"}`}
          >
            <path d="M12 16.5V7.5" />
            <path d="m6 10.5 6-6 6 6" />
            <path d="M4.5 18h15a1.5 1.5 0 0 0 0-3h-15a1.5 1.5 0 0 0 0 3Z" />
          </svg>
          <p className="mt-3 text-sm font-medium text-slate-800">
            {isUploading ? "Subiendo..." : "Arrastra un PDF aquí"}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            o haz clic para seleccionar un archivo (.pdf)
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={ALLOWED_MIME}
            className="hidden"
            disabled={isUploading}
            onChange={onInputChange}
          />
        </div>
      </form>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </div>
      )}

      {job && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900 truncate">{job.filename}</p>
              <p className="text-xs text-slate-500 mt-0.5">Trabajo: {job.jobId}</p>
            </div>
            <span
              className={
                "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium " +
                (job.status === "COMPLETED"
                  ? "bg-emerald-100 text-emerald-800"
                  : job.status === "FAILED"
                    ? "bg-red-100 text-red-800"
                    : job.status === "PROCESSING"
                      ? "bg-blue-100 text-blue-800"
                      : "bg-slate-200 text-slate-800")
              }
            >
              {statusLabel(job.status)}
            </span>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
              <span>Progreso</span>
              <span>{Math.min(100, Math.max(0, job.progress))}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className={
                  "h-full transition-all duration-300 " +
                  (job.status === "FAILED"
                    ? "bg-red-500"
                    : job.status === "COMPLETED"
                      ? "bg-emerald-500"
                      : "bg-blue-600")
                }
                style={{ width: `${Math.min(100, Math.max(0, job.progress))}%` }}
              />
            </div>
          </div>

          {job.status === "FAILED" && job.error && (
            <p className="text-xs text-red-700">{job.error}</p>
          )}
          {job.status === "COMPLETED" && !job.error && (
            <p className="text-xs text-emerald-700">Documento indexado correctamente.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default UploadPanel;
