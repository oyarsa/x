"""Semantic Scholar API client and shared utilities."""

import asyncio
from typing import Any, Self

import httpx
from rich.console import Console

console = Console()


def extract_pdf_url(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract PDF URL from API response item with fallbacks.

    Tries in order:
    1. Semantic Scholar openAccessPdf
    2. ArXiv via externalIds
    3. ACL Anthology via DOI

    Args:
        item: Paper data from Semantic Scholar API

    Returns:
        Tuple of (pdf_url, pdf_source) where pdf_source is "S2", "ArXiv", "ACL", or None
    """
    # Try Semantic Scholar's openAccessPdf first
    pdf_info = item.get("openAccessPdf")
    pdf_url = pdf_info.get("url") if pdf_info else None
    if pdf_url == "":
        pdf_url = None

    pdf_source: str | None = None
    if pdf_url:
        pdf_source = "S2"
    else:
        # Fall back to ArXiv or ACL Anthology
        external_ids: dict[str, Any] = item.get("externalIds") or {}
        if arxiv_id := external_ids.get("ArXiv"):
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            pdf_source = "ArXiv"
        elif (doi := external_ids.get("DOI")) and doi.startswith("10.18653/v1/"):
            # ACL Anthology DOIs: 10.18653/v1/2024.acl-long.123
            acl_id = doi.removeprefix("10.18653/v1/")
            pdf_url = f"https://aclanthology.org/{acl_id}.pdf"
            pdf_source = "ACL"

    return pdf_url, pdf_source


class SemanticScholarAPI:
    """Async client for Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    DEFAULT_RATE_LIMIT = 1.0  # Seconds between requests (with API key)

    def __init__(
        self,
        api_key: str,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the API client.

        Args:
            api_key: Semantic Scholar API key
            rate_limit: Minimum seconds between requests
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.headers = {"x-api-key": api_key}
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0

    async def __aenter__(self) -> Self:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rate_limit_wait(self) -> None:
        """Ensure minimum time between requests."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit:
                await asyncio.sleep(self.rate_limit - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Make a request with retry logic for rate limits.

        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            max_retries: Maximum retry attempts for rate limiting

        Returns:
            JSON response as dictionary

        Raises:
            RuntimeError: If client not initialized or max retries exceeded
        """
        if self._client is None:
            raise RuntimeError("API client not initialized. Use 'async with' context.")

        for attempt in range(max_retries):
            await self._rate_limit_wait()
            try:
                response = await self._client.request(method, url, params=params)
                if response.status_code == 429:
                    wait_time = 60 * (attempt + 1)
                    console.print(
                        f"[yellow]Rate limited, waiting {wait_time}s...[/yellow]"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 60 * (attempt + 1)
                    console.print(
                        f"[yellow]Rate limited, waiting {wait_time}s...[/yellow]"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise
        raise RuntimeError(f"Max retries exceeded for {url}")

    async def search_papers_bulk(
        self,
        venue: str,
        year: str | None = None,
        token: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search for papers using the bulk API.

        Args:
            venue: Venue name(s) to filter by (comma-separated)
            year: Year or year range (e.g., "2024" or "2020-2025")
            token: Continuation token for pagination
            fields: List of fields to return

        Returns:
            API response with 'data', 'total', and optional 'token'
        """
        if fields is None:
            fields = [
                "paperId",
                "title",
                "year",
                "venue",
                "citationCount",
                "fieldsOfStudy",
                "url",
                "openAccessPdf",
                "externalIds",
            ]

        params = {
            "venue": venue,
            "fields": ",".join(fields),
        }

        if year:
            params["year"] = year
        if token:
            params["token"] = token

        return await self._request_with_retry(
            "GET", f"{self.BASE_URL}/paper/search/bulk", params=params
        )

    async def get_paper_references(
        self,
        paper_id: str,
        limit: int = 1000,
    ) -> list[str]:
        """Get references for a paper (papers this paper cites).

        Args:
            paper_id: Semantic Scholar paper ID
            limit: Maximum references to fetch

        Returns:
            List of cited paper IDs
        """
        references: list[str] = []
        offset = 0

        while True:
            params = {
                "fields": "paperId",
                "limit": str(min(limit, 1000)),
                "offset": str(offset),
            }
            try:
                result = await self._request_with_retry(
                    "GET",
                    f"{self.BASE_URL}/paper/{paper_id}/references",
                    params=params,
                )
                data = result.get("data", [])
                for item in data:
                    cited = item.get("citedPaper", {})
                    if cited and cited.get("paperId"):
                        references.append(cited["paperId"])

                if len(data) < 1000:
                    break
                offset += len(data)
                if offset >= limit:
                    break
            except Exception:
                break

        return references

    async def get_paper_citations(
        self,
        paper_id: str,
        limit: int = 1000,
    ) -> list[str]:
        """Get citations for a paper (papers that cite this paper).

        Args:
            paper_id: Semantic Scholar paper ID
            limit: Maximum citations to fetch

        Returns:
            List of citing paper IDs
        """
        citations: list[str] = []
        offset = 0

        while True:
            params = {
                "fields": "paperId",
                "limit": str(min(limit, 1000)),
                "offset": str(offset),
            }
            try:
                result = await self._request_with_retry(
                    "GET",
                    f"{self.BASE_URL}/paper/{paper_id}/citations",
                    params=params,
                )
                data = result.get("data", [])
                for item in data:
                    citing = item.get("citingPaper", {})
                    if citing and citing.get("paperId"):
                        citations.append(citing["paperId"])

                if len(data) < 1000:
                    break
                offset += len(data)
                if offset >= limit:
                    break
            except Exception:
                break

        return citations
