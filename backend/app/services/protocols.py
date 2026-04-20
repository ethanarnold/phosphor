"""Protocol generation - LLM-produced experimental protocols per opportunity."""

import json
import uuid

from fastapi import HTTPException, status
from litellm import acompletion
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.lab import Lab
from app.models.lab_state import LabState
from app.models.opportunity import Opportunity
from app.models.paper import Paper
from app.models.protocol import Protocol
from app.schemas.lab_state import LabStateData
from app.schemas.protocol import ProtocolContent

PROTOCOL_PROMPT_VERSION = "v1.0.0"

PROTOCOL_SYSTEM_PROMPT = """You are an experimental protocol generator for research labs. Given a lab's current capabilities and a research opportunity, produce a concrete, step-by-step protocol the lab can attempt.

Rules:
1. GROUND phases and materials in the lab's actual equipment, techniques, reagents, and organisms. Prefer what the lab already has.
2. If the opportunity requires a resource the lab does NOT have, include it in `flagged_gaps` — do not pretend the lab has it.
3. Produce AT LEAST 2 phases, each with at least 1 concrete step.
4. Cite source papers by DOI or PMID in `citations` (use whatever identifiers are supplied).
5. Keep steps actionable: include concentrations, temperatures, durations, or cycle counts where the source material provides them.

Output ONLY a valid JSON object. No markdown, no commentary.

Schema:
{
  "title": "string (<= 200 chars)",
  "phases": [
    {
      "name": "string",
      "steps": ["string", ...],
      "duration_estimate": "string or null",
      "materials_used": ["string", ...]
    }
  ],
  "materials": ["string", ...],
  "expected_outcomes": ["string", ...],
  "flagged_gaps": ["string", ...],
  "citations": ["DOI or PMID", ...]
}"""


def _strip_code_fence(response_text: str) -> str:
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return text


def _format_papers(papers: list[Paper]) -> str:
    if not papers:
        return "No source papers."
    parts: list[str] = []
    for p in papers:
        identifier = f"DOI {p.doi}" if p.doi else f"PMID {p.pmid}" if p.pmid else "—"
        parts.append(f"Paper ({identifier})\nTitle: {p.title}\nAbstract: {p.abstract}")
    return "\n\n".join(parts)


def _format_opportunity(opp: Opportunity) -> str:
    def _stringify(v: object) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, dict):
            return [str(x) for x in v.values()]
        return []

    return json.dumps(
        {
            "description": opp.description,
            "required_equipment": _stringify(opp.required_equipment),
            "required_techniques": _stringify(opp.required_techniques),
            "required_expertise": _stringify(opp.required_expertise),
            "estimated_complexity": opp.estimated_complexity,
        },
        indent=2,
    )


async def _generate_content(
    *,
    lab_state: LabStateData,
    opportunity: Opportunity,
    papers: list[Paper],
    settings: Settings,
) -> tuple[str, ProtocolContent]:
    user_prompt = f"""Lab state:
{json.dumps(lab_state.model_dump(mode="json"), indent=2)}

Research opportunity:
{_format_opportunity(opportunity)}

Source papers:
{_format_papers(papers)}

Produce the protocol JSON object:"""

    response = await acompletion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": PROTOCOL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=4000,
    )
    raw = _strip_code_fence(response.choices[0].message.content)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Protocol generation returned invalid JSON",
        ) from e

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Protocol generation did not return a JSON object",
        )

    title = str(parsed.pop("title", "")).strip() or opportunity.description[:200]
    try:
        content = ProtocolContent.model_validate(parsed)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Protocol generation failed schema validation",
        ) from e

    return title[:500], content


async def generate_protocol(
    session: AsyncSession,
    lab: Lab,
    opportunity_id: uuid.UUID,
    user_id: str,
    settings: Settings | None = None,
) -> Protocol:
    """Generate and persist a protocol for one opportunity.

    Raises HTTPException(404) if the opportunity or lab state is missing,
    HTTPException(502) if the LLM output fails validation.
    """
    if settings is None:
        settings = get_settings()

    opp_result = await session.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.lab_id == lab.id,
        )
    )
    opportunity = opp_result.scalar_one_or_none()
    if opportunity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    state_result = await session.execute(
        select(LabState).where(LabState.lab_id == lab.id).order_by(LabState.version.desc()).limit(1)
    )
    lab_state_row = state_result.scalar_one_or_none()
    if lab_state_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab has no state yet; submit signals first",
        )
    lab_state_data = LabStateData.model_validate(lab_state_row.state)

    papers: list[Paper] = []
    if opportunity.source_paper_ids:
        papers_result = await session.execute(
            select(Paper).where(Paper.id.in_(list(opportunity.source_paper_ids)))
        )
        papers = list(papers_result.scalars().all())

    title, content = await _generate_content(
        lab_state=lab_state_data,
        opportunity=opportunity,
        papers=papers,
        settings=settings,
    )

    protocol = Protocol(
        lab_id=lab.id,
        opportunity_id=opportunity.id,
        title=title,
        content=content.model_dump(mode="json"),
        lab_state_version=lab_state_row.version,
        llm_model=settings.llm_model,
        prompt_version=PROTOCOL_PROMPT_VERSION,
        created_by=user_id,
    )
    session.add(protocol)
    await session.flush()
    return protocol
