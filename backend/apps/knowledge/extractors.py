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


def extract_url(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, timeout=15, headers={"User-Agent": "AI-Sales-Support-Agent/1.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
    "csv": extract_csv,
}


def extract_text_for_document(document) -> str:
    source_type = document.source_type
    if source_type == "url":
        return extract_url(document.source_url)

    extractor = EXTRACTORS.get(source_type)
    if extractor is None:
        raise ValueError(f"No extractor registered for source_type={source_type!r}")

    with document.file.open("rb") as file_obj:
        return extractor(file_obj)
