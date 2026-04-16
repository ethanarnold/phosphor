"""Tests for Phase 2 Pydantic schemas."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from app.schemas.literature_scan import ScanRequest, ScanResponse
from app.schemas.opportunity import (
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityStatusUpdate,
)
from app.schemas.paper import PaperResponse


class TestPaperSchemas:
    """Tests for paper schemas."""

    def test_paper_response_minimal(self) -> None:
        """Paper response with minimal fields."""
        paper = PaperResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            title="Test Paper",
            abstract="Test abstract text",
            source="pubmed",
            created_at=datetime.now(),
        )
        assert paper.title == "Test Paper"
        assert paper.doi is None
        assert paper.pmid is None

    def test_paper_response_full(self) -> None:
        """Paper response with all fields."""
        paper = PaperResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            doi="10.1234/test",
            pmid="12345678",
            semantic_scholar_id="abc123",
            title="Full Paper",
            abstract="Full abstract",
            authors=[{"last_name": "Smith", "first_name": "John"}],
            journal="Nature",
            source="semantic_scholar",
            created_at=datetime.now(),
        )
        assert paper.doi == "10.1234/test"
        assert paper.authors is not None
        assert len(paper.authors) == 1


class TestOpportunitySchemas:
    """Tests for opportunity schemas."""

    def test_opportunity_response(self) -> None:
        """Valid opportunity response."""
        opp = OpportunityResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            description="Test opportunity description",
            required_equipment=["PCR machine"],
            required_techniques=["Western blot"],
            required_expertise=["Molecular biology"],
            estimated_complexity="medium",
            source_paper_ids=[uuid.uuid4()],
            quality_score=0.85,
            status="active",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert opp.estimated_complexity == "medium"
        assert opp.quality_score == 0.85

    def test_opportunity_status_update_valid(self) -> None:
        """Valid status update values."""
        for status_val in ["active", "dismissed", "archived"]:
            update = OpportunityStatusUpdate(status=status_val)  # type: ignore
            assert update.status == status_val

    def test_opportunity_status_update_invalid(self) -> None:
        """Invalid status value should fail."""
        with pytest.raises(ValidationError):
            OpportunityStatusUpdate(status="invalid")  # type: ignore

    def test_opportunity_list_response(self) -> None:
        """Opportunity list response."""
        resp = OpportunityListResponse(opportunities=[], total=0)
        assert resp.total == 0
        assert resp.opportunities == []


class TestScanSchemas:
    """Tests for literature scan schemas."""

    def test_scan_request_minimal(self) -> None:
        """Scan request with minimal fields."""
        req = ScanRequest(query_terms=["CRISPR"])
        assert req.query_terms == ["CRISPR"]
        assert req.max_results == 100
        assert len(req.sources) == 2

    def test_scan_request_full(self) -> None:
        """Scan request with all fields."""
        req = ScanRequest(
            query_terms=["CRISPR", "gene editing"],
            mesh_terms=["Gene Editing"],
            field_of_study="Biology",
            max_results=50,
            sources=["pubmed"],
        )
        assert req.max_results == 50
        assert req.sources == ["pubmed"]

    def test_scan_request_empty_query_terms(self) -> None:
        """Scan request requires at least one query term."""
        with pytest.raises(ValidationError):
            ScanRequest(query_terms=[])

    def test_scan_request_max_results_bounds(self) -> None:
        """Max results must be between 1 and 500."""
        with pytest.raises(ValidationError):
            ScanRequest(query_terms=["test"], max_results=0)
        with pytest.raises(ValidationError):
            ScanRequest(query_terms=["test"], max_results=501)

    def test_scan_request_invalid_source(self) -> None:
        """Invalid source should fail."""
        with pytest.raises(ValidationError):
            ScanRequest(query_terms=["test"], sources=["google_scholar"])  # type: ignore

    def test_scan_response(self) -> None:
        """Valid scan response."""
        resp = ScanResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            scan_type="manual",
            query_params={"query_terms": ["test"]},
            papers_found=10,
            papers_new=5,
            opportunities_extracted=3,
            status="completed",
            started_at=datetime.now(),
            triggered_by="user_123",
        )
        assert resp.papers_found == 10
        assert resp.status == "completed"


class TestApiKeySchemas:
    """Tests for API key schemas."""

    def test_api_key_create(self) -> None:
        """Valid API key creation request."""
        key = ApiKeyCreate(
            name="My API Key",
            scopes={"literature:scan": True, "opportunities:read": True},
        )
        assert key.name == "My API Key"
        assert key.scopes["literature:scan"] is True

    def test_api_key_create_empty_name(self) -> None:
        """Empty name should fail."""
        with pytest.raises(ValidationError):
            ApiKeyCreate(name="", scopes={"read": True})

    def test_api_key_create_response(self) -> None:
        """API key create response includes plaintext key."""
        resp = ApiKeyCreateResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            name="Test Key",
            key="ph_abc123def456",
            key_prefix="ph_abc12",
            scopes={"read": True},
            created_at=datetime.now(),
        )
        assert resp.key.startswith("ph_")

    def test_api_key_response_no_plaintext(self) -> None:
        """Regular API key response has no plaintext key field."""
        resp = ApiKeyResponse(
            id=uuid.uuid4(),
            lab_id=uuid.uuid4(),
            name="Test Key",
            key_prefix="ph_abc12",
            scopes={"read": True},
            is_active=True,
            created_at=datetime.now(),
        )
        assert not hasattr(resp, "key") or "key" not in resp.model_fields
