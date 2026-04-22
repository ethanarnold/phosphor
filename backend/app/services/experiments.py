"""Experiment service — structured entry + LLM-parsed quick-log."""

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.signal import RawSignal
from app.schemas.experiment import ExperimentEntry

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


def _strip_code_fence(raw: str) -> str:
    # Sonnet 4.6 often wraps JSON in ```json ... ``` despite the "ONLY valid JSON" instruction.
    m = _FENCE_RE.match(raw)
    return m.group(1) if m else raw


QUICK_LOG_PROMPT = """You parse free-text experiment notes into structured form.

Output ONLY valid JSON matching this schema:
{
  "technique": str (required, concrete name like "Western blot", "qPCR"),
  "outcome": "success" | "partial" | "failed" (required; infer from tone),
  "notes": str (required; the user's original observations, cleaned up),
  "equipment_used": [str],
  "organisms_used": [str],
  "reagents_used": [str]
}

If the text is too vague to determine a technique, use "unspecified" and set outcome to "partial".
Do not invent equipment/reagents that are not mentioned. Leave lists empty if unclear."""


async def create_experiment_signal(
    *,
    session: AsyncSession,
    lab_id: uuid.UUID,
    created_by: str,
    entry: ExperimentEntry,
) -> RawSignal:
    """Persist an experiment entry as a RawSignal."""
    if entry.date is None:
        entry = entry.model_copy(update={"date": datetime.now(UTC)})

    signal = RawSignal(
        lab_id=lab_id,
        signal_type="experiment",
        content=json.loads(entry.model_dump_json()),
        created_by=created_by,
    )
    session.add(signal)
    await session.flush()
    return signal


async def parse_quick_log(
    *,
    text: str,
    outcome_hint: str | None,
    settings: Settings,
) -> ExperimentEntry:
    """Use the LLM to parse a single free-text field into an ExperimentEntry."""
    user_prompt = text
    if outcome_hint:
        user_prompt = f"[User says outcome was: {outcome_hint}]\n\n{text}"

    response = await acompletion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": QUICK_LOG_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    raw = response.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(_strip_code_fence(raw))
    data.setdefault("notes", text)
    return ExperimentEntry.model_validate(data)
