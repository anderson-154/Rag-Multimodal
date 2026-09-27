// frontend/lib/api.ts
const DEFAULT_API_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL;
  if (fromEnv) {
    return fromEnv.endsWith("/") ? fromEnv.slice(0, -1) : fromEnv;
  }
  return DEFAULT_API_URL;
}

export type JobStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface UploadResponse {
  job_id: string;
  filename: string;
  status: JobStatus | string;
  document_id: string;
  checksum: string;
  already_existed: boolean;
}

export interface JobResponse {
  job_id: string;
  document_filename: string;
  status: JobStatus;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  document_name: string;
  page: number;
  chunk_id: string;
  image_ids: string[];
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  is_grounded: boolean;
}

export interface QueryOptions {
  top_k?: number;
  document_ids?: string[];
}

interface ErrorPayload {
  detail?: string;
  error_code?: string;
  correlation_id?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly errorCode?: string;
  public readonly correlationId?: string;
  public readonly body: ErrorPayload;

  constructor(
    message: string,
    status: number,
    body: ErrorPayload,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = body.error_code;
    this.correlationId = body.correlation_id;
    this.body = body;
  }
}

async function parseErrorBody(response: Response): Promise<ErrorPayload> {
  try {
    const json = (await response.json()) as ErrorPayload;
    if (json && typeof json === "object") {
      return json;
    }
    return {};
  } catch {
    try {
      const text = await response.text();
      return { detail: text };
    } catch {
      return {};
    }
  }
}

function readableErrorMessage(status: number, body: ErrorPayload, fallback: string): string {
  if (body.detail && typeof body.detail === "string") {
    return body.detail;
  }
  switch (status) {
    case 400:
      return "Solicitud inválida.";
    case 404:
      return "Recurso no encontrado.";
    case 413:
      return "El archivo es demasiado grande.";
    case 415:
      return "Tipo de archivo no soportado.";
    case 503:
      return "El servicio no está disponible en este momento. Inténtelo de nuevo.";
    case 500:
      return "Error interno del servidor.";
    default:
      return fallback;
  }
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const base = getApiBaseUrl();
  const form = new FormData();
  form.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${base}/api/v1/documents`, {
      method: "POST",
      body: form,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Error de red desconocido";
    throw new ApiError(
      `No se pudo conectar con el servidor: ${message}`,
      0,
      { detail: message },
    );
  }

  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      readableErrorMessage(response.status, body, "Error al subir el documento."),
      response.status,
      body,
    );
  }

  return (await response.json()) as UploadResponse;
}

export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const base = getApiBaseUrl();

  let response: Response;
  try {
    response = await fetch(`${base}/api/v1/jobs/${encodeURIComponent(jobId)}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Error de red desconocido";
    throw new ApiError(
      `No se pudo conectar con el servidor: ${message}`,
      0,
      { detail: message },
    );
  }

  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      readableErrorMessage(response.status, body, "Error al obtener el estado del trabajo."),
      response.status,
      body,
    );
  }

  return (await response.json()) as JobResponse;
}

export async function query(
  question: string,
  options: QueryOptions = {},
): Promise<QueryResponse> {
  const base = getApiBaseUrl();
  const payload: Record<string, unknown> = { question };
  if (options.top_k !== undefined) {
    payload.top_k = options.top_k;
  }
  if (options.document_ids !== undefined && options.document_ids.length > 0) {
    payload.document_ids = options.document_ids;
  }

  let response: Response;
  try {
    response = await fetch(`${base}/api/v1/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Error de red desconocido";
    throw new ApiError(
      `No se pudo conectar con el servidor: ${message}`,
      0,
      { detail: message },
    );
  }

  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      readableErrorMessage(response.status, body, "Error al ejecutar la consulta."),
      response.status,
      body,
    );
  }

  return (await response.json()) as QueryResponse;
}

export function getImageUrl(imageId: string): string {
  const base = getApiBaseUrl();
  return `${base}/api/v1/images/${encodeURIComponent(imageId)}`;
}
