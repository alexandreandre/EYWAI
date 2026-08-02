"""Parse lignes export paie Quadra → champs EYWAI."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.modules.admin_import.application.payroll_export_mapping import (
    find_payroll_export_header_row_index,
    normalize_nir,
)
from app.modules.admin_import.application.payroll_export_preview import (
    enrich_payroll_export_preview,
)
from app.modules.admin_import.application.rib_excel import (
    TabularSheet,
    _rows_to_sheet,
    row_value,
)
from app.modules.admin_import.application.rib_parser import (
    build_coordonnees_bancaires,
    parse_rib_cell,
)
from app.shared.utils.xlsx_safe import iter_sheet_rows

DSN_PLACEHOLDER_SUFFIX = ".dsn-import.local"


def read_payroll_export_file(content: bytes, filename: str) -> TabularSheet:
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        raw_rows = _read_csv_raw(content)
    elif lower.endswith((".xlsx", ".xls")):
        raw_rows = iter_sheet_rows(content)
    else:
        raise ValueError("Format non supporté. Utilisez un fichier Excel (.xlsx) ou CSV.")

    if not raw_rows:
        return TabularSheet()

    header_idx = find_payroll_export_header_row_index(raw_rows)
    if header_idx is None:
        header_idx = 0
    return _rows_to_sheet(raw_rows, header_idx)


def _read_csv_raw(content: bytes) -> List[List[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


def parse_french_date(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date().isoformat()
        except ValueError:
            continue
    clean = raw.replace("-", "").replace("/", "")
    if len(clean) == 8 and clean.isdigit():
        if int(clean[4:8]) > 1900:
            return f"{clean[4:8]}-{clean[2:4]}-{clean[0:2]}"
    return None


def parse_payment_method(raw: str) -> Optional[str]:
    norm = (raw or "").strip().lower()
    if not norm:
        return None
    if "virement" in norm:
        return "virement"
    if "cheque" in norm or "chèque" in norm:
        return "cheque"
    if "espece" in norm or "espèce" in norm:
        return "especes"
    return None


def map_service_to_team_name(raw: str) -> Optional[str]:
    norm = (raw or "").strip().upper()
    if not norm:
        return None
    if norm == "MOD":
        return "MOD"
    if norm in ("MOI", "CAD"):
        return "MOI"
    return None


def map_statut_cadre(raw: str) -> Optional[str]:
    norm = (raw or "").strip().lower()
    if not norm:
        return None
    if "cadre" in norm:
        return "Cadre"
    return "Non-Cadre"


def map_sexe(raw: str) -> Optional[str]:
    norm = (raw or "").strip().lower()
    if norm.startswith("homme") or norm == "m":
        return "M"
    if norm.startswith("femme") or norm == "f":
        return "F"
    return None


def _parse_float(raw: str) -> Optional[float]:
    if not raw or not str(raw).strip():
        return None
    try:
        val = float(str(raw).replace("\u202f", "").replace(" ", "").replace(",", "."))
        return val
    except ValueError:
        return None


def _parse_int(raw: str) -> Optional[int]:
    val = _parse_float(raw)
    if val is None:
        return None
    return int(round(val))


def resolve_prior_service_months(
    prior_days: Optional[int],
    hire_date_iso: Optional[str],
    reference_date: Optional[date] = None,
) -> Optional[int]:
    """Convertit la colonne « Nb jour anc. » en reprise d'ancienneté (mois).

    La colonne de l'export porte l'ancienneté **totale** à la date d'extraction du
    fichier, alors qu'EYWAI stocke dans `prior_service_months` les seuls mois de
    carrière **antérieurs à l'embauche** (le moteur les retranche de `hire_date`).
    Reprendre la colonne telle quelle comptait donc deux fois l'ancienneté acquise
    dans l'entreprise. On retranche ce qui s'est écoulé depuis l'embauche ; la date
    d'extraction n'étant pas dans le fichier, on prend le jour de l'import.
    """
    if prior_days is None or prior_days <= 0:
        return None
    ref = reference_date or date.today()
    seniority_start = ref - timedelta(days=prior_days)
    if not hire_date_iso:
        return _months_between(seniority_start, ref)
    try:
        hire = date.fromisoformat(str(hire_date_iso)[:10])
    except (TypeError, ValueError):
        return _months_between(seniority_start, ref)
    # Ancienneté qui remonte avant l'embauche = vraie reprise ; sinon rien à reprendre.
    return _months_between(seniority_start, hire)


def _months_between(start: date, end: date) -> int:
    if start >= end:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)


def is_dsn_placeholder_email(email: str) -> bool:
    return (email or "").strip().lower().endswith(DSN_PLACEHOLDER_SUFFIX)


def coerce_email_and_phone(email: str, phone: str) -> tuple[str, str]:
    """
    Quadra place parfois un numéro de téléphone dans la colonne e-mail
    quand aucune adresse n'est renseignée.
    """
    email = (email or "").strip()
    phone = (phone or "").strip()
    if not email or "@" in email:
        return email, phone
    digits = re.sub(r"\D", "", email)
    if len(digits) >= 8 and sum(ch.isdigit() for ch in email) >= 8:
        if not phone:
            phone = email
        return "", phone
    return email, phone


def parse_payroll_export_row(
    row: Dict[str, str],
    mapping: Dict[str, str],
    *,
    map_mod_moi_teams: bool = True,
) -> Dict[str, Any]:
    """Transforme une ligne brute en champs applicables + preview."""
    out: Dict[str, Any] = {
        "raw_identity": "",
        "preview": {},
        "employee_patch": {},
        "boeth": None,
        "team_name": None,
        "warnings": [],
    }

    fn = row_value(row, mapping.get("first_name"))
    ln = row_value(row, mapping.get("last_name"))
    nir = normalize_nir(row_value(row, mapping.get("nir")))
    email = row_value(row, mapping.get("email"))
    phone = row_value(row, mapping.get("phone"))
    email, phone = coerce_email_and_phone(email, phone)
    identifiant = row_value(row, mapping.get("identifiant"))

    out["raw_identity"] = f"{fn} {ln}".strip() or identifiant or nir or "Salarié"
    out["preview"] = {
        "first_name": fn or None,
        "last_name": ln or None,
        "nir": nir or None,
        "email": email or None,
        "phone": phone or None,
        "identifiant": identifiant or None,
    }

    patch: Dict[str, Any] = {}

    if fn:
        patch["first_name"] = fn
    if ln:
        patch["last_name"] = ln
    nom_usage = row_value(row, mapping.get("nom_usage"))
    if nom_usage:
        patch["nom_usage"] = nom_usage
    if nir:
        patch["nir"] = nir

    if email and not is_dsn_placeholder_email(email):
        patch["email"] = email
    elif email:
        patch["email"] = email

    if phone:
        patch["phone_number"] = phone

    sexe = map_sexe(row_value(row, mapping.get("sexe")))
    if sexe:
        patch["sexe"] = sexe

    nationality = row_value(row, mapping.get("nationality"))
    if nationality:
        patch["nationalite"] = nationality

    birth_date = parse_french_date(row_value(row, mapping.get("birth_date")))
    birth_city = row_value(row, mapping.get("birth_city"))
    birth_dept = row_value(row, mapping.get("birth_dept"))
    if birth_date:
        patch["date_naissance"] = birth_date
    if birth_city:
        lieu = birth_city
        if birth_dept:
            lieu = f"{birth_city} ({birth_dept})"
        patch["lieu_naissance"] = lieu

    street_num = row_value(row, mapping.get("street_num"))
    btq = row_value(row, mapping.get("btq"))
    street = row_value(row, mapping.get("street"))
    extra = row_value(row, mapping.get("address_extra"))
    cp = row_value(row, mapping.get("postal_code"))
    city = row_value(row, mapping.get("city"))
    if any([street_num, street, cp, city]):
        rue_parts = [p for p in [street_num, btq, street] if p]
        patch["adresse"] = {
            "numero": street_num or None,
            "rue": " ".join(rue_parts) if rue_parts else street or "",
            "complement": extra or None,
            "code_postal": cp or "",
            "ville": city or "",
        }

    hire = parse_french_date(row_value(row, mapping.get("hire_date")))
    if hire:
        patch["hire_date"] = hire

    exit_d = parse_french_date(row_value(row, mapping.get("exit_date")))
    if exit_d:
        patch["contract_end_date"] = exit_d

    cdd = row_value(row, mapping.get("cdd")).lower()
    if cdd == "oui":
        patch["contract_type"] = "CDD"
    elif cdd == "non":
        patch["contract_type"] = "CDI"

    statut = map_statut_cadre(row_value(row, mapping.get("statut_cadre")))
    if statut:
        patch["statut"] = statut

    salary = _parse_float(row_value(row, mapping.get("base_salary")))
    if salary is not None and salary > 0:
        patch["salaire_de_base"] = {"valeur": round(salary, 2), "type": "mensuel"}

    activity_pct = _parse_float(row_value(row, mapping.get("activity_pct")))
    monthly_hours = _parse_float(row_value(row, mapping.get("monthly_hours")))

    if activity_pct is not None and activity_pct > 0:
        is_tp = activity_pct < 100
        if monthly_hours and monthly_hours > 0:
            weekly = round(monthly_hours * 12 / 52, 2)
        else:
            weekly = round(35.0 * activity_pct / 100.0, 2)
        from app.modules.employees.domain.rules import normalize_temps_travail_fields

        is_tp, weekly = normalize_temps_travail_fields(is_tp, weekly)
        patch["is_temps_partiel"] = is_tp
        patch["duree_hebdomadaire"] = weekly
        out["preview"]["activity_pct"] = activity_pct
        out["preview"]["is_temps_partiel"] = is_tp
        out["preview"]["duree_hebdomadaire"] = weekly

    payment = parse_payment_method(row_value(row, mapping.get("payment_method")))
    if payment:
        patch["salary_payment_method"] = payment
        out["preview"]["payment_method"] = payment

    rib_raw = row_value(row, mapping.get("rib"))
    if rib_raw:
        iban, bic, iban_valid, rib_error = parse_rib_cell(rib_raw)
        out["preview"]["rib_raw"] = rib_raw
        out["preview"]["iban_valid"] = iban_valid
        if iban_valid and iban:
            patch["coordonnees_bancaires"] = build_coordonnees_bancaires(iban, bic or "")
        elif rib_error:
            out["warnings"].append(rib_error)
        if payment == "virement" and not iban_valid:
            out["warnings"].append("Virement demandé mais RIB/IBAN invalide.")

    handicap_raw = row_value(row, mapping.get("handicap")).lower()
    if handicap_raw == "oui":
        out["boeth"] = {"boeth_code": "01"}
        out["preview"]["handicap"] = True
    elif handicap_raw == "non":
        out["preview"]["handicap"] = False

    service = row_value(row, mapping.get("service"))
    team_name = None
    if service:
        out["preview"]["service"] = service
    if map_mod_moi_teams:
        team_name = map_service_to_team_name(service)
        if team_name:
            out["team_name"] = team_name
            out["preview"]["team_name"] = team_name

    prior_days = _parse_int(row_value(row, mapping.get("prior_service_days")))
    prior_months = resolve_prior_service_months(prior_days, patch.get("hire_date"))
    if prior_months is not None:
        patch["prior_service_months"] = prior_months

    rp_num = row_value(row, mapping.get("residence_permit_number"))
    rp_from = parse_french_date(row_value(row, mapping.get("residence_permit_from")))
    rp_to = parse_french_date(row_value(row, mapping.get("residence_permit_to")))
    if rp_num or rp_to or rp_from:
        patch["is_subject_to_residence_permit"] = True
        if rp_num:
            patch["residence_permit_number"] = rp_num
        if rp_to:
            patch["residence_permit_expiry_date"] = rp_to
        if rp_from:
            patch["residence_permit_type"] = f"Valide depuis {rp_from}"

    out["employee_patch"] = patch
    enrich_payroll_export_preview(
        out["preview"],
        row=row,
        mapping=mapping,
        patch=patch,
        team_name=team_name,
        monthly_hours=monthly_hours,
    )

    return out
