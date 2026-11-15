"""Reduce a fetched page to the text sent to the AI."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from price_watch.config import LIMITS
from price_watch.fetch import FetchedPage

DROPPED_TAGS = ("script", "style", "noscript", "nav", "template", "svg")
PASS_THROUGH_MARKERS = ("json", "xml", "rss", "atom")
BLANK_LINES = re.compile(r"\n\s*\n+")


def is_pass_through(content_type: str) -> bool:
    lowered = content_type.lower()
    return any(marker in lowered for marker in PASS_THROUGH_MARKERS)


def is_html(page: FetchedPage) -> bool:
    return "html" in page.content_type.lower() or (
        not page.content_type and page.body.lstrip()[:15].lower().startswith(("<!doctype", "<html"))
    )


def html_to_text(html: str, base_url: str) -> str:
    """Visible text with links kept as `text (url)`; scripts, styles and navigation dropped."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(DROPPED_TAGS):
        tag.decompose()
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if isinstance(href, str) and not href.startswith(("#", "javascript:", "mailto:")):
            link.append(f" ({urljoin(base_url, href)})")
    text = soup.get_text("\n", strip=True)
    return BLANK_LINES.sub("\n", text)


def trim_page(page: FetchedPage, max_characters: int = LIMITS.max_page_characters) -> str | None:
    """Return the page text cut at the limit, or None when nothing usable is left."""
    if is_pass_through(page.content_type):
        text = page.body.strip()
    elif is_html(page):
        text = html_to_text(page.body, page.url).strip()
    else:
        return None
    return text[:max_characters] or None
