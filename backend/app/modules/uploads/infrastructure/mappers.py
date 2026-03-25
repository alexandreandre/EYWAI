"""
Mappers pour le module uploads.

Utilitaires d'extraction du chemin storage depuis l'URL publique (règle de format legacy).
Comportement identique à api/routers/uploads.py (part après '/logos/').
"""


def storage_path_from_logo_url(logo_url: str | None) -> str | None:
    """
    Extrait le chemin dans le bucket à partir de l'URL publique.
    Format attendu : .../logos/<path> → retourne 'logos/<path>' pour remove().
    """
    if not logo_url or "/logos/" not in logo_url:
        return None
    return "logos/" + logo_url.split("/logos/")[1]
