"""Safe in-memory extraction for supported offer upload formats."""

from pathlib import Path
from typing import BinaryIO

import pymupdf


DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_CHARACTERS = 50_000
MAX_PDF_PAGES = 100
READ_CHUNK_SIZE = 64 * 1024


class FileParseError(ValueError):
    """Raised when an uploaded offer cannot be safely read."""


def extract_offer_text(
    uploaded_file: BinaryIO,
    filename: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_characters: int = DEFAULT_MAX_CHARACTERS,
) -> str:
    """Extract text from a TXT or PDF upload without saving it to disk.

    The parser validates the extension, enforces a byte limit while reading,
    limits PDF page count and extracted text length, and rejects encrypted,
    corrupt, empty, or unsupported documents.
    """
    extension = Path(filename or "").suffix.lower()
    if extension not in {".txt", ".pdf"}:
        raise FileParseError("Unsupported file type. Upload a .txt or .pdf file.")

    if max_bytes <= 0 or max_characters <= 0:
        raise ValueError("File and text limits must be positive.")

    try:
        uploaded_file.seek(0)
        data = uploaded_file.read(max_bytes + 1)
    except (AttributeError, OSError) as exc:
        raise FileParseError("The uploaded file could not be read.") from exc

    if not data:
        raise FileParseError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise FileParseError("The uploaded file exceeds the 5 MB size limit.")

    if extension == ".txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise FileParseError(
                "The text file must use UTF-8 encoding."
            ) from exc
    else:
        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:
                if document.needs_pass:
                    raise FileParseError("Password-protected PDF files are not supported.")
                if document.page_count == 0:
                    raise FileParseError("The PDF does not contain any pages.")
                if document.page_count > MAX_PDF_PAGES:
                    raise FileParseError(
                        f"PDF files cannot exceed {MAX_PDF_PAGES} pages."
                    )

                extracted_parts = []
                character_count = 0
                for page in document:
                    remaining = max_characters - character_count
                    if remaining <= 0:
                        break
                    page_text = page.get_text("text")
                    extracted_parts.append(page_text[:remaining])
                    character_count += min(len(page_text), remaining)
                text = "\n".join(extracted_parts)
        except FileParseError:
            raise
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError, ValueError) as exc:
            raise FileParseError(
                "The PDF is corrupt, invalid, or could not be opened."
            ) from exc

    text = text.strip()
    if not text:
        raise FileParseError(
            "No selectable text was found. Scanned image-only PDFs are not supported."
        )
    if len(text) > max_characters:
        text = text[:max_characters]
    return text
