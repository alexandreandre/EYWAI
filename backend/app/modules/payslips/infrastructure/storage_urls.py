"""URLs signées Supabase pour les PDF bulletins (téléchargement vs aperçu inline)."""

from __future__ import annotations

from app.core.database import supabase


def _signed_url_map(paths: list[str], expires: int, *, download: bool) -> dict[str, str]:
    if not paths:
        return {}
    signed = supabase.storage.from_("payslips").create_signed_urls(
        paths, expires, options={"download": download}
    )
    if isinstance(signed, dict) and signed.get("error"):
        raise RuntimeError(signed.get("message", "Storage error"))
    return {
        path: item["signedURL"]
        for path, item in zip(paths, signed)
        if item.get("signedURL")
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
    return (
        download_map.get(storage_path, ""),
        preview_map.get(storage_path, ""),
    )
