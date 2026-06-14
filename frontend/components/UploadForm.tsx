"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadPdf, type LlmProvider } from "@/lib/api";

function toggleButtonClass(active: boolean) {
  return `rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
    active
      ? "border-gold/60 bg-gold/20 text-gold-light"
      : "border-gold/30 bg-transparent text-gold-dim hover:border-gold/50 hover:text-gold-light"
  }`;
}

export default function UploadForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [llmProvider, setLlmProvider] = useState<LlmProvider>("groq");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadPdf(file, llmProvider);
      router.push(`/session/${result.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex flex-1 items-center justify-center p-6 bg-dark-radial">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 h-64 w-96 rounded-full bg-gold/5 blur-3xl" />
        <div className="absolute bottom-0 left-0 h-px w-full bg-gradient-to-r from-transparent via-gold/30 to-transparent" />
      </div>

      <div className="card-gold relative w-full max-w-lg p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-gold/40 bg-gold/10">
            <span className="text-gold-light text-lg">◈</span>
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold text-cream">
              Socratic Graph
            </h1>
            <p className="text-gold-dim text-xs tracking-wide">Learning Platform</p>
          </div>
        </div>

        <p className="text-parchment mb-4 text-sm leading-relaxed">
          Upload a PDF to generate an interactive topic tree with multi-layer
          Socratic assessments.
        </p>

        <p className="mb-6 rounded-lg border border-gold/30 bg-gold/5 px-3 py-2 text-xs text-gold-dim">
          POC preview — processes the first <strong className="text-gold-light">10 chunks</strong> only (~10k characters).
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="label-gold mb-2 block">Document</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-parchment
                file:mr-4 file:rounded-lg file:border file:border-gold/40
                file:bg-gold/10 file:px-4 file:py-2 file:text-gold-light
                file:font-medium file:transition-colors
                hover:file:bg-gold/20 hover:file:border-gold/60"
            />
          </label>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              title="Use Groq (llama-3.3-70b)"
              aria-pressed={llmProvider === "groq"}
              onClick={() => setLlmProvider("groq")}
              disabled={loading}
              className={toggleButtonClass(llmProvider === "groq")}
            >
              Groq
            </button>
            <button
              type="button"
              title="Use Anthropic (Claude Haiku 4.5) when Groq rate limits hit"
              aria-pressed={llmProvider === "anthropic"}
              onClick={() => setLlmProvider("anthropic")}
              disabled={loading}
              className={toggleButtonClass(llmProvider === "anthropic")}
            >
              Anthropic
            </button>
          </div>

          <button
            type="submit"
            disabled={!file || loading}
            className="btn-gold w-full"
          >
            {loading
              ? `Processing (${llmProvider}, 10 chunks)…`
              : "Upload & Build Tree"}
          </button>

          {error && (
            <p className="rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-red-300 text-sm" role="alert">
              {error}
            </p>
          )}
        </form>
      </div>
    </main>
  );
}
