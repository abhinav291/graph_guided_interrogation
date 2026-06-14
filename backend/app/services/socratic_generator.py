from __future__ import annotations

import json
import random
import re

from pydantic import ValidationError

from app.models.socratic import ChunkNode, McqBranch, SocraticAssessment
from app.services.llm_client import (
    FALLBACK_LABEL,
    LlmClient,
    MCQ_KEYS,
    OPTION_MAX_WORDS,
    get_llm_client,
    normalize_llm_provider,
)

_STYLE_RULES = """VOICE AND STYLE (critical):
- Write like a UPSC Prelims examiner: direct, substantive, exam-ready questions.
- Ground every question in the study_material provided, but NEVER reference the source in the question wording.
- FORBIDDEN in question stems and options: "chunk", "passage", "text", "document", "study material", "source",
  "according to", "as per", "as stated in", "the diagram shows", "explicitly names/labels/lists in",
  "under CAUSE/SIGNIFICANCE in", "mentioned in the", "from the given".
- Ask about facts, causes, mechanisms, and relationships as if the student already studied the topic.
- Name specific terms, institutions, provisions, events, dates, or actors directly in the question.

BAD MCQ: "According to the chunk, what British legislation regarding salt triggered the Dandi March?"
GOOD MCQ: "Which British legislation's monopoly on salt prompted Gandhi to launch the Dandi March in 1930?"

BAD L1: "Which legislation does the chunk explicitly name under CAUSE?"
GOOD L1: "Which legislative measure establishing a salt monopoly directly motivated Gandhi's civil disobedience campaign?"

BAD L2: "What does the passage imply about mass mobilisation?"
GOOD L2: "If the Salt Act monopoly was the primary grievance, why did Gandhi select salt taxation over other colonial restrictions?"

BAD L3: "Which detail from the chunk confirms this reasoning?"
GOOD L3: "Given that the Salt Act (1882) was the legislative trigger, which structural sequence best shows cause preceding significance in the Civil Disobedience launch?"
"""

MCQ_SYSTEM = f"""You generate the opening MCQ for a UPSC-style Socratic assessment.

The user message contains study_material (your sole factual source) and a heading (topic context).
Use study_material for accuracy; never mention study_material, chunk, passage, or document in output.

Return ONLY valid JSON:
{{
  "question_text": "...",
  "options": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
  "correct_option": "B",
  "option_feedback": {{
    "A": "Why A fails: name the specific misconception or misread (under 20 words).",
    "C": "...",
    "D": "..."
  }},
  "topper_explanation": "2–3 sentences: why the correct option holds, citing the key fact or mechanism."
}}

{_STYLE_RULES}

Rules:
- Test ONE clear concept, fact, or relationship — not a vague summary.
- All four options must be plausible; distractors reflect common confusions (swapped cause/effect, wrong scope, wrong actor, adjacent but incorrect detail).
- Exactly 4 options A–D; each option at most {OPTION_MAX_WORDS} words (count carefully; prefer 10–16 words).
- option_feedback: explain why each WRONG option is wrong with a specific factual correction (omit correct_option).
- topper_explanation states the substantive reason the correct answer holds.
- Vary which letter is correct.
"""

