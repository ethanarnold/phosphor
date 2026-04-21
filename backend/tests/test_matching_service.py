"""Unit tests for the matching service scoring helpers."""

from app.schemas.lab_state import (
    Equipment,
    Expertise,
    LabStateData,
    Technique,
)
from app.schemas.matching import FeasibilityBreakdown
from app.services.matching import (
    build_match_score,
    feasibility_score,
    score_equipment,
    score_expertise,
    score_techniques,
)


def _genomics_lab() -> LabStateData:
    return LabStateData(
        equipment=[
            Equipment(
                name="Illumina MiSeq",
                capabilities=["targeted sequencing", "amplicon sequencing"],
                limitations=None,
            ),
            Equipment(
                name="Bio-Rad CFX96 qPCR",
                capabilities=["real-time PCR", "gene expression"],
                limitations=None,
            ),
            Equipment(
                name="Nanodrop 2000",
                capabilities=["DNA quantification"],
                limitations=None,
            ),
        ],
        techniques=[
            Technique(name="PCR", proficiency="expert", notes=None),
            Technique(name="CRISPR-Cas9 gene editing", proficiency="competent", notes=None),
            Technique(name="Flow cytometry", proficiency="learning", notes=None),
        ],
        expertise=[
            Expertise(domain="Molecular biology", confidence="high"),
            Expertise(domain="Bioinformatics", confidence="medium"),
        ],
    )


class _OppStub:
    """Mimic ORM Opportunity for scoring without a DB."""

    def __init__(self, equipment: list[str], techniques: list[str], expertise: list[str]):
        self.required_equipment = equipment
        self.required_techniques = techniques
        self.required_expertise = expertise


class TestScoreEquipment:
    def test_exact_name_match_is_have(self) -> None:
        lab = _genomics_lab()
        result = score_equipment(lab, ["Illumina MiSeq"])
        assert result["Illumina MiSeq"] == "have"

    def test_capability_match_is_have(self) -> None:
        lab = _genomics_lab()
        result = score_equipment(lab, ["real-time PCR"])
        assert result["real-time PCR"] == "have"

    def test_acquirable_when_keyword_matches(self) -> None:
        lab = _genomics_lab()
        # No microscope in lab; microscope is on the ACQUIRABLE list
        result = score_equipment(lab, ["fluorescence microscope"])
        assert result["fluorescence microscope"] == "acquire"

    def test_unknown_is_cannot(self) -> None:
        lab = _genomics_lab()
        exotic = score_equipment(lab, ["synchrotron beamline"])
        assert exotic["synchrotron beamline"] == "cannot"
        # Expensive/specialized items that superficially match an acquirable
        # keyword are blocked via NON_ACQUIRABLE_PHRASES ('cryo', 'electron
        # microscope'). Cryo-EM costs $1M+; don't tell a lab it's 'acquirable'.
        blocked = score_equipment(lab, ["cryo-electron microscope"])
        assert blocked["cryo-electron microscope"] == "cannot"


class TestScoreTechniques:
    def test_practiced_for_expert(self) -> None:
        lab = _genomics_lab()
        result = score_techniques(lab, ["PCR"])
        assert result["PCR"] == "practiced"

    def test_practiced_for_competent(self) -> None:
        lab = _genomics_lab()
        result = score_techniques(lab, ["CRISPR-Cas9 gene editing"])
        assert result["CRISPR-Cas9 gene editing"] == "practiced"

    def test_learnable_when_learning(self) -> None:
        lab = _genomics_lab()
        result = score_techniques(lab, ["flow cytometry"])
        assert result["flow cytometry"] == "learnable"

    def test_learnable_via_adjacent_expertise(self) -> None:
        lab = _genomics_lab()
        # Lab has "Bioinformatics" medium expertise; technique "Bioinformatics"
        # sharing that domain should be learnable even if not listed directly.
        result = score_techniques(lab, ["Bioinformatics pipelines"])
        assert result["Bioinformatics pipelines"] == "learnable"

    def test_gap_when_unknown(self) -> None:
        lab = _genomics_lab()
        result = score_techniques(lab, ["nuclear magnetic resonance spectroscopy"])
        assert result["nuclear magnetic resonance spectroscopy"] == "gap"


class TestScoreExpertise:
    def test_strong_for_high_confidence(self) -> None:
        lab = _genomics_lab()
        result = score_expertise(lab, ["Molecular biology"])
        assert result["Molecular biology"] == "strong"

    def test_adjacent_for_medium(self) -> None:
        lab = _genomics_lab()
        result = score_expertise(lab, ["Bioinformatics"])
        assert result["Bioinformatics"] == "adjacent"

    def test_gap_when_unknown(self) -> None:
        lab = _genomics_lab()
        result = score_expertise(lab, ["Quantum optics"])
        assert result["Quantum optics"] == "gap"


class TestFeasibilityScore:
    def test_all_have_yields_one(self) -> None:
        bd = FeasibilityBreakdown(
            equipment={"MiSeq": "have"},
            techniques={"PCR": "practiced"},
            expertise={"Molecular biology": "strong"},
        )
        assert feasibility_score(bd) == 1.0

    def test_all_missing_yields_zero(self) -> None:
        bd = FeasibilityBreakdown(
            equipment={"exotic": "cannot"},
            techniques={"exotic": "gap"},
            expertise={"exotic": "gap"},
        )
        assert feasibility_score(bd) == 0.0

    def test_no_requirements_is_neutral(self) -> None:
        bd = FeasibilityBreakdown(equipment={}, techniques={}, expertise={})
        assert feasibility_score(bd) == 0.5

    def test_partial_mix(self) -> None:
        bd = FeasibilityBreakdown(
            equipment={"a": "have", "b": "cannot"},  # avg 0.5
            techniques={"t": "practiced"},  # avg 1.0
            expertise={"e": "adjacent"},  # avg 0.6
        )
        # weighted: 0.5*0.4 + 1.0*0.4 + 0.6*0.2 = 0.2 + 0.4 + 0.12 = 0.72
        assert abs(feasibility_score(bd) - 0.72) < 1e-6


class TestBuildMatchScore:
    def test_composite_blends_feasibility_and_alignment(self) -> None:
        lab = _genomics_lab()
        opp = _OppStub(
            equipment=["Illumina MiSeq"],
            techniques=["PCR"],
            expertise=["Molecular biology"],
        )
        score = build_match_score(lab, opp, alignment=0.5)  # type: ignore[arg-type]
        # feasibility = 1.0, alignment = 0.5 -> composite = 0.6*1.0 + 0.4*0.5 = 0.8
        assert score.feasibility == 1.0
        assert score.alignment == 0.5
        assert abs(score.composite - 0.8) < 1e-6

    def test_breakdown_is_populated(self) -> None:
        lab = _genomics_lab()
        opp = _OppStub(
            equipment=["Illumina MiSeq"],
            techniques=["Unknown Technique"],
            expertise=["Molecular biology"],
        )
        score = build_match_score(lab, opp, alignment=0.5)  # type: ignore[arg-type]
        assert score.breakdown.equipment["Illumina MiSeq"] == "have"
        assert score.breakdown.techniques["Unknown Technique"] == "gap"
        assert score.breakdown.expertise["Molecular biology"] == "strong"
