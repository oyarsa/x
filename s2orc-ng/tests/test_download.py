"""Unit tests for download.py."""

from typing import Any

import pytest

from download import (
    Author,
    AuthorId,
    CitationData,
    PaperId,
    PaperMetadata,
    compute_bibliographic_coupling,
    compute_co_citations,
    compute_stats,
    create_splits,
    parse_paper_metadata,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_papers() -> dict[PaperId, PaperMetadata]:
    """Sample papers for testing."""
    return {
        PaperId("p1"): PaperMetadata(
            paper_id=PaperId("p1"),
            title="Paper 1",
            abstract="Abstract 1",
            year=2022,
            venue="ACL",
            authors=[Author(author_id=AuthorId("a1"), name="Author 1")],
            citation_count=10,
            fields_of_study=["NLP"],
            url="https://example.com/p1",
            open_access_pdf="https://example.com/p1.pdf",
            pdf_source="S2",
        ),
        PaperId("p2"): PaperMetadata(
            paper_id=PaperId("p2"),
            title="Paper 2",
            abstract="Abstract 2",
            year=2023,
            venue="EMNLP",
            authors=[Author(author_id=AuthorId("a2"), name="Author 2")],
            citation_count=20,
            fields_of_study=["NLP", "ML"],
            url="https://example.com/p2",
            open_access_pdf=None,
            pdf_source=None,
        ),
        PaperId("p3"): PaperMetadata(
            paper_id=PaperId("p3"),
            title="Paper 3",
            abstract=None,
            year=2024,
            venue="ACL",
            authors=[],
            citation_count=5,
            fields_of_study=[],
            url="https://example.com/p3",
            open_access_pdf="https://example.com/p3.pdf",
            pdf_source="ArXiv",
        ),
        PaperId("p4"): PaperMetadata(
            paper_id=PaperId("p4"),
            title="Paper 4",
            abstract="Abstract 4",
            year=2025,
            venue="NAACL",
            authors=[Author(author_id=None, name="Anonymous")],
            citation_count=0,
            fields_of_study=["NLP"],
            url="https://example.com/p4",
            open_access_pdf=None,
            pdf_source=None,
        ),
    }


# ============================================================================
# Test parse_paper_metadata
# ============================================================================


class TestParsePaperMetadata:
    """Tests for parse_paper_metadata function."""

    def test_parses_complete_response(self) -> None:
        """Should parse a complete API response correctly."""
        response = {
            "paperId": "abc123",
            "title": "A Great Paper",
            "abstract": "This paper is about something important.",
            "year": 2024,
            "venue": "ACL",
            "authors": [
                {"authorId": "auth1", "name": "Alice Smith"},
                {"authorId": "auth2", "name": "Bob Jones"},
                {"authorId": None, "name": "Anonymous"},
            ],
            "citationCount": 42,
            "fieldsOfStudy": ["Computer Science", "NLP"],
            "url": "https://example.com/paper",
            "openAccessPdf": {"url": "https://example.com/paper.pdf"},
            "externalIds": {"ArXiv": "2401.12345", "DOI": "10.1234/test"},
        }

        paper = parse_paper_metadata(response)

        assert paper.paper_id == "abc123"
        assert paper.title == "A Great Paper"
        assert paper.abstract == "This paper is about something important."
        assert paper.year == 2024
        assert paper.venue == "ACL"
        assert paper.citation_count == 42
        assert paper.fields_of_study == ["Computer Science", "NLP"]
        assert paper.url == "https://example.com/paper"
        assert paper.open_access_pdf == "https://example.com/paper.pdf"
        assert paper.pdf_source == "S2"
        # Check authors
        assert len(paper.authors) == 3
        assert paper.authors[0].author_id == "auth1"
        assert paper.authors[0].name == "Alice Smith"
        assert paper.authors[2].author_id is None

    def test_handles_missing_fields(self) -> None:
        """Should handle missing optional fields gracefully."""
        paper = parse_paper_metadata({"paperId": "min123"})

        assert paper.paper_id == "min123"
        assert paper.title == ""
        assert paper.abstract is None
        assert paper.year is None
        assert paper.venue is None
        assert paper.authors == []
        assert paper.citation_count is None
        assert paper.fields_of_study == []
        assert paper.url == ""
        assert paper.open_access_pdf is None
        assert paper.pdf_source is None

    @pytest.mark.parametrize(
        ("response", "expected_url", "expected_source"),
        [
            # ArXiv fallback
            (
                {
                    "paperId": "x",
                    "openAccessPdf": None,
                    "externalIds": {"ArXiv": "2401.12345"},
                },
                "https://arxiv.org/pdf/2401.12345.pdf",
                "ArXiv",
            ),
            # ACL Anthology fallback
            (
                {
                    "paperId": "x",
                    "openAccessPdf": None,
                    "externalIds": {"DOI": "10.18653/v1/2024.acl-long.123"},
                },
                "https://aclanthology.org/2024.acl-long.123.pdf",
                "ACL",
            ),
            # Empty PDF URL treated as None, falls back to ArXiv
            (
                {
                    "paperId": "x",
                    "openAccessPdf": {"url": ""},
                    "externalIds": {"ArXiv": "2401.12345"},
                },
                "https://arxiv.org/pdf/2401.12345.pdf",
                "ArXiv",
            ),
            # No PDF available
            (
                {"paperId": "x", "openAccessPdf": None},
                None,
                None,
            ),
        ],
        ids=["arxiv_fallback", "acl_fallback", "empty_url_fallback", "no_pdf"],
    )
    def test_pdf_extraction(
        self,
        response: dict[str, Any],
        expected_url: str | None,
        expected_source: str | None,
    ) -> None:
        """Should extract PDF URL with appropriate fallbacks."""
        paper = parse_paper_metadata(response)
        assert paper.open_access_pdf == expected_url
        assert paper.pdf_source == expected_source


# ============================================================================
# Test compute_co_citations
# ============================================================================


class TestComputeCoCitations:
    """Tests for compute_co_citations function."""

    def test_finds_co_citation_pairs(self) -> None:
        """Should find papers that are cited together."""
        citations = {
            PaperId("p1"): [PaperId("c1"), PaperId("c2"), PaperId("c3")],
            PaperId("p2"): [PaperId("c1"), PaperId("c2")],
            PaperId("p3"): [PaperId("c1")],
        }

        result = compute_co_citations(citations, min_overlap=2)

        assert len(result) == 1
        pair = result[0]
        assert {pair.paper_1, pair.paper_2} == {PaperId("p1"), PaperId("p2")}
        assert pair.score == 2

    @pytest.mark.parametrize(
        ("min_overlap", "expected_count"),
        [(2, 1), (3, 0)],
        ids=["overlap_2_finds_pair", "overlap_3_no_pair"],
    )
    def test_respects_min_overlap(self, min_overlap: int, expected_count: int) -> None:
        """Should filter out pairs below min_overlap threshold."""
        citations = {
            PaperId("p1"): [PaperId("c1"), PaperId("c2"), PaperId("c3")],
            PaperId("p2"): [PaperId("c1"), PaperId("c2")],
        }
        result = compute_co_citations(citations, min_overlap=min_overlap)
        assert len(result) == expected_count

    def test_empty_citations(self) -> None:
        """Should handle empty citations dict."""
        result = compute_co_citations({}, min_overlap=2)
        assert result == []

    def test_no_overlap(self) -> None:
        """Should return empty list when no papers share citations."""
        citations = {
            PaperId("p1"): [PaperId("c1")],
            PaperId("p2"): [PaperId("c2")],
        }
        result = compute_co_citations(citations, min_overlap=1)
        assert result == []


# ============================================================================
# Test compute_bibliographic_coupling
# ============================================================================


class TestComputeBibliographicCoupling:
    """Tests for compute_bibliographic_coupling function."""

    def test_finds_coupled_papers(self) -> None:
        """Should find papers that share references."""
        references = {
            PaperId("p1"): [PaperId("r1"), PaperId("r2"), PaperId("r3")],
            PaperId("p2"): [PaperId("r1"), PaperId("r2")],
            PaperId("p3"): [PaperId("r4")],
        }

        result = compute_bibliographic_coupling(references, min_overlap=2)

        assert len(result) == 1
        pair = result[0]
        assert {pair.paper_1, pair.paper_2} == {PaperId("p1"), PaperId("p2")}
        assert pair.score == 2

    @pytest.mark.parametrize(
        ("min_overlap", "expected_count"),
        [(1, 1), (2, 0)],
        ids=["overlap_1_finds_pair", "overlap_2_no_pair"],
    )
    def test_respects_min_overlap(self, min_overlap: int, expected_count: int) -> None:
        """Should filter out pairs below min_overlap threshold."""
        references = {
            PaperId("p1"): [PaperId("r1"), PaperId("r2")],
            PaperId("p2"): [PaperId("r1")],
        }
        result = compute_bibliographic_coupling(references, min_overlap=min_overlap)
        assert len(result) == expected_count

    def test_skips_empty_references(self) -> None:
        """Should skip papers with no references."""
        references = {
            PaperId("p1"): [PaperId("r1"), PaperId("r2")],
            PaperId("p2"): [],
            PaperId("p3"): [PaperId("r1"), PaperId("r2")],
        }

        result = compute_bibliographic_coupling(references, min_overlap=2)

        assert len(result) == 1
        pair = result[0]
        assert {pair.paper_1, pair.paper_2} == {PaperId("p1"), PaperId("p3")}

    def test_empty_references(self) -> None:
        """Should handle empty references dict."""
        result = compute_bibliographic_coupling({}, min_overlap=2)
        assert result == []


# ============================================================================
# Test create_splits
# ============================================================================


class TestCreateSplits:
    """Tests for create_splits function."""

    def test_splits_by_year(self, sample_papers: dict[PaperId, PaperMetadata]) -> None:
        """Should split papers into train/dev/test by year."""
        splits = create_splits(
            sample_papers,
            train_years=(2022, 2023),
            dev_year=2024,
            test_year=2025,
        )

        assert PaperId("p1") in splits.train  # 2022
        assert PaperId("p2") in splits.train  # 2023
        assert PaperId("p3") in splits.dev  # 2024
        assert PaperId("p4") in splits.test  # 2025

    def test_excludes_papers_outside_range(self) -> None:
        """Should exclude papers that don't match any split criteria."""
        papers = {
            PaperId("p1"): PaperMetadata(
                paper_id=PaperId("p1"),
                title="Paper 1",
                abstract=None,
                year=2020,  # Outside all ranges
                venue="ACL",
                authors=[],
                citation_count=0,
                fields_of_study=[],
                url="",
                open_access_pdf=None,
            ),
        }

        splits = create_splits(
            papers, train_years=(2022, 2023), dev_year=2024, test_year=2025
        )

        assert splits.train == []
        assert splits.dev == []
        assert splits.test == []

    def test_skips_papers_without_year(self) -> None:
        """Should skip papers with year=None."""
        papers = {
            PaperId("p1"): PaperMetadata(
                paper_id=PaperId("p1"),
                title="Paper 1",
                abstract=None,
                year=None,
                venue="ACL",
                authors=[],
                citation_count=0,
                fields_of_study=[],
                url="",
                open_access_pdf=None,
            ),
        }

        splits = create_splits(
            papers, train_years=(2022, 2023), dev_year=2024, test_year=2025
        )

        assert splits.train == []
        assert splits.dev == []
        assert splits.test == []

    def test_empty_papers(self) -> None:
        """Should handle empty papers dict."""
        splits = create_splits(
            {}, train_years=(2022, 2023), dev_year=2024, test_year=2025
        )

        assert splits.train == []
        assert splits.dev == []
        assert splits.test == []


# ============================================================================
# Test compute_stats
# ============================================================================


class TestComputeStats:
    """Tests for compute_stats function."""

    def test_counts_papers(self, sample_papers: dict[PaperId, PaperMetadata]) -> None:
        """Should count papers correctly."""
        citation_data = CitationData(
            references={PaperId("p1"): [PaperId("r1"), PaperId("r2")]},
            citations={PaperId("p1"): [PaperId("c1")]},
        )
        stats = compute_stats(sample_papers, citation_data)

        assert stats.total_papers == 4
        assert stats.papers_with_abstract == 3  # p1, p2, p4
        assert stats.papers_with_pdf == 2  # p1, p3
        assert stats.papers_with_references == 1
        assert stats.total_references == 2
        assert stats.total_citations == 1

    def test_groups_by_year_and_venue(
        self, sample_papers: dict[PaperId, PaperMetadata]
    ) -> None:
        """Should group papers by year and venue."""
        citation_data = CitationData(references={}, citations={})
        stats = compute_stats(sample_papers, citation_data)

        assert stats.by_year == {2022: 1, 2023: 1, 2024: 1, 2025: 1}
        # ACL: 2, EMNLP: 1, NAACL: 1 - sorted by count descending
        assert next(iter(stats.by_venue.keys())) == "ACL"
        assert stats.by_venue["ACL"] == 2

    def test_empty_papers(self) -> None:
        """Should handle empty papers dict."""
        citation_data = CitationData(references={}, citations={})
        stats = compute_stats({}, citation_data)

        assert stats.total_papers == 0
        assert stats.papers_with_abstract == 0
        assert stats.by_year == {}
        assert stats.by_venue == {}
