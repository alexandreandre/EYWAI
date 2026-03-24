"""
Règles métier pures du domaine contract_parser.

Sans I/O : uniquement décisions sur les données.
Aucune dépendance FastAPI ni détail d'infrastructure.
"""


def is_scanned_pdf(text: str) -> bool:
    """
    Détermine si un PDF est probablement scanné en analysant le texte extrait.
    Un PDF scanné aura très peu de texte extractible ou un ratio alphanumérique faible.
    """
    if not text:
        return True
    alphanumeric_count = sum(c.isalnum() for c in text)
    if alphanumeric_count < 50:
        return True
    if len(text) > 0 and (alphanumeric_count / len(text)) < 0.3:
        return True
    return False
