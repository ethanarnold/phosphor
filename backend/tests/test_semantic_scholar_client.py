"""Tests for Semantic Scholar API client normalization."""

from datetime import date

import pytest

from app.services.semantic_scholar import SemanticScholarClient


class TestSemanticScholarNormalization:
    """Tests for paper normalization from S2 API format."""

    @pytest.fixture
    def client(self) -> SemanticScholarClient:
        return SemanticScholarClient(http_client=None)  # type: ignore

    def test_normalize_full_paper(self, client: SemanticScholarClient) -> None:
        """Full paper data should normalize correctly."""
        raw = {
            "paperId": "abc123",
            "externalIds": {"DOI": "10.1234/test", "PubMed": "12345678"},
            "title": "Test Paper Title",
            "abstract": "This is the abstract text.",
            "authors": [{"name": "John Smith"}, {"name": "Jane Doe"}],
            "journal": {"name": "Nature"},
            "year": 2024,
            "fieldsOfStudy": ["Biology", "Medicine"],
        }
        result = client._normalize_paper(raw)

        assert result is not None
        assert result["semantic_scholar_id"] == "abc123"
        assert result["doi"] == "10.1234/test"
        assert result["pmid"] == "12345678"
        assert result["title"] == "Test Paper Title"
        assert result["abstract"] == "This is the abstract text."
        assert len(result["authors"]) == 2
        assert result["authors"][0]["first_name"] == "John"
        assert result["authors"][0]["last_name"] == "Smith"
        assert result["journal"] == "Nature"
        assert result["publication_date"] == date(2024, 1, 1)
        assert result["source"] == "semantic_scholar"
        assert result["fields_of_study"] == ["Biology", "Medicine"]

    def test_normalize_paper_without_abstract(self, client: SemanticScholarClient) -> None:
        """Papers without abstracts should be skipped (return None)."""
        raw = {
            "paperId": "xyz789",
            "title": "No Abstract Paper",
            "abstract": None,
            "authors": [],
        }
        result = client._normalize_paper(raw)
        assert result is None

    def test_normalize_paper_without_title(self, client: SemanticScholarClient) -> None:
        """Papers without titles should be skipped."""
        raw = {
            "paperId": "xyz789",
            "title": None,
            "abstract": "Has abstract but no title",
            "authors": [],
        }
        result = client._normalize_paper(raw)
        assert result is None

    def test_normalize_paper_no_external_ids(self, client: SemanticScholarClient) -> None:
        """Papers without external IDs should still work."""
        raw = {
            "paperId": "abc123",
            "externalIds": None,
            "title": "Test Paper",
            "abstract": "Test abstract",
            "authors": [],
            "year": None,
        }
        result = client._normalize_paper(raw)
        assert result is not None
        assert result["doi"] is None
        assert result["pmid"] is None
        assert result["publication_date"] is None

    def test_normalize_author_single_name(self, client: SemanticScholarClient) -> None:
        """Authors with single names should be handled."""
        raw = {
            "paperId": "abc123",
            "title": "Test",
            "abstract": "Abstract",
            "authors": [{"name": "Madonna"}],
        }
        result = client._normalize_paper(raw)
        assert result is not None
        assert result["authors"][0]["last_name"] == "Madonna"
