"""Tests unitaires — extraction d'URL signées Supabase Storage."""

from app.shared.infrastructure.storage_signed_url import extract_signed_url


def test_extract_signed_url_from_signed_url_key():
    assert extract_signed_url({"signedURL": "https://example.com/a.pdf"}) == "https://example.com/a.pdf"


def test_extract_signed_url_from_signed_url_camel_case():
    assert extract_signed_url({"signedUrl": "https://example.com/b.pdf"}) == "https://example.com/b.pdf"


def test_extract_signed_url_from_snake_case():
    assert extract_signed_url({"signed_url": "https://example.com/c.pdf"}) == "https://example.com/c.pdf"


def test_extract_signed_url_prefers_signed_url_key():
    assert (
        extract_signed_url({"signedURL": "https://a", "signedUrl": "https://b"})
        == "https://a"
    )


def test_extract_signed_url_from_plain_string():
    assert extract_signed_url("https://example.com/d.pdf") == "https://example.com/d.pdf"


def test_extract_signed_url_empty_and_none():
    assert extract_signed_url(None) is None
    assert extract_signed_url({}) is None
    assert extract_signed_url({"other": "x"}) is None
    assert extract_signed_url("   ") is None


class _ResponseWithData:
    def __init__(self, data):
        self.data = data


def test_extract_signed_url_from_response_object():
    assert (
        extract_signed_url(_ResponseWithData({"signedUrl": "https://example.com/e.pdf"}))
        == "https://example.com/e.pdf"
    )
