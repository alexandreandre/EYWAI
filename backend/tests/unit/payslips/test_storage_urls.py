"""Tests unitaires — URLs signées bulletins (aperçu vs téléchargement)."""

from unittest.mock import MagicMock, patch

from app.modules.payslips.infrastructure.storage_urls import (
    create_payslip_signed_urls,
    create_payslip_url_maps,
)


@patch("app.modules.payslips.infrastructure.storage_urls.supabase")
def test_create_payslip_url_maps_returns_download_and_preview(mock_supabase):
    bucket = MagicMock()
    mock_supabase.storage.from_.return_value = bucket
    bucket.create_signed_urls.side_effect = [
        [{"signedURL": "https://dl.example/a.pdf"}],
        [{"signedURL": "https://preview.example/a.pdf"}],
    ]

    download_map, preview_map = create_payslip_url_maps(["co/2025/01.pdf"])

    assert download_map == {"co/2025/01.pdf": "https://dl.example/a.pdf"}
    assert preview_map == {"co/2025/01.pdf": "https://preview.example/a.pdf"}
    assert bucket.create_signed_urls.call_args_list[0].kwargs["options"] == {"download": True}
    assert bucket.create_signed_urls.call_args_list[1].kwargs["options"] == {"download": False}


@patch("app.modules.payslips.infrastructure.storage_urls.create_payslip_url_maps")
def test_create_payslip_signed_urls_delegates_to_maps(mock_maps):
    mock_maps.return_value = (
        {"path/a.pdf": "https://dl.example/a.pdf"},
        {"path/a.pdf": "https://preview.example/a.pdf"},
    )

    download_url, preview_url = create_payslip_signed_urls("path/a.pdf")

    assert download_url == "https://dl.example/a.pdf"
    assert preview_url == "https://preview.example/a.pdf"


@patch("app.modules.payslips.infrastructure.storage_urls.create_payslip_url_maps")
def test_create_payslip_signed_urls_falls_back_to_download_when_preview_missing(mock_maps):
    mock_maps.return_value = (
        {"path/a.pdf": "https://dl.example/a.pdf"},
        {},
    )

    download_url, preview_url = create_payslip_signed_urls("path/a.pdf")

    assert download_url == "https://dl.example/a.pdf"
    assert preview_url == "https://dl.example/a.pdf"


def test_preview_url_with_download_fallback():
    from app.modules.payslips.infrastructure.storage_urls import preview_url_with_download_fallback

    preview_map = {"x.pdf": "https://preview.example/x.pdf"}
    download_map = {"x.pdf": "https://dl.example/x.pdf"}

    assert (
        preview_url_with_download_fallback(preview_map, download_map, "x.pdf")
        == "https://preview.example/x.pdf"
    )
    assert (
        preview_url_with_download_fallback({}, download_map, "x.pdf")
        == "https://dl.example/x.pdf"
    )
    assert preview_url_with_download_fallback({}, {}, "missing.pdf") == ""
