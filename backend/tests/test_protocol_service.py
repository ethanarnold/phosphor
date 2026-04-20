"""Tests for the protocol generation service."""

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.lab_state import Equipment, LabStateData, Technique
from app.services import protocols as protocols_service
from app.services.protocols import PROTOCOL_PROMPT_VERSION, _generate_content


class _OppStub:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.description = "Screen DNA damage repair genes in TNBC organoids"
        self.required_equipment = ["Cas9 delivery", "organoid culture"]
        self.required_techniques = ["CRISPR screening"]
        self.required_expertise = ["Functional genomics"]
        self.estimated_complexity = "high"


def _lab_state() -> LabStateData:
    return LabStateData(
        equipment=[Equipment(name="Cas9 delivery system", capabilities=[])],
        techniques=[Technique(name="CRISPR screening", proficiency="competent")],
    )


def _canned_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        llm_model="claude-sonnet-4-20250514",
        embedding_model="text-embedding-3-small",
    )


VALID_JSON = json.dumps(
    {
        "title": "CRISPR screen protocol for TNBC organoids",
        "phases": [
            {
                "name": "Organoid culture setup",
                "steps": [
                    "Thaw patient-derived TNBC organoids in Matrigel",
                    "Seed 5,000 organoids per well in 96-well plates",
                ],
                "duration_estimate": "5 days",
                "materials_used": ["Matrigel", "organoid culture medium"],
            },
            {
                "name": "CRISPR knockout screen",
                "steps": [
                    "Transduce organoids with Cas9 lentivirus",
                    "Select with puromycin (2 µg/mL) for 72h",
                    "Assess viability via CellTiter-Glo",
                ],
                "duration_estimate": "2 weeks",
                "materials_used": ["Cas9 lentivirus", "puromycin"],
            },
        ],
        "materials": ["Matrigel", "Cas9 lentivirus", "puromycin"],
        "expected_outcomes": [
            "Identification of synthetic lethal partners in BRCA1-null organoids"
        ],
        "flagged_gaps": [],
        "citations": ["10.1234/example-doi"],
    }
)


class TestGenerateContent:
    @pytest.mark.asyncio
    async def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_acompletion(**_: object) -> SimpleNamespace:
            return _canned_response(VALID_JSON)

        monkeypatch.setattr(protocols_service, "acompletion", fake_acompletion)

        title, content = await _generate_content(
            lab_state=_lab_state(),
            opportunity=_OppStub(),  # type: ignore[arg-type]
            papers=[],
            settings=_settings(),  # type: ignore[arg-type]
        )

        assert "CRISPR screen" in title
        assert len(content.phases) == 2
        assert any("Matrigel" in m for m in content.materials)
        assert content.citations == ["10.1234/example-doi"]

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fenced = f"```json\n{VALID_JSON}\n```"

        async def fake_acompletion(**_: object) -> SimpleNamespace:
            return _canned_response(fenced)

        monkeypatch.setattr(protocols_service, "acompletion", fake_acompletion)

        _, content = await _generate_content(
            lab_state=_lab_state(),
            opportunity=_OppStub(),  # type: ignore[arg-type]
            papers=[],
            settings=_settings(),  # type: ignore[arg-type]
        )
        assert len(content.phases) == 2

    @pytest.mark.asyncio
    async def test_invalid_json_raises_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_acompletion(**_: object) -> SimpleNamespace:
            return _canned_response("not valid json")

        monkeypatch.setattr(protocols_service, "acompletion", fake_acompletion)

        with pytest.raises(HTTPException) as excinfo:
            await _generate_content(
                lab_state=_lab_state(),
                opportunity=_OppStub(),  # type: ignore[arg-type]
                papers=[],
                settings=_settings(),  # type: ignore[arg-type]
            )
        assert excinfo.value.status_code == 502

    @pytest.mark.asyncio
    async def test_schema_violation_raises_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Single phase violates min_length=2 on phases
        bad = json.dumps(
            {
                "title": "Bad",
                "phases": [
                    {
                        "name": "Only phase",
                        "steps": ["do a thing"],
                        "duration_estimate": None,
                        "materials_used": [],
                    }
                ],
                "materials": [],
                "expected_outcomes": ["x"],
                "flagged_gaps": [],
                "citations": [],
            }
        )

        async def fake_acompletion(**_: object) -> SimpleNamespace:
            return _canned_response(bad)

        monkeypatch.setattr(protocols_service, "acompletion", fake_acompletion)

        with pytest.raises(HTTPException) as excinfo:
            await _generate_content(
                lab_state=_lab_state(),
                opportunity=_OppStub(),  # type: ignore[arg-type]
                papers=[],
                settings=_settings(),  # type: ignore[arg-type]
            )
        assert excinfo.value.status_code == 502


def test_prompt_version_pinned() -> None:
    # Bumping this is a PR-reviewable event: it invalidates persisted protocols
    # from prior versions for audit / comparison.
    assert PROTOCOL_PROMPT_VERSION == "v1.0.0"
