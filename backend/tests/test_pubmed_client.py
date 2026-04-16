"""Tests for PubMed API client XML parsing."""

from datetime import date

import pytest

from app.services.pubmed import PubMedClient

# Sample PubMed EFetch XML response (simplified)
SAMPLE_EFETCH_XML = """<?xml version="1.0" encoding="utf-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>CRISPR-Cas9 knockout study in cancer organoids</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">We studied CRISPR knockouts.</AbstractText>
          <AbstractText Label="RESULTS">BRCA1 knockout showed synthetic lethality.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
          </Author>
          <Author>
            <LastName>Doe</LastName>
            <ForeName>Jane</ForeName>
          </Author>
        </AuthorList>
        <Journal>
          <Title>Nature Methods</Title>
          <JournalIssue>
            <PubDate>
              <Year>2024</Year>
              <Month>03</Month>
            </PubDate>
          </JournalIssue>
        </Journal>
        <ArticleDate>
          <Year>2024</Year>
          <Month>02</Month>
          <Day>15</Day>
        </ArticleDate>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName>CRISPR-Cas Systems</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName>Gene Knockout Techniques</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1038/nmeth.1234</ArticleId>
        <ArticleId IdType="pubmed">12345678</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>99999999</PMID>
      <Article>
        <ArticleTitle>Paper without abstract</ArticleTitle>
        <AuthorList>
          <Author><LastName>Nobody</LastName></Author>
        </AuthorList>
        <Journal>
          <Title>Some Journal</Title>
          <JournalIssue>
            <PubDate><Year>2024</Year></PubDate>
          </JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">99999999</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""


class TestPubMedXMLParsing:
    """Tests for PubMed XML response parsing."""

    @pytest.fixture
    def client(self) -> PubMedClient:
        """Create a PubMed client (no http_client needed for parsing tests)."""
        return PubMedClient(http_client=None)  # type: ignore

    def test_parse_article_with_abstract(self, client: PubMedClient) -> None:
        """Articles with abstracts should be parsed correctly."""
        papers = client._parse_efetch_xml(SAMPLE_EFETCH_XML)

        # Only one paper has an abstract
        assert len(papers) == 1

        paper = papers[0]
        assert paper["pmid"] == "12345678"
        assert paper["doi"] == "10.1038/nmeth.1234"
        assert paper["title"] == "CRISPR-Cas9 knockout study in cancer organoids"
        assert "BACKGROUND" in paper["abstract"]
        assert "RESULTS" in paper["abstract"]
        assert paper["journal"] == "Nature Methods"
        assert paper["source"] == "pubmed"

    def test_parse_authors(self, client: PubMedClient) -> None:
        """Authors should be parsed correctly."""
        papers = client._parse_efetch_xml(SAMPLE_EFETCH_XML)
        paper = papers[0]

        assert len(paper["authors"]) == 2
        assert paper["authors"][0]["last_name"] == "Smith"
        assert paper["authors"][0]["first_name"] == "John"
        assert paper["authors"][1]["last_name"] == "Doe"

    def test_parse_mesh_terms(self, client: PubMedClient) -> None:
        """MeSH terms should be parsed."""
        papers = client._parse_efetch_xml(SAMPLE_EFETCH_XML)
        paper = papers[0]

        assert len(paper["mesh_terms"]) == 2
        assert "CRISPR-Cas Systems" in paper["mesh_terms"]

    def test_parse_publication_date(self, client: PubMedClient) -> None:
        """Publication date should be extracted."""
        papers = client._parse_efetch_xml(SAMPLE_EFETCH_XML)
        paper = papers[0]

        assert paper["publication_date"] == date(2024, 2, 15)

    def test_skip_papers_without_abstract(self, client: PubMedClient) -> None:
        """Papers without abstracts should be skipped."""
        papers = client._parse_efetch_xml(SAMPLE_EFETCH_XML)
        pmids = [p["pmid"] for p in papers]
        assert "99999999" not in pmids


class TestPubMedSearchParsing:
    """Tests for PubMed ESearch XML parsing."""

    SAMPLE_ESEARCH_XML = """<?xml version="1.0" encoding="utf-8"?>
    <eSearchResult>
        <Count>2</Count>
        <IdList>
            <Id>12345678</Id>
            <Id>87654321</Id>
        </IdList>
    </eSearchResult>"""

    @pytest.fixture
    def client(self) -> PubMedClient:
        return PubMedClient(http_client=None)  # type: ignore

    def test_parse_esearch_empty(self, client: PubMedClient) -> None:
        """Empty search results should return empty list."""
        import xml.etree.ElementTree as ET

        xml = """<eSearchResult><Count>0</Count><IdList/></eSearchResult>"""
        root = ET.fromstring(xml)
        id_list = root.find("IdList")
        pmids = [el.text for el in id_list.findall("Id") if el.text]
        assert pmids == []
