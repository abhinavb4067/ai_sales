"""Multi-page website crawler for knowledge-base URL sources.

Master spec section 7 requirements this satisfies: crawl only permitted
public pages, respect robots.txt, reasonable crawl limits, deduplicate
URLs, same-origin only. Every fetch goes through
apps.knowledge.net_safety.safe_get, so SSRF protections (private IPs,
cloud metadata, disallowed schemes/ports, redirect/size limits) apply to
every page crawled, not just the first one.

Not implemented here (left for a later pass if needed): authenticated/
private pages (explicitly out of scope per the master spec — "Do not
crawl authenticated/private pages unless a specifically authorized
integration is designed for them"), and change-tracking across crawls
beyond the content checksum apps.knowledge.services already computes.
"""
import urllib.robotparser
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from apps.knowledge.net_safety import UnsafeURLError, safe_get

DEFAULT_MAX_PAGES = 20
MAX_PAGES_CEILING = 50  # hard cap regardless of what a business requests
MAX_TOTAL_CHARS = 2_000_000  # keep extraction + chunking bounded


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def _normalize(url: str) -> str:
    url, _ = urldefrag(url)  # strip #fragments — not distinct pages
    return url.rstrip("/")


def _load_robots_parser(start_url: str) -> urllib.robotparser.RobotFileParser:
    """Fetches robots.txt through the same SSRF-safe path as every other
    request here — deliberately not RobotFileParser.read(), which would
    use urllib directly and bypass safe_get's protections."""
    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = safe_get(robots_url)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            parser.allow_all = True
    except (UnsafeURLError, Exception):  # noqa: BLE001 — missing/unreachable robots.txt means "allow"
        parser.allow_all = True
    return parser


def _extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        links.append(_normalize(urljoin(base_url, href)))
    return links


def _page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def crawl_website(start_url: str, *, max_pages: int = DEFAULT_MAX_PAGES) -> str:
    """Breadth-first crawl starting from start_url, staying on the same
    origin, skipping URLs robots.txt disallows, deduplicating visited
    URLs, and stopping at max_pages (capped at MAX_PAGES_CEILING) or
    MAX_TOTAL_CHARS of extracted text — whichever comes first. Returns
    the concatenated text of every page visited, each prefixed with its
    source URL so citations/debugging can trace an answer back to a
    specific page.
    """
    max_pages = max(1, min(max_pages, MAX_PAGES_CEILING))
    start_url = _normalize(start_url)
    robots = _load_robots_parser(start_url)

    visited: set[str] = set()
    queue = [start_url]
    pages: list[str] = []
    total_chars = 0

    while queue and len(visited) < max_pages and total_chars < MAX_TOTAL_CHARS:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        if not robots.can_fetch("Ectama-KnowledgeIngestion/1.0", url):
            continue

        try:
            response = safe_get(url)
            response.raise_for_status()
        except Exception:  # noqa: BLE001 — a single bad page shouldn't abort the whole crawl
            continue

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            continue

        text = _page_text(response.text)
        if text:
            pages.append(f"--- Page: {url} ---\n{text}")
            total_chars += len(text)

        for link in _extract_links(url, response.text):
            if link not in visited and _same_origin(link, start_url):
                queue.append(link)

    return "\n\n".join(pages)
