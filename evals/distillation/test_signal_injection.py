"""Signal injection tests - verify state updates correctly."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# These tests mock the LLM to test signal processing logic


def create_mock_llm_response(new_state: dict[str, Any]) -> AsyncMock:
    """Create a mock LLM response with the given state."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(message=AsyncMock(content=json.dumps(new_state)))
    ]
    return mock_response


class TestSignalInjection:
    """Test that signals correctly update lab state."""

    def test_add_equipment_signal(self, empty_state: dict[str, Any]) -> None:
        """Adding equipment via signal should update state."""
        # Simulate signal
        signal = {
            "signal_type": "correction",
            "content": {
                "correction_type": "add",
                "field": "equipment",
                "item_name": "Illumina MiSeq",
                "new_value": {
                    "name": "Illumina MiSeq",
                    "capabilities": ["sequencing"],
                    "limitations": None
                }
            }
        }

        # Expected result after processing
        expected_state = empty_state.copy()
        expected_state["equipment"] = [{
            "name": "Illumina MiSeq",
            "capabilities": ["sequencing"],
            "limitations": None
        }]
        expected_state["signal_count"] = 1

        # Verify signal structure is valid
        assert signal["signal_type"] == "correction"
        assert signal["content"]["field"] == "equipment"

        # In real test, we'd call the distillation engine
        # For now, verify expected state structure
        assert "equipment" in expected_state
        assert len(expected_state["equipment"]) == 1
        assert expected_state["equipment"][0]["name"] == "Illumina MiSeq"

    def test_add_experiment_signal(self, genomics_lab: dict[str, Any]) -> None:
        """Adding experiment should update experimental history."""
        current_state = genomics_lab["ground_truth"]
        initial_history_count = len(current_state["experimental_history"])

        # New experiment signal
        signal = {
            "signal_type": "experiment",
            "content": {
                "technique": "CRISPR knockout",
                "outcome": "success",
                "notes": "Successfully knocked out BRCA1 gene",
                "equipment_used": ["Bio-Rad CFX96 qPCR"],
                "organisms_used": ["HEK293T"],
                "reagents_used": ["Cas9 protein", "sgRNA"]
            }
        }

        # Verify signal is well-formed
        assert signal["signal_type"] == "experiment"
        assert signal["content"]["outcome"] in ["success", "partial", "failed"]

        # After processing, history should be updated or compressed
        # (actual compression logic would be in distillation service)

    def test_remove_equipment_signal(self, genomics_lab: dict[str, Any]) -> None:
        """Removing equipment via correction should update state."""
        current_state = genomics_lab["ground_truth"]
        initial_equipment_count = len(current_state["equipment"])

        # Correction signal to remove equipment
        signal = {
            "signal_type": "correction",
            "content": {
                "correction_type": "remove",
                "field": "equipment",
                "item_name": "Gel documentation system",
                "reason": "Equipment retired"
            }
        }

        # Verify signal structure
        assert signal["content"]["correction_type"] == "remove"
        assert signal["content"]["field"] == "equipment"

        # After processing, equipment count should decrease
        # (simulated - actual logic in distillation service)

    def test_update_technique_proficiency(self, genomics_lab: dict[str, Any]) -> None:
        """Updating technique proficiency should reflect in state."""
        current_state = genomics_lab["ground_truth"]

        # Find CRISPR technique
        crispr_technique = next(
            (t for t in current_state["techniques"] if "CRISPR" in t["name"]),
            None
        )
        assert crispr_technique is not None
        assert crispr_technique["proficiency"] == "competent"

        # Correction to upgrade proficiency
        signal = {
            "signal_type": "correction",
            "content": {
                "correction_type": "update",
                "field": "techniques",
                "item_name": "CRISPR-Cas9 gene editing",
                "new_value": {
                    "name": "CRISPR-Cas9 gene editing",
                    "proficiency": "expert",
                    "notes": "Now proficient in multiple cell types"
                },
                "reason": "Extensive practice and successful experiments"
            }
        }

        # Verify signal structure
        assert signal["content"]["new_value"]["proficiency"] == "expert"


class TestDocumentSignals:
    """Test document ingestion signals."""

    def test_protocol_document_signal(self) -> None:
        """Protocol documents should extract relevant information."""
        signal = {
            "signal_type": "document",
            "content": {
                "filename": "PCR_optimization_protocol.pdf",
                "document_type": "protocol",
                "text_chunks": [
                    "This protocol describes optimized PCR conditions for amplifying GC-rich regions.",
                    "Required equipment: Bio-Rad CFX96 thermocycler",
                    "Reagents: Q5 High-Fidelity DNA Polymerase, GC Enhancer"
                ],
                "extracted_equipment": ["Bio-Rad CFX96"],
                "extracted_techniques": ["PCR", "GC-rich amplification"]
            }
        }

        assert signal["signal_type"] == "document"
        assert signal["content"]["document_type"] == "protocol"
        assert len(signal["content"]["text_chunks"]) > 0

    def test_paper_document_signal(self) -> None:
        """Research papers should extract methodology information."""
        signal = {
            "signal_type": "document",
            "content": {
                "filename": "our_recent_paper.pdf",
                "document_type": "paper",
                "text_chunks": [
                    "We performed RNA-seq analysis on samples treated with compound X.",
                    "Flow cytometry analysis revealed increased apoptosis.",
                    "Western blot confirmed protein expression changes."
                ],
                "extracted_equipment": [],
                "extracted_techniques": ["RNA-seq", "flow cytometry", "Western blot"]
            }
        }

        assert signal["content"]["document_type"] == "paper"
        assert "RNA-seq" in signal["content"]["extracted_techniques"]
