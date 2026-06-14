"use client";

import type { PathStepSummary } from "@/lib/assessmentState";

interface RevealPanelProps {
  wasCorrect: boolean;
  mcqCorrect: boolean;
  correctOption: string;
  topperExplanation: string;
  pathSteps: PathStepSummary[];
  fullChunkText: string;
  showSourceText: boolean;
  onHideSourceText: () => void;
}

export default function RevealPanel({
  wasCorrect,
  mcqCorrect,
  correctOption,
  topperExplanation,
  pathSteps,
  fullChunkText,
  showSourceText,
  onHideSourceText,
}: RevealPanelProps) {
  let resultMessage: string;
  if (wasCorrect) {
    resultMessage = "Correct — your answer and reasoning match the topper path.";
  } else if (mcqCorrect) {
    resultMessage =
      "Your initial answer was right, but your reasoning was incorrect after two attempts. Review below.";
  } else {
    resultMessage = `Incorrect — the correct answer was ${correctOption}. Review below.`;
  }

  return (
    <div className="space-y-4 border-t border-border-gold pt-4">
      <div
        className={`rounded-lg px-4 py-3 text-sm border ${
          wasCorrect
            ? "bg-gold/10 text-gold-light border-gold/40"
            : "bg-red-950/30 text-red-300 border-red-900/40"
        }`}
      >
        {wasCorrect ? "✦ " : "✗ "}
        {resultMessage}
      </div>

      {pathSteps.length > 0 && (
        <div className="rounded-lg border border-border-gold bg-surface px-4 py-3 text-sm">
          <p className="label-gold mb-3">Your path vs correct path</p>
          <div className="space-y-3">
            {pathSteps.map((step) => (
              <div
                key={step.layer}
                className="rounded-md border border-border-gold/60 bg-elevated/50 px-3 py-2"
              >
                <p className="text-gold-dim text-xs mb-2">{step.layer}</p>
                {step.question && (
                  <p className="text-parchment text-sm mb-3 leading-relaxed border-l-2 border-gold/30 pl-2">
                    {step.question}
                  </p>
                )}
                <div className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-parchment/60 mb-0.5">
                      You selected
                    </p>
                    <p
                      className={`text-sm leading-snug ${
                        step.isCorrect ? "text-gold-light" : "text-red-300"
                      }`}
                    >
                      {step.isCorrect ? "✓ " : "✗ "}
                      {step.selected}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-parchment/60 mb-0.5">
                      Correct answer
                    </p>
                    <p className="text-sm leading-snug text-gold-light">
                      {step.correct}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {topperExplanation && (
        <div className="rounded-lg border border-border-gold bg-surface px-4 py-3 text-sm">
          <p className="label-gold mb-2">Topper explanation</p>
          <p className="text-parchment leading-relaxed">{topperExplanation}</p>
        </div>
      )}

      {showSourceText && (
        <div className="rounded-lg border border-gold/30 bg-elevated p-4 shadow-gold">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="label-gold">Source Text</h3>
            <button
              type="button"
              onClick={onHideSourceText}
              className="rounded-md border border-border-gold bg-surface px-3 py-1 text-xs font-medium text-parchment transition-colors hover:border-gold hover:text-gold-light"
            >
              Hide Document Text
            </button>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-cream/80 border-l-2 border-gold/30 pl-3">
            {fullChunkText}
          </p>
        </div>
      )}
    </div>
  );
}
