"""Unit tests for api.py."""

from typing import Any

import pytest

from api import extract_pdf_url


class TestExtractPdfUrl:
    """Tests for extract_pdf_url function."""

    @pytest.mark.parametrize(
        ("item", "expected_url", "expected_source"),
        [
            # S2 openAccessPdf
            (
                {"openAccessPdf": {"url": "https://example.com/paper.pdf"}},
                "https://example.com/paper.pdf",
                "S2",
            ),
            # ArXiv fallback
            (
                {"openAccessPdf": None, "externalIds": {"ArXiv": "2401.12345"}},
                "https://arxiv.org/pdf/2401.12345.pdf",
                "ArXiv",
            ),
            # ACL Anthology fallback
            (
                {
                    "openAccessPdf": None,
                    "externalIds": {"DOI": "10.18653/v1/2024.acl-long.123"},
                },
                "https://aclanthology.org/2024.acl-long.123.pdf",
                "ACL",
            ),
            # ACL Anthology - EMNLP format
            (
                {
                    "openAccessPdf": None,
                    "externalIds": {"DOI": "10.18653/v1/2023.emnlp-main.456"},
                },
                "https://aclanthology.org/2023.emnlp-main.456.pdf",
                "ACL",
            ),
            # ACL Anthology - old format
            (
                {"openAccessPdf": None, "externalIds": {"DOI": "10.18653/v1/P19-1001"}},
                "https://aclanthology.org/P19-1001.pdf",
                "ACL",
            ),
            # S2 preferred over ArXiv
            (
                {
                    "openAccessPdf": {"url": "https://s2.com/paper.pdf"},
                    "externalIds": {"ArXiv": "2401.12345"},
                },
                "https://s2.com/paper.pdf",
                "S2",
            ),
            # ArXiv preferred over ACL
            (
                {
                    "openAccessPdf": None,
                    "externalIds": {
                        "ArXiv": "2401.12345",
                        "DOI": "10.18653/v1/2024.acl-long.123",
                    },
                },
                "https://arxiv.org/pdf/2401.12345.pdf",
                "ArXiv",
            ),
            # Empty S2 URL falls back to ArXiv
            (
                {"openAccessPdf": {"url": ""}, "externalIds": {"ArXiv": "2401.12345"}},
                "https://arxiv.org/pdf/2401.12345.pdf",
                "ArXiv",
            ),
            # Non-ACL DOI ignored
            (
                {"openAccessPdf": None, "externalIds": {"DOI": "10.1234/other.paper"}},
                None,
                None,
            ),
            # Missing externalIds
            (
                {"openAccessPdf": None},
                None,
                None,
            ),
            # None externalIds
            (
                {"openAccessPdf": None, "externalIds": None},
                None,
                None,
            ),
            # Empty item
            (
                {},
                None,
                None,
            ),
            # Missing url key in openAccessPdf
            (
                {"openAccessPdf": {}},
                None,
                None,
            ),
        ],
        ids=[
            "s2_pdf",
            "arxiv_fallback",
            "acl_fallback",
            "acl_emnlp_format",
            "acl_old_format",
            "s2_over_arxiv",
            "arxiv_over_acl",
            "empty_url_fallback",
            "non_acl_doi_ignored",
            "missing_external_ids",
            "none_external_ids",
            "empty_item",
            "missing_url_key",
        ],
    )
    def test_extract_pdf_url(
        self,
        item: dict[str, Any],
        expected_url: str | None,
        expected_source: str | None,
    ) -> None:
        """Should extract PDF URL with appropriate fallbacks."""
        url, source = extract_pdf_url(item)
        assert url == expected_url
        assert source == expected_source
