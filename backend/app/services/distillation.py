"""Distillation engine - compresses signals into lab state."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import tiktoken
from litellm import acompletion
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.distillation import DistillationRun
from app.models.lab_state import LabState
from app.models.signal import RawSignal
from app.schemas.lab_state import LabStateData

PROMPT_VERSION = "v1.0.0"

SYSTEM_PROMPT = """You are a lab capability compressor. Your job is to maintain a compressed representation of a research lab's capabilities that an LLM can reason over effectively.

Given the lab's current state and new signals (experiments, documents, corrections), update the state to incorporate new information while maintaining compression.

Target output: under 2000 tokens when serialized as JSON.

Rules:
1. MERGE redundant information - if equipment is mentioned multiple times, consolidate
2. PRESERVE critical details - equipment capabilities, technique proficiency levels, expertise areas
3. SUMMARIZE experimental history - extract key insights, don't list every experiment
4. REMOVE outdated or superseded information
5. APPLY corrections directly - if a user says "we don't have X", remove X
6. MAINTAIN structure - output must be valid JSON matching the schema exactly

Schema:
{
  "equipment": [{"name": str, "capabilities": [str], "limitations": str|null}],
  "techniques": [{"name": str, "proficiency": "expert"|"competent"|"learning", "notes": str|null}],
  "expertise": [{"domain": str, "confidence": "high"|"medium"|"low"}],
  "organisms": [{"name": str, "strains": [str], "notes": str|null}],
  "reagents": [{"name": str, "quantity": str|null, "notes": str|null}],
  "experimental_history": [{"technique": str, "outcome": "success"|"partial"|"failed", "insight": str}],
  "resource_constraints": {"budget_notes": str|null, "time_constraints": str|null, "personnel_notes": str|null},
  "signal_count": int
}

Output ONLY valid JSON. No markdown, no explanation, just the JSON object."""


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4


def create_empty_state() -> dict[str, Any]:
    """Create an empty lab state."""
    return LabStateData(signal_count=0).model_dump()


async def run_distillation(
    session: AsyncSession,
    lab_id: uuid.UUID,
    signal_ids: list[uuid.UUID],
    settings: Settings | None = None,
) -> LabState:
    """Run distillation to update lab state with new signals.

    Args:
        session: Database session
        lab_id: Lab UUID
        signal_ids: List of signal UUIDs to process
        settings: App settings (uses default if not provided)

    Returns:
        The new LabState version

    Raises:
        ValueError: If distillation fails
    """
    if settings is None:
        settings = get_settings()

    # Get current state (or empty if none exists)
    current_state_result = await session.execute(
        select(LabState)
        .where(LabState.lab_id == lab_id)
        .order_by(LabState.version.desc())
        .limit(1)
    )
    current_state = current_state_result.scalar_one_or_none()

    if current_state:
        current_state_data = current_state.state
        input_version = current_state.version
        new_version = current_state.version + 1
    else:
        current_state_data = create_empty_state()
        input_version = None
        new_version = 1

    # Get signals to process
    signals_result = await session.execute(
        select(RawSignal).where(RawSignal.id.in_(signal_ids))
    )
    signals = signals_result.scalars().all()

    if not signals:
        raise ValueError("No signals found to process")

    # Format signals for prompt
    signals_text = "\n\n".join(
        f"Signal {i+1} (type: {s.signal_type}):\n{json.dumps(s.content, indent=2)}"
        for i, s in enumerate(signals)
    )

    # Create distillation run record
    distillation_run = DistillationRun(
        lab_id=lab_id,
        input_state_version=input_version,
        output_state_version=new_version,
        signals_processed=[s.id for s in signals],
        prompt_version=PROMPT_VERSION,
        llm_model=settings.llm_model,
        status="running",
    )
    session.add(distillation_run)
    await session.flush()

    try:
        # Call LLM for compression
        user_prompt = f"""Current state:
{json.dumps(current_state_data, indent=2)}

New signals to incorporate:
{signals_text}

Output the updated lab state JSON:"""

        response = await acompletion(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=4000,
        )

        # Parse response
        response_text = response.choices[0].message.content.strip()

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            # Remove markdown code block
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        new_state_data = json.loads(response_text)

        # Validate against schema
        validated_state = LabStateData.model_validate(new_state_data)

        # Update signal count
        validated_state.signal_count = (
            current_state_data.get("signal_count", 0) + len(signals)
        )

        # Count tokens
        state_json = validated_state.model_dump_json()
        token_count = count_tokens(state_json)

        # Warn if exceeding target
        if token_count > settings.max_state_tokens:
            # In production, could trigger re-compression
            pass

        # Create new state version
        new_state = LabState(
            lab_id=lab_id,
            version=new_version,
            state=validated_state.model_dump(),
            token_count=token_count,
            created_by="system",
        )
        session.add(new_state)

        # Mark signals as processed
        await session.execute(
            update(RawSignal)
            .where(RawSignal.id.in_(signal_ids))
            .values(processed=True)
        )

        # Update distillation run
        distillation_run.status = "completed"
        distillation_run.completed_at = datetime.now(UTC)

        await session.flush()

        return new_state

    except Exception as e:
        # Mark distillation as failed
        distillation_run.status = "failed"
        distillation_run.completed_at = datetime.now(UTC)
        await session.flush()

        raise ValueError(f"Distillation failed: {e}") from e


async def get_unprocessed_signals(
    session: AsyncSession,
    lab_id: uuid.UUID,
    limit: int = 10,
) -> list[RawSignal]:
    """Get unprocessed signals for a lab."""
    result = await session.execute(
        select(RawSignal)
        .where(
            RawSignal.lab_id == lab_id,
            RawSignal.processed == False,  # noqa: E712
        )
        .order_by(RawSignal.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())
