"""Détection colonnes export paie Quadra/Cegid."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.modules.admin_import.application.rib_excel import (
    _match_alias,
    _normalize_header,
)

NIR_ALIASES = ("numero insee", "nir", "n° ss", "no ss", "numero securite sociale")
LAST_NAME_ALIASES = ("nom",)
FIRST_NAME_ALIASES = ("prenom", "prénom")
NOM_USAGE_ALIASES = ("nom marital",)
EMAIL_ALIASES = ("e-mail", "email", "mail", "courriel")
PHONE_ALIASES = ("tel", "tél", "telephone", "téléphone")
SERVICE_ALIASES = ("service",)
PAYMENT_ALIASES = ("paiement", "moyen de paiement", "mode paiement")
RIB_ALIASES = ("rib", "iban", "releve identite bancaire")
HANDICAP_ALIASES = ("handicape", "handicapé", "handicap")
ACTIVITY_PCT_ALIASES = ("% activite", "% activité", "pct activite")
STATUT_CADRE_ALIASES = ("categorie tds", "catégorie tds", "statut cadre")
HIRE_DATE_ALIASES = ("date d'entree", "date d'entrée", "date entree")
EXIT_DATE_ALIASES = ("date de sortie", "date sortie")
CDD_ALIASES = ("cdd",)
BASE_SALARY_ALIASES = ("salaire de base", "salaire base")
MONTHLY_HOURS_ALIASES = ("nbheuremois", "nb heure mois", "heures mois")
STREET_NUM_ALIASES = ("n°", "no", "numero")
BTQ_ALIASES = ("btq",)
STREET_ALIASES = ("voie", "rue")
ADDRESS_EXTRA_ALIASES = ("complement", "complément")
POSTAL_CODE_ALIASES = ("cp", "code postal")
CITY_ALIASES = ("ville",)
BIRTH_DATE_ALIASES = ("date naiss", "date naissance")
BIRTH_DEPT_ALIASES = ("dept naiss", "departement naissance")
BIRTH_CITY_ALIASES = ("commune naissance", "lieu naissance")
NATIONALITY_ALIASES = ("nationalite", "nationalité")
SEXE_ALIASES = ("sexe",)
PRIOR_SERVICE_DAYS_ALIASES = ("nb jour anc", "jours anciennete")
RESIDENCE_PERMIT_NUM_ALIASES = ("n° carte sejour", "carte sejour", "carte séjour")
RESIDENCE_PERMIT_FROM_ALIASES = ("date obt.", "date obtention")
RESIDENCE_PERMIT_TO_ALIASES = ("date expir.", "date expiration")
IDENTIFIANT_ALIASES = ("identifiant", "matricule")


def _match_header(header: str, aliases: Tuple[str, ...]) -> bool:
    norm = _normalize_header(header)
    if not norm:
        return False
    if norm in aliases:
        return True
    return any(alias in norm for alias in aliases if len(alias) >= 3)


def detect_payroll_export_column_mapping(headers: List[str]) -> Dict[str, str]:
    """Retourne mapping clé logique -> nom colonne source."""
    mapping: Dict[str, str] = {}

    def set_once(key: str, header: str, aliases: Tuple[str, ...]) -> None:
        if key in mapping:
            return
        if _match_header(header, aliases):
            mapping[key] = header

    for header in headers:
        if not header:
            continue
        set_once("nir", header, NIR_ALIASES)
        set_once("last_name", header, LAST_NAME_ALIASES)
        set_once("first_name", header, FIRST_NAME_ALIASES)
        set_once("nom_usage", header, NOM_USAGE_ALIASES)
        norm = _normalize_header(header)
        if "email" not in mapping and _match_header(header, EMAIL_ALIASES):
            if not (norm and "envoi" in norm and "mail" in norm):
                mapping["email"] = header
        set_once("phone", header, PHONE_ALIASES)
        set_once("service", header, SERVICE_ALIASES)
        set_once("payment_method", header, PAYMENT_ALIASES)
        set_once("rib", header, RIB_ALIASES)
        set_once("handicap", header, HANDICAP_ALIASES)
        set_once("activity_pct", header, ACTIVITY_PCT_ALIASES)
        set_once("statut_cadre", header, STATUT_CADRE_ALIASES)
        set_once("hire_date", header, HIRE_DATE_ALIASES)
        set_once("exit_date", header, EXIT_DATE_ALIASES)
        set_once("cdd", header, CDD_ALIASES)
        set_once("base_salary", header, BASE_SALARY_ALIASES)
        set_once("monthly_hours", header, MONTHLY_HOURS_ALIASES)
        set_once("street_num", header, STREET_NUM_ALIASES)
        set_once("btq", header, BTQ_ALIASES)
        set_once("street", header, STREET_ALIASES)
        set_once("address_extra", header, ADDRESS_EXTRA_ALIASES)
        set_once("postal_code", header, POSTAL_CODE_ALIASES)
        set_once("city", header, CITY_ALIASES)
        set_once("birth_date", header, BIRTH_DATE_ALIASES)
        set_once("birth_dept", header, BIRTH_DEPT_ALIASES)
        set_once("birth_city", header, BIRTH_CITY_ALIASES)
        set_once("nationality", header, NATIONALITY_ALIASES)
        set_once("sexe", header, SEXE_ALIASES)
        set_once("prior_service_days", header, PRIOR_SERVICE_DAYS_ALIASES)
        set_once("residence_permit_number", header, RESIDENCE_PERMIT_NUM_ALIASES)
        set_once("residence_permit_from", header, RESIDENCE_PERMIT_FROM_ALIASES)
        set_once("residence_permit_to", header, RESIDENCE_PERMIT_TO_ALIASES)
        set_once("identifiant", header, IDENTIFIANT_ALIASES)

    return mapping


def _score_header_row(headers: List[str]) -> int:
    mapping = detect_payroll_export_column_mapping(headers)
    score = len(mapping) * 2
    if "nir" in mapping:
        score += 10
    if "last_name" in mapping and "first_name" in mapping:
        score += 8
    non_empty = sum(1 for h in headers if h)
    if non_empty >= 5:
        score += 1
    return score


def find_payroll_export_header_row_index(
    raw_rows: List[List[str]], *, max_scan: int = 25
) -> int | None:
    best_idx: int | None = None
    best_score = 0
    for idx, row in enumerate(raw_rows[:max_scan]):
        headers = [str(c or "").strip() for c in row]
        score = _score_header_row(headers)
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_score < 6:
        return None
    return best_idx


def normalize_nir(raw: str) -> str:
    return re.sub(r"\s", "", (raw or "").strip())


def nir_match_key(raw: str) -> str:
    """Clé de rapprochement NIR (13 premiers chiffres — NIR en base vs export Quadra 15 chiffres)."""
    n = normalize_nir(raw)
    if len(n) >= 13:
        return n[:13]
    return n
