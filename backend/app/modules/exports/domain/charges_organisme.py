# Détection d'organisme à partir du libellé de cotisation (logique pure, sans dépendance infra).

ORGANISME_URSSAF = "URSSAF"
ORGANISME_RETRAITE = "RETRAITE"
ORGANISME_PREVOYANCE = "PREVOYANCE"
ORGANISME_MUTUELLE = "MUTUELLE"
ORGANISME_AUTRE = "AUTRE"

KNOWN_ORGANISMES = frozenset(
    {
        ORGANISME_URSSAF,
        ORGANISME_RETRAITE,
        ORGANISME_PREVOYANCE,
        ORGANISME_MUTUELLE,
        ORGANISME_AUTRE,
    }
)


def resolve_organisme(libelle: str) -> str:
    """Retourne l'organisme social associé au libellé de cotisation."""
    upper = (libelle or "").upper()
    if "URSSAF" in upper:
        return ORGANISME_URSSAF
    if "RETRAITE" in upper or "AGIRC" in upper or "ARRCO" in upper:
        return ORGANISME_RETRAITE
    if "PREVOYANCE" in upper:
        return ORGANISME_PREVOYANCE
    if "MUTUELLE" in upper:
        return ORGANISME_MUTUELLE
    return ORGANISME_AUTRE
