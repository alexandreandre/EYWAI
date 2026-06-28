"""
Règles métier pures du module employees.

Aucune dépendance FastAPI, DB ou HTTP. Utilisées par l'application.
"""

from typing import Any, Dict, List

# Comportement identique au router legacy (employment_status par défaut, etc.)

DEFAULT_EMPLOYMENT_STATUS = "actif"
DEFAULT_RESIDENCE_PERMIT_SUBJECT = False
DSN_IMPORT_PLACEHOLDER_EMAIL_SUFFIX = ".dsn-import.local"
DSN_IMPORT_AUTH_EMAIL_DOMAIN = "dsn-import.eywai.fr"
DUREE_LEGALE_HEBDO = 35.0


def normalize_temps_travail_fields(
    is_temps_partiel: bool | None,
    duree_hebdomadaire: float | None,
) -> tuple[bool, float]:
    """Réconcilie le booléen temps partiel et la durée hebdomadaire contractuelle.

    La durée hebdo (< 35 h) fait foi pour marquer un temps partiel.
    Si le booléen est explicite mais la durée reste à 35 h (DSN incomplète),
    on conserve le flag pour relecture RH sans le forcer à faux.
    """
    duree = float(duree_hebdomadaire if duree_hebdomadaire is not None else DUREE_LEGALE_HEBDO)
    if duree <= 0:
        duree = DUREE_LEGALE_HEBDO

    if duree < DUREE_LEGALE_HEBDO - 0.01:
        return True, round(duree, 2)

    if is_temps_partiel is True:
        return True, round(duree, 2)

    return False, round(duree, 2)


def is_temps_travail_incoherent(
    is_temps_partiel: bool | None,
    duree_hebdomadaire: float | None,
) -> bool:
    """True si temps partiel déclaré mais durée hebdo plein temps (quotité DSN absente)."""
    if not is_temps_partiel:
        return False
    duree = float(duree_hebdomadaire if duree_hebdomadaire is not None else DUREE_LEGALE_HEBDO)
    return duree >= DUREE_LEGALE_HEBDO - 0.01


def is_dsn_import_placeholder_email(email: str | None) -> bool:
    """True si l'email est le placeholder technique généré à l'import DSN."""
    if not email:
        return False
    value = str(email).strip().lower()
    return value.endswith(DSN_IMPORT_PLACEHOLDER_EMAIL_SUFFIX) or value.endswith(
        f"@{DSN_IMPORT_AUTH_EMAIL_DOMAIN}"
    )


def build_dsn_import_auth_email(seed: str) -> str:
    """Email technique valide côté Auth pour comptes issus d'une DSN sans email exploitable."""
    cleaned = "".join(ch for ch in str(seed or "") if ch.isalnum()).lower()
    if not cleaned:
        cleaned = "employee"
    return f"import.{cleaned}@{DSN_IMPORT_AUTH_EMAIL_DOMAIN}"


def build_employee_folder_name(
    normalized_last_name: str, normalized_first_name: str
) -> str:
    """
    Construit le nom de dossier employé à partir des noms normalisés.
    Comportement legacy : "{LAST_NAME}_{First_Name}" (ex. DUPONT_Jean).
    """
    return f"{normalized_last_name}_{normalized_first_name}"


def default_company_data_fallback() -> Dict[str, Any]:
    """Données entreprise par défaut si lecture BDD échoue (comportement legacy)."""
    return {
        "company_name": "Entreprise",
        "siret": "",
        "email": "",
    }


def normalize_collaborator_name_part(name: str) -> str:
    """Normalise une partie de nom pour l'identifiant (sans accents, minuscules)."""
    from app.shared.utils import remove_accents

    normalized = remove_accents(str(name or "").strip()).lower()
    normalized = normalized.replace(" ", "_").replace("'", "").replace("-", "_")
    slug = "".join(c for c in normalized if c.isalnum() or c in "._")
    slug = slug.strip("._")
    return slug or "x"


def build_collaborator_username_base(first_name: str, last_name: str) -> str:
    """Identifiant canonique : prenom.nom (ex. jean.dupont, samir.boufrida)."""
    first = normalize_collaborator_name_part(first_name)
    last = normalize_collaborator_name_part(last_name)
    if first == "x" and last == "x":
        return "collaborateur"
    return f"{first}.{last}"


def is_import_style_username(username: str | None) -> bool:
    """True si l'identifiant provient d'un placeholder d'import DSN."""
    if not username:
        return False
    return str(username).strip().lower().startswith("import.")


def resolve_unique_collaborator_username(
    base: str,
    taken_usernames: set[str],
    *,
    max_numeric_suffix: int = 99,
) -> str:
    """
    Retourne un identifiant disponible à partir de la base prenom.nom.

    Stratégie : base → base2 → base3 … → base.{hex} si épuisement.
    """
    import secrets

    normalized_base = base.strip().lower()
    taken = {str(u).strip().lower() for u in taken_usernames if u}

    if normalized_base not in taken:
        return normalized_base

    for suffix in range(2, max_numeric_suffix + 2):
        candidate = f"{normalized_base}{suffix}"
        if candidate not in taken:
            return candidate

    while True:
        candidate = f"{normalized_base}.{secrets.token_hex(2)}"
        if candidate not in taken:
            return candidate


def derive_collaborator_username(
    first_name: str,
    last_name: str,
    email: str | None = None,
    existing: str | None = None,
) -> str:
    """
    Identifiant de connexion : toujours prenom.nom (sans vérification d'unicité).

    Préférer ``allocate_collaborator_username`` à la création en base.
    """
    _ = email  # conservé pour compatibilité d'appel — l'email n'influence plus l'identifiant
    if existing and str(existing).strip() and not is_import_style_username(existing):
        return str(existing).strip().lower()
    return build_collaborator_username_base(first_name, last_name)


__all__: List[str] = [
    "DEFAULT_EMPLOYMENT_STATUS",
    "DEFAULT_RESIDENCE_PERMIT_SUBJECT",
    "DUREE_LEGALE_HEBDO",
    "DSN_IMPORT_PLACEHOLDER_EMAIL_SUFFIX",
    "is_temps_travail_incoherent",
    "normalize_temps_travail_fields",
    "build_collaborator_username_base",
    "build_employee_folder_name",
    "default_company_data_fallback",
    "derive_collaborator_username",
    "is_dsn_import_placeholder_email",
    "is_import_style_username",
    "normalize_collaborator_name_part",
    "resolve_unique_collaborator_username",
]
