"""Synchronisation catalogue mutuelle depuis données PSC importées DSN."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.dsn_import.psc_catalog")

PACK_LABELS = {
    "isole": "Isolé",
    "famille": "Famille",
    "duo": "Duo",
    "autre": "Autre",
}

STATUT_LABELS = {
    "cadre": "Cadre",
    "non_cadre": "Non-cadre",
}


def _build_libelle(
    pack: Optional[str],
    statut: str,
    montant_sal: float,
    montant_pat: float,
) -> str:
    """Libellé catalogue sans montants (affichés à part dans l'UI)."""
    parts: list[str] = []
    if pack and pack in PACK_LABELS:
        parts.append(PACK_LABELS[pack])
    if statut in STATUT_LABELS:
        parts.append(STATUT_LABELS[statut])
    if not parts:
        parts.append("Formule mutuelle")
    return " · ".join(parts)


def _find_existing_type(
    client: Any,
    company_id: str,
    row: Dict[str, Any],
) -> Optional[str]:
    query = (
        client.table("company_mutuelle_types")
        .select("id")
        .eq("company_id", company_id)
        .eq("montant_salarial", row["montant_salarial"])
        .eq("montant_patronal", row["montant_patronal"])
        .eq("statut_categoriel", row["statut_categoriel"])
    )
    if row.get("pack_couverture"):
        query = query.eq("pack_couverture", row["pack_couverture"])
    if row.get("code_option_dsn"):
        query = query.eq("code_option_dsn", row["code_option_dsn"])
    if row.get("reference_contrat_dsn"):
        query = query.eq("reference_contrat_dsn", row["reference_contrat_dsn"])
    if row.get("code_organisme_dsn"):
        query = query.eq("code_organisme_dsn", row["code_organisme_dsn"])

    resp = query.limit(1).execute()
    if resp.data:
        return str(resp.data[0]["id"])
    return None


def sync_employee_psc_catalog(
    company_id: str,
    employee_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Crée ou réutilise une formule mutuelle catalogue et l'affecte au salarié
    lorsque l'import DSN a détecté une affiliation / cotisation PSC.
    """
    specificites = payload.get("specificites_paie") or {}
    if not isinstance(specificites, dict):
        return
    mutuelle = specificites.get("mutuelle") or {}
    if not isinstance(mutuelle, dict) or not mutuelle.get("adhesion"):
        return

    lignes = mutuelle.get("lignes_specifiques") or []
    if not lignes:
        return

    ligne = lignes[0]
    montant_sal = float(ligne.get("montant_salarial") or 0)
    montant_pat = float(ligne.get("montant_patronal") or 0)
    if montant_sal <= 0 and montant_pat <= 0:
        return

    meta = payload.get("_psc_meta") or {}
    pack = mutuelle.get("pack_couverture") or meta.get("pack_couverture")
    statut = meta.get("statut_categoriel") or (
        "cadre" if payload.get("statut") == "Cadre" else "non_cadre"
    )
    dsn = mutuelle.get("dsn") or {}

    catalog_row: Dict[str, Any] = {
        "company_id": company_id,
        "libelle": _build_libelle(pack, statut, montant_sal, montant_pat),
        "montant_salarial": round(montant_sal, 2),
        "montant_patronal": round(montant_pat, 2),
        "part_patronale_soumise_a_csg": bool(
            ligne.get("part_patronale_soumise_a_csg", True)
        ),
        "is_active": True,
        "statut_categoriel": statut,
        "source": "dsn_import",
    }
    if pack:
        catalog_row["pack_couverture"] = pack
    if dsn.get("code_option"):
        catalog_row["code_option_dsn"] = dsn["code_option"]
    if dsn.get("reference_contrat"):
        catalog_row["reference_contrat_dsn"] = dsn["reference_contrat"]
    if dsn.get("code_organisme"):
        catalog_row["code_organisme_dsn"] = dsn["code_organisme"]

    client = get_supabase_admin_client()
    mutuelle_type_id = _find_existing_type(client, company_id, catalog_row)

    if not mutuelle_type_id:
        resp = client.table("company_mutuelle_types").insert(catalog_row).execute()
        if not resp.data:
            logger.warning("Échec création formule mutuelle DSN pour %s", employee_id)
            return
        mutuelle_type_id = str(resp.data[0]["id"])

    client.table("employee_mutuelle_types").delete().eq(
        "employee_id", employee_id
    ).execute()

    client.table("employee_mutuelle_types").upsert(
        {
            "employee_id": employee_id,
            "mutuelle_type_id": mutuelle_type_id,
        },
        on_conflict="employee_id,mutuelle_type_id",
    ).execute()

    mutuelle_updated = {
        **mutuelle,
        "adhesion": True,
        "mutuelle_type_ids": [mutuelle_type_id],
        "lignes_specifiques": [],
    }
    specificites_updated = {**specificites, "mutuelle": mutuelle_updated}
    client.table("employees").update(
        {"specificites_paie": specificites_updated}
    ).eq("id", employee_id).execute()
