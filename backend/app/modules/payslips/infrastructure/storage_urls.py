"""URLs signées Supabase pour les PDF bulletins (téléchargement vs aperçu inline)."""

from __future__ import annotations

from app.core.database import supabase
from app.shared.infrastructure.storage_signed_url import extract_signed_url


def _signed_url_map(paths: list[str], expires: int, *, download: bool) -> dict[str, str]:
    if not paths:
        return {}
    signed = supabase.storage.from_("payslips").create_signed_urls(
        paths, expires, options={"download": download}
    )
    if isinstance(signed, dict) and signed.get("error"):
        raise RuntimeError(signed.get("message", "Storage error"))
    items = signed if isinstance(signed, list) else []
    return {
        path: url
        for path, item in zip(paths, items)
        if (url := extract_signed_url(item))
    }


def create_payslip_url_maps(
    paths: list[str],
    expires: int = 3600,
) -> tuple[dict[str, str], dict[str, str]]:
    """Retourne (download_urls, preview_urls) indexés par chemin storage."""
    download_map = _signed_url_map(paths, expires, download=True)
    preview_map = _signed_url_map(paths, expires, download=False)
    return download_map, preview_map


def create_payslip_signed_urls(
    storage_path: str,
    expires: int = 3600,
) -> tuple[str, str]:
    """Retourne (download_url, preview_url) pour un seul bulletin."""
    download_map, preview_map = create_payslip_url_maps([storage_path], expires)
    download_url = download_map.get(storage_path, "")
    preview_url = preview_map.get(storage_path) or download_url
    return download_url, preview_url


def preview_url_with_download_fallback(
    preview_map: dict[str, str],
    download_map: dict[str, str],
    storage_path: str,
) -> str:
    """URL d'aperçu inline, avec repli sur l'URL de téléchargement si besoin."""
    return preview_map.get(storage_path) or download_map.get(storage_path, "")
