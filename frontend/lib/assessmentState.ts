import type { McqBranch, McqKey, SocraticAssessment, SocraticOption } from "./types";

export type RetryLayer = "mcq" | "layer_1" | "layer_2" | "layer_3";

export function isFallbackOption(optionId: string): boolean {
  return optionId.startsWith("fallback_");
}

export function pathsEqual(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

export function getCorrectBranch(assessment: SocraticAssessment): McqBranch {
  return (
    assessment.socratic_tree[assessment.correct_option] ??
    Object.values(assessment.socratic_tree)[0]
  );
}

export function getMcqOptions(
  assessment: SocraticAssessment
): { key: McqKey; text: string }[] {
  return (["A", "B", "C", "D"] as McqKey[]).map((key) => ({
    key,
    text: assessment.options[key],
  }));
}

export function getMcqFeedback(
  assessment: SocraticAssessment,
  key: McqKey
): string {
  return (
    assessment.option_feedback?.[key] ??
    "That answer does not match what the text supports."
  );
}

export function getReasoningFeedback(
  assessment: SocraticAssessment,
  optionId: string
): string {
  if (isFallbackOption(optionId)) {
    return (
      assessment.reasoning_feedback?.[optionId] ??
      "Custom reasoning may miss the key point from the text."
    );
  }
  return (
    assessment.reasoning_feedback?.[optionId] ??
    "That reasoning step does not follow best from the text."
  );
}

export function getLayer1(assessment: SocraticAssessment): {
  question: string;
  options: SocraticOption[];
} {
  const branch = getCorrectBranch(assessment);
  return {
    question: branch.layer_1_question,
    options: branch.layer_1_options,
  };
}

export function getLayer2(
  assessment: SocraticAssessment,
  l1Id: string
): { question: string; options: SocraticOption[] } {
  const branch = getCorrectBranch(assessment).layer_2_branches[l1Id];
  return {
    question: branch.layer_2_question,
    options: branch.layer_2_options,
  };
}

export function getLayer3(assessment: SocraticAssessment): {
  question: string;
  options: SocraticOption[];
} {
  const branch = getCorrectBranch(assessment);
  return {
    question: branch.layer_3_question,
    options: branch.layer_3_options,
  };
}

export interface PathStepSummary {
  layer: string;
  question: string;
  selected: string;
  correct: string;
  isCorrect: boolean;
}

function findOptionText(options: SocraticOption[], id: string): string {
  const opt = options.find((o) => o.id === id);
  return opt?.text ?? id;
}

export function buildPathComparison(
  assessment: SocraticAssessment,
  selectedPath: string[]
): PathStepSummary[] {
  const topper = assessment.topper_path;
  if (!topper.length) return [];

  const branch = getCorrectBranch(assessment);
  const selMcq = selectedPath[0] as McqKey | undefined;
  const topMcq = assessment.correct_option as McqKey;

  const steps: PathStepSummary[] = [
    {
      layer: "Initial answer",
      question: assessment.question_text,
      selected: selMcq
        ? `${selMcq}: ${assessment.options[selMcq]}`
        : "—",
      correct: `${topMcq}: ${assessment.options[topMcq]}`,
      isCorrect: selMcq === topMcq,
    },
  ];

  const layerDefs = [
    { label: "Layer 1 — Reasoning", idx: 1 },
    { label: "Layer 2 — Deep dive", idx: 2 },
    { label: "Layer 3 — Mastery", idx: 3 },
  ] as const;

  for (const { label, idx } of layerDefs) {
    const topId = topper[idx];
    if (!topId) break;

    let correctText = topId;
    let question = "";
    if (idx === 1) {
      correctText = findOptionText(branch.layer_1_options, topId);
      question = branch.layer_1_question;
    } else if (idx === 2 && topper[1]) {
      const l2 = branch.layer_2_branches[topper[1]];
      correctText = l2 ? findOptionText(l2.layer_2_options, topId) : topId;
      question = l2?.layer_2_question ?? "";
    } else if (idx === 3 && topper[1] && topper[2]) {
      correctText = findOptionText(branch.layer_3_options, topId);
      question = branch.layer_3_question;
    }

    const selId = selectedPath[idx];
    let selectedText = "—";
    let isCorrect = false;
    if (selId && selMcq === topMcq) {
      if (idx === 1) {
        selectedText = findOptionText(branch.layer_1_options, selId);
      } else if (idx === 2 && selectedPath[1]) {
        const l2 = branch.layer_2_branches[selectedPath[1]];
        selectedText = l2 ? findOptionText(l2.layer_2_options, selId) : selId;
      } else if (idx === 3 && selectedPath[1] && selectedPath[2]) {
        selectedText = findOptionText(branch.layer_3_options, selId);
      }
      isCorrect = selId === topId;
    }

    steps.push({
      layer: label,
      question,
      selected: selectedText,
      correct: correctText,
      isCorrect,
    });
  }

  return steps;
}

export function expectedOptionAtLayer(
  assessment: SocraticAssessment,
  layer: RetryLayer
): string | null {
  const topper = assessment.topper_path;
  if (layer === "mcq") return topper[0] ?? null;
  if (layer === "layer_1") return topper[1] ?? null;
  if (layer === "layer_2") return topper[2] ?? null;
  if (layer === "layer_3") return topper[3] ?? null;
  return null;
}
