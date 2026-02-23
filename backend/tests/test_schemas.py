"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.lab_state import (
    Equipment,
    ExperimentSummary,
    Expertise,
    LabStateData,
    Technique,
)
from app.schemas.signal import (
    CorrectionContent,
    DocumentContent,
    ExperimentContent,
    SignalCreate,
)


class TestLabStateSchemas:
    """Tests for lab state schemas."""

    def test_equipment_valid(self) -> None:
        """Valid equipment should parse."""
        equipment = Equipment(
            name="PCR Machine",
            capabilities=["PCR", "qPCR"],
            limitations="Max 96 samples",
        )
        assert equipment.name == "PCR Machine"
        assert len(equipment.capabilities) == 2

    def test_equipment_minimal(self) -> None:
        """Equipment with minimal fields should parse."""
        equipment = Equipment(name="Microscope", capabilities=[])
        assert equipment.name == "Microscope"
        assert equipment.limitations is None

    def test_equipment_name_required(self) -> None:
        """Equipment should require name."""
        with pytest.raises(ValidationError):
            Equipment(capabilities=["test"])  # type: ignore

    def test_technique_valid_proficiency(self) -> None:
        """Technique should accept valid proficiency values."""
        for proficiency in ["expert", "competent", "learning"]:
            technique = Technique(name="PCR", proficiency=proficiency)  # type: ignore
            assert technique.proficiency == proficiency

    def test_technique_invalid_proficiency(self) -> None:
        """Technique should reject invalid proficiency."""
        with pytest.raises(ValidationError):
            Technique(name="PCR", proficiency="beginner")  # type: ignore

    def test_experiment_summary_valid(self) -> None:
        """Valid experiment summary should parse."""
        summary = ExperimentSummary(
            technique="CRISPR",
            outcome="success",
            insight="Achieved 80% editing efficiency",
        )
        assert summary.outcome == "success"

    def test_lab_state_empty(self) -> None:
        """Empty lab state should be valid."""
        state = LabStateData()
        assert state.equipment == []
        assert state.signal_count == 0

    def test_lab_state_full(self) -> None:
        """Full lab state should parse."""
        state = LabStateData(
            equipment=[Equipment(name="PCR", capabilities=["amplification"])],
            techniques=[Technique(name="PCR", proficiency="expert")],
            expertise=[Expertise(domain="Genomics", confidence="high")],
            signal_count=5,
        )
        assert len(state.equipment) == 1
        assert state.signal_count == 5


class TestSignalSchemas:
    """Tests for signal schemas."""

    def test_experiment_content_valid(self) -> None:
        """Valid experiment content should parse."""
        content = ExperimentContent(
            technique="Western Blot",
            outcome="success",
            notes="Detected target protein at expected size",
            equipment_used=["Gel apparatus"],
        )
        assert content.outcome == "success"

    def test_experiment_content_all_outcomes(self) -> None:
        """Experiment should accept all outcome values."""
        for outcome in ["success", "partial", "failed"]:
            content = ExperimentContent(
                technique="PCR",
                outcome=outcome,  # type: ignore
                notes="Test",
            )
            assert content.outcome == outcome

    def test_document_content_valid(self) -> None:
        """Valid document content should parse."""
        content = DocumentContent(
            filename="protocol.pdf",
            document_type="protocol",
            text_chunks=["Step 1: Add reagent"],
        )
        assert content.document_type == "protocol"

    def test_correction_content_valid(self) -> None:
        """Valid correction content should parse."""
        content = CorrectionContent(
            correction_type="add",
            field="equipment",
            item_name="New Microscope",
            new_value={"name": "New Microscope", "capabilities": []},
        )
        assert content.correction_type == "add"

    def test_signal_create_experiment(self) -> None:
        """Signal create should validate experiment content."""
        signal = SignalCreate(
            signal_type="experiment",
            content={
                "technique": "PCR",
                "outcome": "success",
                "notes": "Amplified target gene",
            },
        )
        typed = signal.get_typed_content()
        assert isinstance(typed, ExperimentContent)

    def test_signal_create_document(self) -> None:
        """Signal create should validate document content."""
        signal = SignalCreate(
            signal_type="document",
            content={
                "filename": "test.pdf",
                "document_type": "paper",
                "text_chunks": ["Abstract text"],
            },
        )
        typed = signal.get_typed_content()
        assert isinstance(typed, DocumentContent)

    def test_signal_create_correction(self) -> None:
        """Signal create should validate correction content."""
        signal = SignalCreate(
            signal_type="correction",
            content={
                "correction_type": "remove",
                "field": "equipment",
                "item_name": "Old machine",
            },
        )
        typed = signal.get_typed_content()
        assert isinstance(typed, CorrectionContent)