BRANCH_SYSTEM = f"""You generate a linked Socratic reasoning chain for the CORRECT MCQ option.
The student already picked the right MCQ answer. Teach WHY — step by step — using only study_material for facts.

{_STYLE_RULES}

REASONING CHAIN (each layer must build on the previous):
  MCQ (given) → Layer 1 → Layer 2 (per L1 path) → Layer 3 (one question for the branch)

  Layer 1 — JUSTIFY the MCQ answer:
    Ask which evidence, causal link, definition, or exception best supports the correct MCQ option.
    Options = three distinct justification paths (not three rephrasings of the same idea).

  Layer 2 — EXTEND the chosen L1 path:
    For each L1 option, ask what logically follows IF that justification were true.
    layer_2_question must echo the L1 option concept (paraphrase; do not repeat the L1 question).
    Options = three implications/consequences/mechanisms; one sound, others overreach or contradict facts.

  Layer 3 — STRESS-TEST the full chain (MCQ + L1 + L2 logic):
    ONE question for the whole branch. Lock in the argument with a fine-grained detail
    (date, clause, actor, sequence, exception, or counterexample).

Return ONLY valid JSON:
{{
  "layer_1_question": "<topic-specific; ties to the correct MCQ answer>",
  "layer_1_options": [
    {{ "id": "L1_B1", "text": "..." }},
    {{ "id": "L1_B2", "text": "..." }},
    {{ "id": "L1_B3", "text": "..." }},
    {{ "id": "fallback_B", "text": "{FALLBACK_LABEL}" }}
  ],
  "layer_2_branches": {{
    "L1_B1": {{
      "layer_2_question": "<follows from L1_B1 concept>",
      "layer_2_options": [
        {{ "id": "L2_B1_1", "text": "..." }},
        {{ "id": "L2_B1_2", "text": "..." }},
        {{ "id": "L2_B1_3", "text": "..." }},
        {{ "id": "fallback_L2_B1", "text": "{FALLBACK_LABEL}" }}
      ]
    }},
    "L1_B2": {{ "...same shape; L2 question must match L1_B2 concept..." }},
    "L1_B3": {{ "...same shape..." }}
  }},
  "layer_3_question": "<synthesises MCQ + reasoning with a concrete named element>",
  "layer_3_options": [
    {{ "id": "L3_B_1", "text": "..." }},
    {{ "id": "L3_B_2", "text": "..." }},
    {{ "id": "L3_B_3", "text": "..." }},
    {{ "id": "fallback_L3_B", "text": "{FALLBACK_LABEL}" }}
  ],
  "option_feedback": {{
    "L1_B2": "State the specific gap: wrong evidence, wrong cause, or misread scope (under 20 words).",
    "L2_B1_3": "State the factual correction.",
    "L3_B_2": "State which fact contradicts this choice.",
    "fallback_B": "Custom reasoning may miss the key substantive point."
  }}
}}

Rules:
- Read mcq_question and correct_answer_text from the user message; every layer must stay anchored to them.
- Never use generic filler ("follows from text", "needs more context", "direct evidence", "the passage").
- L1/L2/L3 questions must each introduce NEW substantive angles — do not repeat the same sentence across layers.
- L2 branches: three different layer_2_questions (one per L1 path), each tied to its parent L1 option text.
- Exactly 4 options per layer (3 contextual + 1 fallback). Fallback text MUST be exactly: "{FALLBACK_LABEL}".
- Do NOT nest layer_3 under L2 — layer_3 is one shared question on the branch root.
- option_feedback for EVERY wrong contextual option and every fallback id.
- ALL option text at most {OPTION_MAX_WORDS} words (count carefully; prefer 10–16 words). Questions may be longer but must stay focused (one clear ask).
- Ids: L1_B1, L2_B1_1, L3_B_1, fallback_L3_B (prefix with mcq letter from mcq_key).
"""

_QUESTION_META_PREFIXES = (
    r"(?i)^according to (?:the )?(?:chunk|passage|text|document|study material|source(?: material)?|given (?:text|material|information)|above (?:text|passage)|extract|notes?|diagram)[,:]?\s*",
    r"(?i)^as (?:per|mentioned in|stated in|described in|noted in) (?:the )?(?:chunk|passage|text|document|study material|source|diagram)[,:]?\s*",
    r"(?i)^based on (?:the )?(?:chunk|passage|text|document|study material|source|diagram)[,:]?\s*",
    r"(?i)^from (?:the )?(?:chunk|passage|text|document|study material|source|diagram)[,:]?\s*",
    r"(?i)^in (?:the )?(?:chunk|passage|text|document|diagram)[,:]?\s*",
)

_QUESTION_META_INLINE = (
    (
        r"(?i)\bwhat evidence in the (?:chunk|passage|text|document|diagram) shows?\b",
        "what evidence shows",
    ),
    (
        r"(?i)\bdoes the (?:chunk|passage|text|document|diagram) explicitly name\b",
        "was",
    ),
    (
        r"(?i)\bdoes the (?:chunk|passage|text|document|diagram)\s+(?:show|state|identify|list|label|emphasise|attribute)\b",
        "indicates",
    ),
    (
        r"(?i)\bgiven that the (?:chunk|passage|text|document|diagram) explicitly labels?\b",
        "Given that",
    ),
    (
        r"(?i)\bthe (?:chunk|passage|text|document|diagram)\s+explicitly\s+(?:names?|lists?|labels?|states?|shows?|attributes?|emphasises?|indicates?)\b",
        "",
    ),
    (
        r"(?i)\bthe (?:chunk|passage|text|document|diagram)\s+(?:names?|lists?|labels?|states?|shows?)\b",
        "",
    ),
    (
        r"(?i)\b(?:in|from|within)\s+the\s+(?:chunk|passage|text|document|diagram)\b",
        "",
    ),
    (
        r"(?i)\bunder\s+['\"]?(?:CAUSE|SIGNIFICANCE|CONTEXT|PARTICIPATION)['\"]?\s+in\s+the\s+(?:chunk|passage|diagram)\b",
        "under CAUSE",
    ),
    (
        r"(?i)\bmentioned in the (?:chunk|passage|text|document)\b",
        "",
    ),
)


