"""
PDF / document context.

Drag a PDF onto the Clicky panel → its text is extracted and held as context
for the next question. *"Explain page 3 of my chemistry notes"* works because
the extracted text is appended to the system prompt.

Backend: pypdf (pure Python, no native deps). For .docx use python-docx.
For .txt / .md we just read the file. Anything else → plain bytes preview.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# Ceiling per attachment so we don't blow past LLM context windows.
MAX_CHARS_PER_DOC = 60_000


def extract_text(path: str | Path) -> str:
    """Best-effort text extraction. Returns empty string on failure."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    if p.stat().st_size > 25_000_000:
        raise ValueError("Document attachments must be smaller than 25 MB")
    suf = p.suffix.lower()

    if suf in (".txt", ".md", ".csv", ".log", ".py", ".js", ".ts",
               ".json", ".yaml", ".yml", ".html", ".xml", ".sql"):
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS_PER_DOC]
        except Exception:
            return ""

    if suf == ".pdf":
        try:
            from pypdf import PdfReader   # type: ignore
        except ImportError:
            return f"(install `pypdf` to read {p.name})"
        try:
            reader = PdfReader(str(p))
            chunks = []
            total = 0
            for i, page in enumerate(reader.pages):
                t = (page.extract_text() or "").strip()
                if not t:
                    from tutor_features.ocr import run_ocr
                    for embedded in page.images:
                        import io
                        image = embedded.image.convert("RGB")
                        image.thumbnail((2400, 2400))
                        buffer = io.BytesIO()
                        image.save(buffer, "PNG")
                        t += run_ocr(buffer.getvalue()) + "\n"
                    if not t.strip():
                        t = "[This scanned page could not be read. Enable/install OCR or attach an image of it.]"
                chunk = f"\n[Page {i + 1}]\n{t}"
                chunks.append(chunk)
                total += len(chunk)
                if total >= MAX_CHARS_PER_DOC:
                    break
            return "".join(chunks)[:MAX_CHARS_PER_DOC]
        except Exception as e:
            raise ValueError(f"Could not read PDF: {e}") from e

    if suf in (".docx",):
        try:
            from docx import Document   # type: ignore
        except ImportError:
            return f"(install `python-docx` to read {p.name})"
        try:
            import zipfile
            with zipfile.ZipFile(p) as archive:
                if sum(item.file_size for item in archive.infolist())>30_000_000:
                    raise ValueError('Document expands beyond 30 MB')
            doc = Document(str(p))
            text = "\n".join(par.text for par in doc.paragraphs if par.text.strip())
            text += "\n" + "\n".join(" | ".join(cell.text for cell in row.cells) for table in doc.tables for row in table.rows)
            return text[:MAX_CHARS_PER_DOC]
        except Exception as e:
            raise ValueError(f"Could not read DOCX: {e}") from e

    if suf == ".xlsx":
        return _xlsx_text(p)
    return ""


def _xlsx_text(path):
    import zipfile
    import xml.etree.ElementTree as ET
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > 30_000_000:
            raise ValueError("Spreadsheet expands beyond 30 MB")
        def read(name):
            content = archive.read(name)
            if b"<!DOCTYPE" in content:
                raise ValueError("Document type declarations are not supported")
            return ET.fromstring(content)
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(si.itertext()) for si in read("xl/sharedStrings.xml").findall("s:si", ns)]
        lines, total = [], 0
        for name in sorted(archive.namelist()):
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            lines.append("[" + name + "]")
            for cell in read(name).findall(".//s:c", ns)[:10000]:
                value = cell.findtext("s:v", "", ns)
                if cell.get("t") == "s":
                    value = strings[int(value)] if value.isdigit() and int(value) < len(strings) else ""
                elif cell.get("t") == "inlineStr":
                    node = cell.find("s:is", ns)
                    value = "".join(node.itertext()) if node is not None else ""
                formula = cell.findtext("s:f", "", ns)
                line = f"{cell.get('r')}: {value}" + (f" (formula: {formula})" if formula else "")
                lines.append(line)
                total += len(line)
                if total >= MAX_CHARS_PER_DOC:
                    return "\n".join(lines)[:MAX_CHARS_PER_DOC]
        return "\n".join(lines)


def format_for_prompt(filename: str, text: str) -> str:
    """Wrap extracted text so the LLM knows it's a user-attached document."""
    if not text.strip():
        return ""
    return (
        f"\n\n[USER-ATTACHED DOCUMENT: {filename}]\n"
        f"--- begin document ---\n{text}\n--- end document ---\n"
        "When the user asks about 'this PDF' / 'my notes' / 'page X', refer to "
        "the document above. Cite page numbers when present."
    )
