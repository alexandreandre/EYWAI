"""Colonnes de prévisualisation import export paie (enrichissement salarié)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.admin_import.application.rib_excel import row_value

# (clé preview, libellé UI, clé mapping source — None si dérivée sans colonne dédiée)
PREVIEW_FIELD_SPECS: List[Tuple[str, str, Optional[str]]] = [
    ("identifiant", "Matricule", "identifiant"),
    ("last_name", "Nom", "last_name"),
    ("first_name", "Prénom", "first_name"),
    ("nom_usage", "Nom marital", "nom_usage"),
    ("nir", "NIR", "nir"),
    ("email", "E-mail", "email"),
    ("phone", "Tél.", "phone"),
    ("sexe", "Sexe", "sexe"),
    ("nationality", "Nationalité", "nationality"),
    ("birth_date", "Date naissance", "birth_date"),
    ("birth_dept", "Dept naissance", "birth_dept"),
    ("birth_city", "Commune naissance", "birth_city"),
    ("street_num", "N° voie", "street_num"),
    ("btq", "BTQ", "btq"),
    ("street", "Voie", "street"),
    ("address_extra", "Complément", "address_extra"),
    ("postal_code", "CP", "postal_code"),
    ("city", "Ville", "city"),
    ("hire_date", "Date entrée", "hire_date"),
    ("exit_date", "Date sortie", "exit_date"),
    ("cdd", "CDD (fichier)", "cdd"),
    ("contract_type", "Contrat", "cdd"),
    ("statut", "Statut cadre", "statut_cadre"),
    ("base_salary", "Salaire base", "base_salary"),
    ("activity_pct", "% activité", "activity_pct"),
    ("monthly_hours", "Heures/mois", "monthly_hours"),
    ("is_temps_partiel", "Temps partiel", "activity_pct"),
    ("duree_hebdomadaire", "Heures/sem", "activity_pct"),
    ("payment_method", "Paiement", "payment_method"),
    ("iban_masked", "RIB/IBAN", "rib"),
    ("service", "Service", "service"),
    ("team_name", "Équipe", "service"),
    ("handicap", "Handicapé", "handicap"),
    ("prior_service_days", "Jours anc.", "prior_service_days"),
    ("residence_permit_number", "N° carte séjour", "residence_permit_number"),
    ("residence_permit_from", "Carte obt.", "residence_permit_from"),
    ("residence_permit_to", "Carte expir.", "residence_permit_to"),
]


def _preview_has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def build_preview_field_list(
    column_mapping: Dict[str, str],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Optional[str]]]:
    """Colonnes à afficher : colonnes mappées + champs dérivés présents dans les lignes."""
    seen: set[str] = set()
    fields: List[Dict[str, Optional[str]]] = []

    for preview_key, label, source_key in PREVIEW_FIELD_SPECS:
        if preview_key in seen:
            continue
        map_key = source_key or preview_key
        mapped = map_key in column_mapping
        has_data = any(
            _preview_has_value((row.get("preview_columns") or {}).get(preview_key))
            for row in rows
        )
        if not mapped and not has_data:
            continue
        seen.add(preview_key)
        fields.append(
            {
                "key": preview_key,
                "label": label,
                "source_header": column_mapping.get(map_key) if mapped else None,
            }
        )
    return fields


def enrich_payroll_export_preview(
    preview: Dict[str, Any],
    *,
    row: Dict[str, str],
    mapping: Dict[str, str],
    patch: Dict[str, Any],
    team_name: Optional[str],
    monthly_hours: Optional[float],
) -> None:
    """Complète preview_columns avec toutes les valeurs importables."""
    from app.modules.admin_import.application.payroll_export_parser import parse_french_date

    for key in (
        "street_num",
        "btq",
        "street",
        "address_extra",
        "postal_code",
        "city",
        "birth_dept",
        "birth_city",
    ):
        val = row_value(row, mapping.get(key))
        if val:
            preview[key] = val

    if patch.get("nom_usage"):
        preview["nom_usage"] = patch["nom_usage"]

    if patch.get("sexe"):
        preview["sexe"] = "Homme" if patch["sexe"] == "M" else "Femme"

    if patch.get("nationalite"):
        preview["nationality"] = patch["nationalite"]

    birth_raw = row_value(row, mapping.get("birth_date"))
    if patch.get("date_naissance"):
        preview["birth_date"] = patch["date_naissance"]
    elif birth_raw:
        preview["birth_date"] = parse_french_date(birth_raw) or birth_raw

    if patch.get("hire_date"):
        preview["hire_date"] = patch["hire_date"]
    else:
        hire_raw = row_value(row, mapping.get("hire_date"))
        if hire_raw:
            preview["hire_date"] = parse_french_date(hire_raw) or hire_raw

    if patch.get("contract_end_date"):
        preview["exit_date"] = patch["contract_end_date"]
    else:
        exit_raw = row_value(row, mapping.get("exit_date"))
        if exit_raw:
            preview["exit_date"] = parse_french_date(exit_raw) or exit_raw

    cdd_raw = row_value(row, mapping.get("cdd"))
    if cdd_raw:
        preview["cdd"] = cdd_raw
    if patch.get("contract_type"):
        preview["contract_type"] = patch["contract_type"]

    if patch.get("statut"):
        preview["statut"] = patch["statut"]

    sal = patch.get("salaire_de_base")
    if isinstance(sal, dict) and sal.get("valeur") is not None:
        preview["base_salary"] = sal["valeur"]
    else:
        raw_sal = row_value(row, mapping.get("base_salary"))
        if raw_sal:
            preview["base_salary"] = raw_sal

    if monthly_hours is not None and monthly_hours > 0:
        preview["monthly_hours"] = monthly_hours
    else:
        raw_hours = row_value(row, mapping.get("monthly_hours"))
        if raw_hours:
            preview["monthly_hours"] = raw_hours

    prior_raw = row_value(row, mapping.get("prior_service_days"))
    if prior_raw:
        preview["prior_service_days"] = prior_raw

    rp_num = row_value(row, mapping.get("residence_permit_number"))
    rp_from_raw = row_value(row, mapping.get("residence_permit_from"))
    rp_to_raw = row_value(row, mapping.get("residence_permit_to"))
    if rp_num:
        preview["residence_permit_number"] = rp_num
    if rp_from_raw:
        preview["residence_permit_from"] = parse_french_date(rp_from_raw) or rp_from_raw
    if rp_to_raw:
        preview["residence_permit_to"] = parse_french_date(rp_to_raw) or rp_to_raw

    if team_name:
        preview["team_name"] = team_name

    if "is_temps_partiel" in patch:
        preview["is_temps_partiel"] = "Oui" if patch["is_temps_partiel"] else "Non"
    if patch.get("duree_hebdomadaire") is not None:
        preview["duree_hebdomadaire"] = patch["duree_hebdomadaire"]

    if patch.get("salary_payment_method"):
        preview["payment_method"] = patch["salary_payment_method"]

    if preview.get("handicap") is True:
        preview["handicap"] = "Oui"
    elif preview.get("handicap") is False:
        preview["handicap"] = "Non"
