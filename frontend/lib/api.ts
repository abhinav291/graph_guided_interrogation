import type {
  GenerateAssessmentResponse,
  TreeResponse,
  UploadResponse,
} from "./types";

// Empty string = same-origin; Next.js rewrites /api/* → backend (see next.config.js).
// Set NEXT_PUBLIC_API_BASE only when frontend and backend are on different hosts.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    let detail = res.statusText;
    try {
      const body = JSON.parse(text) as { detail?: string };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      if (text && !text.startsWith("<!DOCTYPE")) detail = text.slice(0, 300);
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (err) {
    if (err instanceof TypeError) {
      const hint = API_BASE
        ? `Check that the backend is up at ${API_BASE} and CORS allows this site.`
        : "Ensure uvicorn is running: cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000";
      throw new Error(`Cannot reach the backend. ${hint}`);
    }
    throw err;
  }
}

export type LlmProvider = "groq" | "anthropic";

export async function uploadPdf(
  file: File,
  llmProvider: LlmProvider = "groq"
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("llm_provider", llmProvider);
  const res = await apiFetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });
  return handleResponse<UploadResponse>(res);
}

export async function fetchTree(sessionId: string): Promise<TreeResponse> {
  const res = await apiFetch(`${API_BASE}/api/session/${sessionId}/tree`);
  return handleResponse<TreeResponse>(res);
}

export async function generateAssessment(
  sessionId: string,
  nodeId: string
): Promise<GenerateAssessmentResponse> {
  const res = await apiFetch(
    `${API_BASE}/api/session/${sessionId}/node/${nodeId}/generate`,
    { method: "POST" }
  );
  return handleResponse<GenerateAssessmentResponse>(res);
}

export async function completeNode(
  sessionId: string,
  nodeId: string,
  selectedPath: string[],
  wasCorrect: boolean
): Promise<void> {
  const res = await apiFetch(
    `${API_BASE}/api/session/${sessionId}/node/${nodeId}/complete`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_path: selectedPath, was_correct: wasCorrect }),
    }
  );
  await handleResponse(res);
}

export async function logFallback(
  sessionId: string,
  nodeId: string,
  layer: number,
  selectedPathPrefix: string[],
  customText: string
): Promise<void> {
  const res = await apiFetch(
    `${API_BASE}/api/session/${sessionId}/node/${nodeId}/fallback-log`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        layer,
        selected_path_prefix: selectedPathPrefix,
        custom_text: customText,
      }),
    }
  );
  await handleResponse(res);
}
