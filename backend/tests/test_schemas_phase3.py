"""Tests for Phase 3 Pydantic schemas (matching + protocol)."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.matching import (
    FeasibilityBreakdown,
    GapAnalysis,
    MatchScore,
    RankedOpportunity,
    RankedOpportunityList,
)
from app.schemas.opportunity import OpportunityResponse
from app.schemas.protocol import (
    ProtocolContent,
    ProtocolPhase,
    ProtocolResponse,
)


def _opp_response() -> OpportunityResponse:
    return OpportunityResponse(
        id=uuid.uuid4(),
        lab_id=uuid.uuid4(),
        description="Screen DNA damage repair genes in TNBC organoids",
        required_equipment=["Cas9", "organoid culture"],
        required_techniques=["CRISPR screening"],
        required_expertise=["Functional genomics"],
        estimated_complexity="high",
        source_paper_ids=[uuid.uuid4()],
        quality_score=0.9,
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestFeasibilityBreakdown:
    def test_accepts_valid_tiers(self) -> None:
        bd = FeasibilityBreakdown(
            equipment={"MiSeq": "have", "LC-MS": "cannot"},
            techniques={"PCR": "practiced"},
            expertise={"genomics": "strong"},
        )
        assert bd.equipment["MiSeq"] == "have"
        assert bd.techniques["PCR"] == "practiced"

    def test_rejects_unknown_tier(self) -> None:
        with pytest.raises(ValidationError):
            FeasibilityBreakdown(
                equipment={"MiSeq": "sometimes"},  # type: ignore[dict-item]
            )


class TestMatchScore:
    def test_valid_score(self) -> None:
        score = MatchScore(
            feasibility=0.8,
            alignment=0.6,
            composite=0.72,
            breakdown=FeasibilityBreakdown(),
        )
        assert score.composite == 0.72

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            MatchScore(
                feasibility=1.5,
                alignment=0.5,
                composite=0.5,
                breakdown=FeasibilityBreakdown(),
            )


class TestRankedList:
    def test_ranked_opportunity_bundles_score(self) -> None:
        opp = _opp_response()
        score = MatchScore(
            feasibility=0.5,
            alignment=0.5,
            composite=0.5,
            breakdown=FeasibilityBreakdown(),
        )
        item = RankedOpportunity(opportunity=opp, score=score)
        assert item.opportunity.id == opp.id
        assert item.score.composite == 0.5

    def test_list_with_total(self) -> None:
        opp = _opp_response()
        score = MatchScore(
            feasibility=0.5,
            alignment=0.5,
            composite=0.5,
            breakdown=FeasibilityBreakdown(),
        )
        payload = RankedOpportunityList(
            items=[RankedOpportunity(opportunity=opp, score=score)],
            total=1,
        )
        assert payload.total == 1
        assert len(payload.items) == 1


class TestGapAnalysis:
    def test_minimum_fields(self) -> None:
        ga = GapAnalysis(
            opportunity_id=uuid.uuid4(),
            estimated_effort="medium",
        )
        assert ga.estimated_effort == "medium"
        assert ga.missing_equipment == []

    def test_rejects_unknown_effort(self) -> None:
        with pytest.raises(ValidationError):
            GapAnalysis(
                opportunity_id=uuid.uuid4(),
                estimated_effort="extreme",  # type: ignore[arg-type]
            )


class TestProtocolContent:
    def _phase(self, name: str = "Setup") -> ProtocolPhase:
        return ProtocolPhase(
            name=name,
            steps=["Prepare buffer"],
            duration_estimate="1h",
            materials_used=["Tris buffer"],
        )

    def test_valid_protocol(self) -> None:
        content = ProtocolContent(
            phases=[self._phase("Setup"), self._phase("Run")],
            materials=["Tris buffer"],
            expected_outcomes=["Purified DNA"],
            flagged_gaps=[],
            citations=["10.1234/abc"],
        )
        assert len(content.phases) == 2

    def test_requires_minimum_two_phases(self) -> None:
        with pytest.raises(ValidationError):
            ProtocolContent(
                phases=[self._phase("Only")],
                expected_outcomes=["Something"],
            )

    def test_phase_requires_steps(self) -> None:
        with pytest.raises(ValidationError):
            ProtocolPhase(
                name="Empty",
                steps=[],
                materials_used=[],
            )


class TestProtocolResponse:
    def test_from_attributes(self) -> None:
        response = ProtocolResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            opportunity_id=uuid.uuid4(),
            title="Test protocol",
            content=ProtocolContent(
                phases=[
                    ProtocolPhase(name="A", steps=["a"], materials_used=[]),
                    ProtocolPhase(name="B", steps=["b"], materials_used=[]),
                ],
                expected_outcomes=["result"],
            ),
            lab_state_version=3,
            llm_model="claude-sonnet-4-20250514",
            prompt_version="v1.0.0",
            status="generated",
            created_at=datetime.now(),
            created_by="user_123",
        )
        assert response.status == "generated"
        assert response.lab_state_version == 3
