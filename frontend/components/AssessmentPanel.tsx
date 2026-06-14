"use client";

import { useEffect, useState } from "react";
import type {
  GenerateAssessmentResponse,
  McqKey,
  Step,
} from "@/lib/types";
import {
  buildPathComparison,
  expectedOptionAtLayer,
  getLayer1,
  getLayer2,
  getLayer3,
  getMcqFeedback,
  getMcqOptions,
  getReasoningFeedback,
  pathsEqual,
  type RetryLayer,
} from "@/lib/assessmentState";
import { completeNode } from "@/lib/api";
import RevealPanel from "./RevealPanel";

interface AssessmentPanelProps {
  sessionId: string;
  nodeId: string | null;
  assessmentData: GenerateAssessmentResponse | null;
  step: Step;
  error: string | null;
  onComplete: (nodeId: string) => void;
}

export default function AssessmentPanel({
  sessionId,
  nodeId,
  assessmentData,
  step,
  error,
  onComplete,
}: AssessmentPanelProps) {
  const [mcqKey, setMcqKey] = useState<McqKey | null>(null);
  const [l1Id, setL1Id] = useState<string | null>(null);
  const [l2Id, setL2Id] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string[]>([]);
  const [showSourceText, setShowSourceText] = useState(true);
  const [internalStep, setInternalStep] = useState<Step>("idle");
  const [mistakeMessage, setMistakeMessage] = useState<string | null>(null);
  const [retriesUsed, setRetriesUsed] = useState<Set<RetryLayer>>(new Set());

  useEffect(() => {
    if (step === "mcq" && assessmentData) {
      setMcqKey(null);
      setL1Id(null);
      setL2Id(null);
      setSelectedPath([]);
      setShowSourceText(true);
      setMistakeMessage(null);
      setRetriesUsed(new Set());
      setInternalStep("mcq");
    } else if (step === "loading") {
      setInternalStep("loading");
    } else if (step === "error") {
      setInternalStep("error");
    }
  }, [step, assessmentData, nodeId]);

  if (!nodeId) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="h-12 w-12 rounded-full border border-border-gold bg-surface flex items-center justify-center">
          <span className="text-gold-dim text-xl">◈</span>
        </div>
        <p className="text-parchment text-sm max-w-[200px]">
          Select a node to begin the Socratic assessment.
        </p>
      </div>
    );
  }

  if (internalStep === "loading") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6">
        <div className="relative h-10 w-10">
          <div className="absolute inset-0 rounded-full border-2 border-border-gold" />
          <div className="absolute inset-0 rounded-full border-2 border-gold border-t-transparent animate-spin" />
        </div>
        <p className="text-parchment text-sm">Generating assessment…</p>
      </div>
    );
  }

  if (internalStep === "error") {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-red-300 text-sm" role="alert">
          {error ?? "Failed to load assessment."}
        </div>
      </div>
    );
  }

  if (!assessmentData) return null;

  const assessment = assessmentData.socratic_assessment;
  const topperPath = assessment.topper_path;
  const correctMcq = assessment.correct_option as McqKey;

  async function finishAssessment(path: string[], wasCorrect: boolean) {
    await completeNode(sessionId, nodeId!, path, wasCorrect);
    setSelectedPath(path);
    setInternalStep("complete");
    setShowSourceText(true);
    setMistakeMessage(null);
    onComplete(nodeId!);
  }

  function handleWrongAttempt(
    layer: RetryLayer,
    path: string[],
    feedback: string
  ) {
    if (!retriesUsed.has(layer)) {
      setRetriesUsed((prev) => new Set(prev).add(layer));
      setMistakeMessage(`${feedback} Try once more.`);
      return;
    }
    finishAssessment(path, false);
  }

  function handleMcqSelect(key: McqKey) {
    if (key !== correctMcq) {
      handleWrongAttempt("mcq", [key], getMcqFeedback(assessment, key));
      return;
    }
    setMcqKey(key);
    setSelectedPath([key]);
    setMistakeMessage(null);
    setInternalStep("layer_1");
  }

  function handleLayerSelect(
    optionId: string,
    layer: "layer_1" | "layer_2" | "layer_3"
  ) {
    const expected = expectedOptionAtLayer(assessment, layer);
    const path = [...selectedPath, optionId];

    if (optionId !== expected) {
      handleWrongAttempt(layer, path, getReasoningFeedback(assessment, optionId));
      return;
    }

    setMistakeMessage(null);

    if (layer === "layer_1") {
      setL1Id(optionId);
      setSelectedPath(path);
      setInternalStep("layer_2");
    } else if (layer === "layer_2") {
      setL2Id(optionId);
      setSelectedPath(path);
      setInternalStep("layer_3");
    } else {
      finishAssessment(path, pathsEqual(path, topperPath));
    }
  }

  if (internalStep === "complete") {
    const wasCorrect = pathsEqual(selectedPath, topperPath);
    const mcqCorrect = mcqKey === correctMcq;
    const pathSteps = buildPathComparison(assessment, selectedPath);
    return (
      <div className="flex h-full flex-col overflow-y-auto p-6">
        <p className="label-gold mb-1">Complete</p>
        <h2 className="font-display text-lg font-semibold text-cream mb-4">
          {assessmentData.heading}
        </h2>
        <RevealPanel
          wasCorrect={wasCorrect}
          mcqCorrect={mcqCorrect}
          correctOption={assessment.correct_option}
          topperExplanation={assessment.topper_explanation}
          pathSteps={pathSteps}
          fullChunkText={assessmentData.full_chunk_text}
          showSourceText={showSourceText}
          onHideSourceText={() => setShowSourceText(false)}
        />
      </div>
    );
  }

  let question = assessment.question_text;
  let options: { id: string; text: string }[] = getMcqOptions(assessment).map(
    (o) => ({ id: o.key, text: o.text })
  );

  if (internalStep === "layer_1") {
    const l1 = getLayer1(assessment);
    question = l1.question;
    options = l1.options;
  } else if (internalStep === "layer_2" && l1Id) {
    const l2 = getLayer2(assessment, l1Id);
    question = l2.question;
    options = l2.options;
  } else if (internalStep === "layer_3") {
    const l3 = getLayer3(assessment);
    question = l3.question;
    options = l3.options;
  }

  const layerLabel =
    internalStep === "mcq"
      ? "Initial Question"
      : internalStep === "layer_1"
        ? "Layer 1 — Reasoning"
        : internalStep === "layer_2"
          ? "Layer 2 — Deep Dive"
          : internalStep === "layer_3"
            ? "Layer 3 — Mastery"
            : "";

  return (
    <div className="flex h-full flex-col overflow-y-auto p-6">
      <p className="label-gold mb-2">{layerLabel}</p>
      <h2 className="font-display text-lg font-semibold text-cream mb-4 leading-snug">
        {assessmentData.heading}
      </h2>
      {mistakeMessage && (
        <p
          className="mb-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-red-200 text-sm"
          role="alert"
        >
          {mistakeMessage}
        </p>
      )}
      <p className="text-sm text-parchment mb-5 leading-relaxed border-l-2 border-gold/40 pl-3">
        {question}
      </p>
      <div className="space-y-2">
        {options.map((opt, i) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => {
              if (internalStep === "mcq") {
                handleMcqSelect(opt.id as McqKey);
              } else {
                handleLayerSelect(
                  opt.id,
                  internalStep as "layer_1" | "layer_2" | "layer_3"
                );
              }
            }}
            className="option-btn group"
          >
            <span className="text-gold-dim text-xs mr-2 group-hover:text-gold transition-colors">
              {String.fromCharCode(65 + i)}.
            </span>
            {opt.text}
          </button>
        ))}
      </div>
    </div>
  );
}