def _sanitize_question_text(text: str) -> str:
    result = text.strip()
    for pattern in _QUESTION_META_PREFIXES:
        result = re.sub(pattern, "", result, count=1)
    for pattern, replacement in _QUESTION_META_INLINE:
        result = re.sub(pattern, replacement, result)
    result = re.sub(r"(?i)\bwas as the\b", "was the", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result


def _sanitize_assessment_questions(payload: dict) -> None:
    payload["question_text"] = _sanitize_question_text(payload["question_text"])
    for branch in payload.get("socratic_tree", {}).values():
        branch["layer_1_question"] = _sanitize_question_text(branch["layer_1_question"])
        branch["layer_3_question"] = _sanitize_question_text(branch["layer_3_question"])
        for l2_branch in branch.get("layer_2_branches", {}).values():
            l2_branch["layer_2_question"] = _sanitize_question_text(
                l2_branch["layer_2_question"]
            )


def _option_id(opt: dict | object) -> str:
    return opt["id"] if isinstance(opt, dict) else opt.id


def _clamp_words(text: str, max_words: int = OPTION_MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip(",;:-—")


def _clamp_layer_options(options: list[dict]) -> None:
    for opt in options:
        if _option_id(opt).startswith("fallback_"):
            continue
        opt["text"] = _clamp_words(str(opt.get("text", "")))


def _clamp_branch_option_lengths(branch: dict) -> None:
    _clamp_layer_options(branch.get("layer_1_options", []))
    _clamp_layer_options(branch.get("layer_3_options", []))
    for l2_branch in branch.get("layer_2_branches", {}).values():
        _clamp_layer_options(l2_branch.get("layer_2_options", []))


def _clamp_mcq_options(options: dict[str, str]) -> dict[str, str]:
    return {key: _clamp_words(value) for key, value in options.items()}


def _mcq_letter_from_branch(raw: dict, fallback: str = "B") -> str:
    for opt in raw.get("layer_1_options", []):
        oid = _option_id(opt)
        if oid.startswith("L1_") and len(oid) >= 4:
            return oid[3]
    for opt in raw.get("layer_3_options", []):
        oid = _option_id(opt)
        if oid.startswith("L3_") and len(oid) >= 4:
            return oid[3]
    return fallback


def _placeholder_l3(mcq_letter: str) -> dict:
    return {
        "layer_3_question": (
            "Which fine-grained detail best confirms this line of reasoning?"
        ),
        "layer_3_options": [
            {"id": f"L3_{mcq_letter}_1", "text": "Matches the central mechanism"},
            {"id": f"L3_{mcq_letter}_2", "text": "Contradicts the stated exception"},
            {"id": f"L3_{mcq_letter}_3", "text": "Applies to a different context"},
            {"id": f"fallback_L3_{mcq_letter}", "text": FALLBACK_LABEL},
        ],
    }


def _placeholder_l2(l1_id: str) -> dict:
    suffix = l1_id.removeprefix("L1_")
    l2_ids = [f"L2_{suffix}_{i}" for i in (1, 2, 3)]
    return {
        "layer_2_question": (
            "Which consequence follows most logically from this justification?"
        ),
        "layer_2_options": [
            {"id": l2_ids[0], "text": "Supported by the underlying argument"},
            {"id": l2_ids[1], "text": "Overstates the historical claim"},
            {"id": l2_ids[2], "text": "Confuses cause with correlation"},
            {"id": f"fallback_L2_{suffix}", "text": FALLBACK_LABEL},
        ],
    }


def _normalize_fallback_options(options: list[dict]) -> None:
    for opt in options:
        if _option_id(opt).startswith("fallback_"):
            opt["text"] = FALLBACK_LABEL


def _strip_nested_l3(raw: dict) -> None:
    for l2_branch in raw.get("layer_2_branches", {}).values():
        l2_branch.pop("layer_3_branches", None)


def _normalize_mcq_branch(branch: dict) -> None:
    _normalize_fallback_options(branch.get("layer_1_options", []))
    _normalize_fallback_options(branch.get("layer_3_options", []))
    for l2_branch in branch.get("layer_2_branches", {}).values():
        _normalize_fallback_options(l2_branch.get("layer_2_options", []))


def _repair_mcq_branch(raw: dict) -> dict:
    _strip_nested_l3(raw)
    l2_branches = raw.setdefault("layer_2_branches", {})
    for opt in raw.get("layer_1_options", []):
        l1_id = _option_id(opt)
        if l1_id.startswith("fallback_"):
            continue
        if l1_id not in l2_branches:
            l2_branches[l1_id] = _placeholder_l2(l1_id)
        elif not l2_branches[l1_id].get("layer_2_question"):
            l2_branches[l1_id]["layer_2_question"] = (
                "Which consequence follows most logically from this justification?"
            )

    letter = _mcq_letter_from_branch(raw)
    if not raw.get("layer_3_question") or not raw.get("layer_3_options"):
        raw.update(_placeholder_l3(letter))
    _normalize_mcq_branch(raw)
    _clamp_branch_option_lengths(raw)
    return raw


def _extract_branch_and_feedback(raw: dict) -> tuple[dict, dict[str, str]]:
    feedback = {str(k): str(v) for k, v in raw.pop("option_feedback", {}).items()}
    return _repair_mcq_branch(raw), feedback


def _remap_letter_in_branch(data: dict, from_letter: str, to_letter: str) -> dict:
    if from_letter == to_letter:
        return data
    raw = json.dumps(data, ensure_ascii=False)
    for prefix in ("L1_", "L2_", "L3_", "fallback_L2_", "fallback_L3_", "fallback_"):
        raw = raw.replace(f"{prefix}{from_letter}", f"{prefix}{to_letter}")
    return json.loads(raw)


def _remap_feedback_ids(
    feedback: dict[str, str], from_letter: str, to_letter: str
) -> dict[str, str]:
    if from_letter == to_letter:
        return feedback
    remapped: dict[str, str] = {}
    for key, value in feedback.items():
        new_key = key
        for prefix in ("L1_", "L2_", "L3_", "fallback_L2_", "fallback_L3_", "fallback_"):
            new_key = new_key.replace(f"{prefix}{from_letter}", f"{prefix}{to_letter}")
        remapped[new_key] = value
    return remapped


def _shuffle_options(options: list[dict]) -> list[dict]:
    contextual = [o for o in options if not _option_id(o).startswith("fallback_")]
    fallback = [o for o in options if _option_id(o).startswith("fallback_")]
    random.shuffle(contextual)
    return contextual + fallback


def _pick_random_topper_path(branch: dict, correct_mcq: str) -> list[str]:
    l1_ids = [
        _option_id(o)
        for o in branch["layer_1_options"]
        if not _option_id(o).startswith("fallback_")
        and _option_id(o) in branch["layer_2_branches"]
    ]
    if not l1_ids:
        return [correct_mcq]
    l1_id = random.choice(l1_ids)
    l2_branch = branch["layer_2_branches"][l1_id]
    l2_ids = [
        _option_id(o)
        for o in l2_branch["layer_2_options"]
        if not _option_id(o).startswith("fallback_")
    ]
    if not l2_ids:
        return [correct_mcq, l1_id]
    l2_id = random.choice(l2_ids)
    l3_ids = [
        _option_id(o)
        for o in branch.get("layer_3_options", [])
        if not _option_id(o).startswith("fallback_")
    ]
    if not l3_ids:
        return [correct_mcq, l1_id, l2_id]
    l3_id = random.choice(l3_ids)
    return [correct_mcq, l1_id, l2_id, l3_id]


def _fill_missing_reasoning_feedback(branch: dict, feedback: dict[str, str]) -> dict[str, str]:
    for opt in branch.get("layer_1_options", []):
        oid = _option_id(opt)
        if oid not in feedback:
            feedback[oid] = (
                "This step misreads or overextends the substantive facts."
            )
    for l2_branch in branch.get("layer_2_branches", {}).values():
        for opt in l2_branch.get("layer_2_options", []):
            oid = _option_id(opt)
            if oid not in feedback:
                feedback[oid] = (
                    "This step misreads or overextends the substantive facts."
                )
    for opt in branch.get("layer_3_options", []):
        oid = _option_id(opt)
        if oid not in feedback:
            feedback[oid] = (
                "This step misreads or overextends the substantive facts."
            )
    return feedback


def _randomize_assessment(payload: dict) -> dict:
    old_correct = payload["correct_option"]
    letters = list(MCQ_KEYS)
    random.shuffle(letters)
    mapping = {old: letters[i] for i, old in enumerate(MCQ_KEYS)}

    payload["options"] = {mapping[k]: payload["options"][k] for k in MCQ_KEYS}
    old_mcq_feedback = payload.get("option_feedback", {})
    payload["option_feedback"] = {
        mapping[k]: old_mcq_feedback.get(k, "This option does not match the facts.")
        for k in MCQ_KEYS
        if k != old_correct
    }

    branch = payload["socratic_tree"][old_correct]
    new_correct = mapping[old_correct]
    remapped_branch = _remap_letter_in_branch(branch, old_correct, new_correct)
    remapped_branch["layer_1_options"] = _shuffle_options(remapped_branch["layer_1_options"])
    remapped_branch["layer_3_options"] = _shuffle_options(remapped_branch["layer_3_options"])
    for l2_branch in remapped_branch["layer_2_branches"].values():
        l2_branch["layer_2_options"] = _shuffle_options(l2_branch["layer_2_options"])

    payload["socratic_tree"] = {new_correct: remapped_branch}
    payload["correct_option"] = new_correct
    payload["reasoning_feedback"] = _remap_feedback_ids(
        payload.get("reasoning_feedback", {}), old_correct, new_correct
    )
    payload["topper_path"] = _pick_random_topper_path(remapped_branch, new_correct)
    topper_ids = set(payload["topper_path"])
    payload["reasoning_feedback"] = {
        k: v
        for k, v in payload["reasoning_feedback"].items()
        if k not in topper_ids
    }
    payload["reasoning_feedback"] = _fill_missing_reasoning_feedback(
        remapped_branch, payload["reasoning_feedback"]
    )
    _normalize_mcq_branch(remapped_branch)
    return payload


class SocraticGenerationError(Exception):
    pass


def _generate_mcq_base(
    heading: str,
    full_chunk_text: str,
    client: LlmClient,
) -> dict:
    user = json.dumps(
        {
            "heading": heading,
            "study_material": full_chunk_text,
            "style": "UPSC examiner voice. Never reference chunk, passage, text, or document in questions.",
        },
        ensure_ascii=False,
    )
    return client.complete_json(MCQ_SYSTEM, user, max_tokens=2048)


def _generate_branch(
    heading: str,
    full_chunk_text: str,
    mcq_key: str,
    option_text: str,
    question_text: str,
    client: LlmClient,
) -> tuple[McqBranch, dict[str, str]]:
    user = json.dumps(
        {
            "heading": heading,
            "study_material": full_chunk_text,
            "mcq_key": mcq_key,
            "mcq_question": question_text,
            "correct_answer_text": option_text,
            "instructions": (
                "Build an interlinked L1→L2→L3 chain. L1 justifies why this MCQ answer is correct. "
                "Each L2 question must follow from its parent L1 option. L3 stress-tests the full argument "
                "using a concrete named detail. Use specific names and concepts — no generic questions, "
                "and never reference chunk/passage/text/document in any question or option."
            ),
        },
        ensure_ascii=False,
    )
    raw = client.complete_json(BRANCH_SYSTEM, user, max_tokens=12288)
    branch_raw, feedback = _extract_branch_and_feedback(raw)
    return McqBranch.model_validate(branch_raw), feedback


def generate_socratic_assessment(
    heading: str,
    full_chunk_text: str,
    client: LlmClient | None = None,
    *,
    max_retries: int = 2,
) -> SocraticAssessment:
    client = client or get_llm_client()
    last_error: str | None = None

    for attempt in range(max_retries + 1):
        try:
            base = _generate_mcq_base(heading, full_chunk_text, client)
            base["options"] = _clamp_mcq_options(base["options"])
            correct = base["correct_option"]
            branch, reasoning_feedback = _generate_branch(
                heading,
                full_chunk_text,
                correct,
                base["options"][correct],
                base["question_text"],
                client,
            )
            payload = {
                "question_text": base["question_text"],
                "options": base["options"],
                "correct_option": correct,
                "option_feedback": base.get("option_feedback", {}),
                "socratic_tree": {correct: branch.model_dump()},
                "reasoning_feedback": reasoning_feedback,
                "topper_path": [],
                "topper_explanation": base["topper_explanation"],
            }
            _sanitize_assessment_questions(payload)
            payload = _randomize_assessment(payload)
            return SocraticAssessment.model_validate(payload)
        except (ValidationError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = str(exc)
            if attempt >= max_retries:
                raise SocraticGenerationError(
                    f"LLM output failed validation after retries: {last_error}"
                ) from exc

    raise SocraticGenerationError("Failed to generate valid Socratic assessment")


def ensure_assessment(node: ChunkNode, *, llm_provider: str = "groq") -> SocraticAssessment:
    if node.socratic_assessment is not None:
        return node.socratic_assessment
    assessment = generate_socratic_assessment(
        node.heading,
        node.full_chunk_text,
        client=get_llm_client(normalize_llm_provider(llm_provider)),
    )
    node.socratic_assessment = assessment
    return assessment
