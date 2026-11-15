"""Fetch one source URL: https only, timeout, size limit enforced while streaming."""

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from price_watch.config import LIMITS

USER_AGENT = "price-watch/0.1 (personal price checker)"
MAX_REDIRECTS = 5
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class FetchError(Exception):
    """The page could not be fetched (network, status, bad scheme)."""


class PageTooLargeError(FetchError):
    """The response body went over the byte limit."""


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    content_type: str
    body: str


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=LIMITS.fetch_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        transport=transport,
    )


def require_https(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise FetchError(f"only absolute https URLs are fetched: {url!r}")


def read_limited_body(response: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise PageTooLargeError(f"response is over {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_url(
    client: httpx.Client, url: str, max_bytes: int = LIMITS.max_response_bytes
) -> FetchedPage:
    """Fetch a page. Redirects are followed by hand so every hop stays on https."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        require_https(current)
        try:
            with client.stream("GET", current) as response:
                client.cookies.clear()  # no cookies, ever
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError(f"redirect without a location from {current!r}")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise FetchError(f"status {response.status_code} from {current!r}")
                declared = response.headers.get("content-length")
                if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                    raise PageTooLargeError(f"response is over {max_bytes} bytes")
                raw = read_limited_body(response, max_bytes)
                content_type = response.headers.get("content-type", "")
                encoding = response.charset_encoding or "utf-8"
        except httpx.HTTPError as error:
            raise FetchError(f"request failed for {current!r}: {type(error).__name__}") from error
        return FetchedPage(url=url, content_type=content_type, body=raw.decode(encoding, "replace"))
    raise FetchError(f"too many redirects from {url!r}")
