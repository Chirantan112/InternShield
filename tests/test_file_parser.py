"""Tests for bounded in-memory TXT and PDF extraction."""

from io import BytesIO

import fitz
import pytest

from internshield.services.file_parser import FileParseError, extract_offer_text


def make_pdf(text="A software internship offer"):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_extracts_utf8_text_file():
    result = extract_offer_text(
        BytesIO("Internship offer – engineer".encode("utf-8")),
        "offer.txt",
    )
    assert "Internship offer" in result


def test_extracts_text_from_pdf():
    result = extract_offer_text(BytesIO(make_pdf()), "offer.pdf")
    assert "software internship offer" in result


@pytest.mark.parametrize("filename", ["offer.exe", "photo.jpg", "unknown"])
def test_rejects_unsupported_extensions(filename):
    with pytest.raises(FileParseError, match="Unsupported"):
        extract_offer_text(BytesIO(b"data"), filename)


def test_rejects_empty_file():
    with pytest.raises(FileParseError, match="empty"):
        extract_offer_text(BytesIO(b""), "empty.txt")


def test_rejects_oversized_file():
    with pytest.raises(FileParseError, match="exceeds"):
        extract_offer_text(BytesIO(b"12345"), "large.txt", max_bytes=4)


def test_rejects_invalid_utf8_text():
    with pytest.raises(FileParseError, match="UTF-8"):
        extract_offer_text(BytesIO(b"\xff\xfe"), "bad.txt")


def test_rejects_corrupt_pdf():
    with pytest.raises(FileParseError, match="corrupt"):
        extract_offer_text(BytesIO(b"not a pdf"), "bad.pdf")


def test_rejects_image_only_or_textless_pdf():
    document = fitz.open()
    document.new_page()
    data = document.tobytes()
    document.close()
    with pytest.raises(FileParseError, match="No selectable text"):
        extract_offer_text(BytesIO(data), "blank.pdf")


def test_caps_extracted_characters():
    result = extract_offer_text(
        BytesIO(b"0123456789"),
        "short.txt",
        max_characters=5,
    )
    assert result == "01234"
