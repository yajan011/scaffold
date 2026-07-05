"""LLM-judge scorer: a model grades the output against a rubric."""

from __future__ import annotations

import json
import re
from typing import Any

from ankora.models import Case, Message, ScorerResult
from ankora.providers.base import Provider

_JUDGE_SYSTEM = (
    "You are a strict evaluator. Grade the candidate answer against the rubric "
    "and reference. Respond with a compact JSON object of the form "
    '{"score": <number between 0 and 1>, "justification": <one short sentence>}.'
)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_LABELED_SCORE = re.compile(r"score\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


class LLMJudgeScorer:
    """Grade an output by asking an injected judge provider to apply a rubric."""

    name = "llm_judge"

    def __init__(self, provider: Provider, rubric: str, threshold: float = 0.7) -> None:
        self.provider = provider
        self.rubric = rubric
        self.threshold = threshold

    def score(self, case: Case, output: str) -> ScorerResult:
        completion = self.provider.complete(self._build_messages(case, output), {"temperature": 0})
        value, justification = _parse_judgement(completion.text)
        return ScorerResult(
            scorer=self.name,
            score=value,
            passed=value >= self.threshold,
            threshold=self.threshold,
            detail=justification,
        )

    def _build_messages(self, case: Case, output: str) -> list[Message]:
        user = (
            f"Rubric:\n{self.rubric}\n\n"
            f"Reference answer:\n{case.reference.output}\n\n"
            f"Candidate answer:\n{output}\n\n"
            "Return only the JSON object."
        )
        return [
            Message(role="system", content=_JUDGE_SYSTEM),
            Message(role="user", content=user),
        ]


def _parse_judgement(text: str) -> tuple[float, str]:
    """Extract a 0..1 score and a short justification from possibly-messy text."""
    text = text or ""

    # 1. A JSON object carrying an explicit score.
    obj = _find_json_object(text)
    if isinstance(obj, dict) and "score" in obj:
        value = _to_score(obj.get("score"))
        if value is not None:
            justification = str(obj.get("justification") or obj.get("reason") or "").strip()
            return value, justification or _summarize(text)

    # 2. A labeled "score: 0.8" anywhere in the prose.
    match = _LABELED_SCORE.search(text)
    if match:
        value = _to_score(match.group(1))
        if value is not None:
            return value, _summarize(text)

    # 3. The first decimal that already looks like a 0..1 score.
    for token in _NUMBER.findall(text):
        if "." in token:
            number = float(token)
            if 0.0 <= number <= 1.0:
                return number, _summarize(text)

    # 4. Fallback: the first number, clamped into range.
    numbers = _NUMBER.findall(text)
    if numbers:
        return _clamp(float(numbers[0])), _summarize(text)

    return 0.0, "could not parse a score from judge output"


def _to_score(value: Any) -> float | None:
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _summarize(text: str, limit: int = 200) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:limit] if collapsed else "(no justification provided)"


def _find_json_object(text: str) -> Any:
    """Find and parse the first balanced ``{...}`` object in ``text``, if any."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : index + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
        start = text.find("{", start + 1)
    return None
