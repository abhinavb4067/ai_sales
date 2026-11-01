"""Text extraction for uploaded documents. One function per source type —
adding a new supported file format later means adding one function here
and one line in EXTRACTORS, nothing else in the ingestion pipeline changes.
"""
import io


def extract_pdf(file_obj) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_obj)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def extract_docx(file_obj) -> str:
    import docx

    document = docx.Document(file_obj)
    return "\n".join(p.text for p in document.paragraphs)


def extract_txt(file_obj) -> str:
    raw = file_obj.read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore")
    return raw


def extract_csv(file_obj) -> str:
    import csv

    raw = file_obj.read()
    text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
    reader = csv.reader(io.StringIO(text))
    rows = [", ".join(row) for row in reader]
    return "\n".join(rows)


def extract_url(url: str, *, max_pages: int = 20) -> str:
    """Crawls up to max_pages same-origin pages starting from `url`,
    respecting robots.txt (apps.knowledge.crawler.crawl_website) — a
    single-page fetch is just max_pages=1, not a separate code path."""
    from apps.knowledge.crawler import crawl_website

    return crawl_website(url, max_pages=max_pages)


def extract_api_source(url: str, *, headers: dict | None = None) -> str:
    """Fetches a configured, business-supplied REST API endpoint and
    flattens the response into retrievable text. JSON responses are
    pretty-printed (field names and values both become searchable text);
    anything else is treated as plain text. No AI-generated request is
    ever made here — the endpoint/headers are configured once by the
    business, not invented per-query (see SECURITY section 8 of the
    master spec: never let the AI invent arbitrary URLs)."""
    import json

    from apps.knowledge.net_safety import safe_get

    response = safe_get(url, headers=headers)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        return json.dumps(response.json(), indent=2)
    return response.text


EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
    "csv": extract_csv,
}


def extract_database_source(document) -> str:
    import json

    from apps.knowledge.db_source import fetch_rows_as_text

    config = json.loads(document.external_db_credentials or "{}")
    return fetch_rows_as_text(config)


def extract_text_for_document(document) -> str:
    source_type = document.source_type
    if source_type == "url":
        max_pages = (document.source_config or {}).get("max_pages", 20)
        return extract_url(document.source_url, max_pages=max_pages)
    if source_type == "api":
        return extract_api_source(document.source_url, headers=(document.source_config or {}).get("headers"))
    if source_type == "database":
        return extract_database_source(document)

    extractor = EXTRACTORS.get(source_type)
    if extractor is None:
        raise ValueError(f"No extractor registered for source_type={source_type!r}")

    with document.file.open("rb") as file_obj:
        return extractor(file_obj)
