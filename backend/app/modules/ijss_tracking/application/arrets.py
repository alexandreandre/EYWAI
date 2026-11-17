"""Écran « Arrêts et IJ » (retour d'Elsa du 16/11).

Le parcours d'Elsa : on enregistre l'arrêt (subrogation cochée ou non), on joint
si on veut les preuves (virement CPAM, IJ transmises par le salarié, décompte),
on saisit les IJ reçues du mois, et Martine verse le maintien. Ce module lit les
arrêts du mois et porte ce geste unique ; le rapprochement détaillé (imports,
clôture) reste dans `service.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.ijss_tracking.domain.arrets_du_mois import (
    TYPES_JUSTIFICATIF,
    bornes_arret,
    bulletin_calcule_avant,
    chiffres_du_bulletin,
    etat_du_maintien,
    ij_estimees_du_bulletin,
    jours_dans_le_mois,
    refus_montant_ij,
)
from app.modules.ijss_tracking.domain.enums import IJSS_ELIGIBLE_ABSENCE_TYPES
from app.modules.ijss_tracking.domain.saisie_ijss import LIBELLE_IJSS_VALIDEES
from app.modules.ijss_tracking.infrastructure import repository as repo

logger = get_logger("modules.ijss_tracking.arrets")

BUCKET_JUSTIFICATIFS = "leave_attachments"
TABLE_JUSTIFICATIFS = "absence_request_justificatifs"


def _client():
    return get_supabase_admin_client()


def _urls_signees(chemins: list[str]) -> dict[str, str]:
    if not chemins:
        return {}
    try:
        from app.modules.absences.infrastructure.providers import storage_provider

        return storage_provider.create_signed_urls(
            chemins, BUCKET_JUSTIFICATIFS, expiry_seconds=3600
        )
    except Exception:
        logger.warning(
            "URLs signées des justificatifs d'arrêt indisponibles", exc_info=True
        )
        return {}


def _arrets_valides(company_id: str) -> list[dict[str, Any]]:
    return (
        _client()
        .table("absence_requests")
        .select(
            "id, employee_id, type, arret_type, selected_days, subrogation_active, "
            "attachment_url, filename, comment, created_at"
        )
        .eq("company_id", company_id)
        .eq("status", "validated")
        .in_("type", list(IJSS_ELIGIBLE_ABSENCE_TYPES))
        .execute()
    ).data or []


def _justificatifs(absence_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not absence_ids:
        return {}
    lignes = (
        _client()
        .table(TABLE_JUSTIFICATIFS)
        .select("id, absence_request_id, kind, storage_path, filename, created_at")
        .in_("absence_request_id", absence_ids)
        .order("created_at")
        .execute()
    ).data or []
    urls = _urls_signees([l["storage_path"] for l in lignes if l.get("storage_path")])
    par_arret: dict[str, list[dict[str, Any]]] = {}
    for l in lignes:
        par_arret.setdefault(str(l["absence_request_id"]), []).append(
            {
                "id": str(l["id"]),
                "kind": l.get("kind") or "autre",
                "filename": l.get("filename"),
                "url": urls.get(l.get("storage_path") or ""),
                "created_at": l.get("created_at"),
            }
        )
    return par_arret


def _saisies_ij_du_mois(company_id: str, year: int, month: int) -> dict[str, float]:
    lignes = (
        _client()
        .table("monthly_inputs")
        .select("employee_id, amount")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .eq("name", LIBELLE_IJSS_VALIDEES)
        .execute()
    ).data or []
    return {
        str(l["employee_id"]): round(abs(float(l.get("amount") or 0)), 2)
        for l in lignes
    }


def lister_arrets_du_mois(company_id: str, year: int, month: int) -> dict[str, Any]:
    """Les arrêts qui touchent le mois, un par ligne, du plus récent au plus ancien."""
    from app.modules.ijss_tracking.application.service import (
        _bulletins_du_mois,
        _fetch_employees,
    )

    arrets = [
        a
        for a in _arrets_valides(company_id)
        if jours_dans_le_mois(a.get("selected_days"), year, month) > 0
    ]
    salaries = {str(e["id"]): e for e in _fetch_employees(company_id)}
    bulletins = _bulletins_du_mois(company_id, year, month)
    saisies = _saisies_ij_du_mois(company_id, year, month)
    periode = repo.get_or_create_period(company_id, year, month) or {}
    lignes_attendues = {
        str(l.get("absence_request_id") or ""): l
        for l in (
            repo.list_expected_lines(str(periode["id"])) if periode.get("id") else []
        )
    }
    pieces = _justificatifs([str(a["id"]) for a in arrets])
    certificats = _urls_signees(
        [a["attachment_url"] for a in arrets if a.get("attachment_url")]
    )

    jour_de_remise: list[int] = []

    def est_remis(bulletin: dict[str, Any] | None) -> bool:
        if not bulletin or bulletin.get("year") is None:
            return False
        from app.modules.payslips.domain.mise_a_disposition import remis_le_du_bulletin
        from app.modules.payslips.infrastructure.mise_a_disposition_queries import (
            jour_de_la_societe,
        )
        from app.shared.domain.temps_local import aujourd_hui_local

        if not jour_de_remise:
            jour_de_remise.append(jour_de_la_societe(company_id))
        remis = remis_le_du_bulletin(bulletin, jour=jour_de_remise[0])
        return bool(remis and remis <= aujourd_hui_local())

    lignes: list[dict[str, Any]] = []
    for a in arrets:
        aid = str(a["id"])
        eid = str(a.get("employee_id") or "")
        emp = salaries.get(eid, {})
        debut, fin = bornes_arret(a.get("selected_days"))
        bulletin = bulletins.get(eid)
        pdata = (bulletin or {}).get("payslip_data") or None
        attendue = lignes_attendues.get(aid) or {}
        estimees = ij_estimees_du_bulletin(pdata)
        if estimees is None and attendue.get("ijss_theorique") is not None:
            estimees = round(float(attendue["ijss_theorique"]), 2)
        recues = attendue.get("ijss_brut_validated")
        lignes.append(
            {
                "absence_id": aid,
                "employee_id": eid,
                "employee_name": f"{emp.get('last_name', '')} {emp.get('first_name', '')}".strip(),
                "type": a.get("type"),
                "arret_type": a.get("arret_type"),
                "date_debut": debut.isoformat() if debut else None,
                "date_fin": fin.isoformat() if fin else None,
                "jours_dans_le_mois": jours_dans_le_mois(
                    a.get("selected_days"), year, month
                ),
                "subrogation_active": bool(a.get("subrogation_active")),
                "certificat_url": certificats.get(a.get("attachment_url") or ""),
                "certificat_filename": a.get("filename"),
                "ij_estimees": estimees,
                "ij_recues": round(float(recues), 2) if recues is not None else None,
                "ij_saisies_du_mois": saisies.get(eid),
                "ij_appliquees_le": attendue.get("applied_to_payslip_at"),
                "bulletin_id": (bulletin or {}).get("id"),
                "maintien": (
                    # Arrêt enregistré après le calcul du bulletin : le dire, pas
                    # « pas de maintien » ni 0 jour indemnisé (MAJI, 17/11). Un
                    # bulletin déjà remis ne se régénère plus : rappel au suivant.
                    {
                        "etat": (
                            "bulletin_remis_avant_l_arret"
                            if est_remis(bulletin)
                            else "bulletin_a_recalculer"
                        ),
                        "montant_verse": 0.0,
                        "montant_en_attente": 0.0,
                        "motif": None,
                    }
                    if bulletin_calcule_avant(bulletin, a.get("created_at"))
                    else etat_du_maintien(pdata)
                ),
                "justificatifs": pieces.get(aid, []),
            }
        )
    lignes.sort(key=lambda l: (l["date_debut"] or "", l["employee_name"]), reverse=True)
    return {
        "year": year,
        "month": month,
        "periode_cloturee": periode.get("status") == "closed",
        "arrets": lignes,
    }


def _arret_de_la_societe(company_id: str, absence_id: str) -> dict[str, Any]:
    arret = (
        _client()
        .table("absence_requests")
        .select(
            "id, employee_id, company_id, type, status, selected_days, subrogation_active"
        )
        .eq("id", absence_id)
        .maybe_single()
        .execute()
    )
    data = arret.data if arret else None
    if not data or str(data.get("company_id")) != str(company_id):
        raise LookupError("Arrêt introuvable.")
    if data.get("type") not in IJSS_ELIGIBLE_ABSENCE_TYPES:
        raise ValueError("Cette absence n'est pas un arrêt indemnisé par la CPAM.")
    if data.get("status") != "validated":
        raise ValueError("Cet arrêt n'est pas enregistré (validé).")
    return data


def _ligne_attendue_de_l_arret(
    company_id: str,
    arret: dict[str, Any],
    periode: dict[str, Any],
    year: int,
    month: int,
) -> dict[str, Any]:
    """La ligne du suivi pour cet arrêt et ce mois ; créée si le bulletin n'a pas
    encore été synchronisé ou fait."""
    aid = str(arret["id"])
    from app.modules.ijss_tracking.application.service import _bulletins_du_mois

    bulletin = _bulletins_du_mois(company_id, year, month).get(
        str(arret["employee_id"])
    )
    for l in repo.list_expected_lines(str(periode["id"])):
        if str(l.get("absence_request_id") or "") == aid:
            # Bulletin recalculé depuis : la ligne reprend ses chiffres (elle
            # restait figée sur un bulletin d'avant l'arrêt, MAJI 17/11).
            if bulletin and calcul_non_repris(l, bulletin):
                return rafraichir_la_ligne(l, bulletin) or l
            return l
    chiffres = chiffres_de_la_ligne(bulletin)
    ligne = repo.upsert_expected_line(
        {
            "company_id": company_id,
            "period_id": str(periode["id"]),
            "employee_id": str(arret["employee_id"]),
            "absence_request_id": aid,
            "payslip_id": (bulletin or {}).get("id"),
            "period_year": year,
            "period_month": month,
            "ijss_theorique": 0.0,
            **chiffres,
            "subrogation_active": bool(arret.get("subrogation_active")),
        }
    )
    if not ligne:
        raise RuntimeError("La ligne de suivi de cet arrêt n'a pas pu être créée.")
    return ligne


def rafraichir_la_ligne(
    ligne: dict[str, Any], bulletin: dict[str, Any] | None
) -> dict[str, Any] | None:
    """La ligne de suivi reprend les chiffres du bulletin actuel du mois."""
    if not bulletin:
        return None
    return repo.update_expected_line(
        str(ligne["id"]),
        {
            **chiffres_de_la_ligne(bulletin),
            "payslip_id": bulletin.get("id") or ligne.get("payslip_id"),
        },
    )


#: Le calcul du bulletin que la ligne a repris (son `generated_at`).
CLE_CALCUL_REPRIS = "bulletin_genere_le"


def chiffres_de_la_ligne(bulletin: dict[str, Any] | None) -> dict[str, Any]:
    """Les chiffres du bulletin, avec la trace du calcul repris."""
    chiffres = chiffres_du_bulletin((bulletin or {}).get("payslip_data"))
    chiffres["calculation_snapshot"][CLE_CALCUL_REPRIS] = (bulletin or {}).get("generated_at")
    return chiffres


def calcul_non_repris(ligne: dict[str, Any], bulletin: dict[str, Any]) -> bool:
    """Le bulletin a été recalculé depuis que la ligne l'a lu. Pas `updated_at` :
    le tableau de bord du suivi le réécrit à chaque ouverture (relecture du 17/11)."""
    snapshot = ligne.get("calculation_snapshot") or {}
    return bool(bulletin.get("generated_at")) and snapshot.get(CLE_CALCUL_REPRIS) != bulletin.get(
        "generated_at"
    )


def enregistrer_ij_recues(
    company_id: str,
    absence_id: str,
    year: int,
    month: int,
    montant: float,
    user_id: str,
) -> dict[str, Any]:
    """Les IJ du mois sont connues : un seul geste.

    Le montant est validé sur la ligne de l'arrêt, puis porté au bulletin par la
    saisie du mois (somme des arrêts du salarié) : bulletin pas encore fait, il
    le prendra à sa génération ; bulletin en cours, il est recalculé ; bulletin
    remis ou mois repris, rien ne change et la réponse dit quoi faire.
    """
    refus = refus_montant_ij(montant)
    if refus:
        raise ValueError(refus)
    montant = round(float(montant), 2)
    arret = _arret_de_la_societe(company_id, absence_id)
    if jours_dans_le_mois(arret.get("selected_days"), year, month) == 0:
        raise ValueError("Cet arrêt ne touche pas ce mois.")
    periode = repo.get_or_create_period(company_id, year, month)
    if not periode:
        raise RuntimeError("Le suivi du mois n'a pas pu être ouvert.")
    if periode.get("status") == "closed":
        raise ValueError("Le suivi IJ de ce mois est clôturé.")

    ligne = _ligne_attendue_de_l_arret(company_id, arret, periode, year, month)
    from app.modules.ijss_tracking.application.apply_to_payslip import (
        apply_validated_ijss_to_payslip,
        validate_expected_line_brut,
    )

    validate_expected_line_brut(
        company_id, str(ligne["id"]), user_id, montant, "manual"
    )

    employee_id = str(arret["employee_id"])
    total = round(
        sum(
            float(l.get("ijss_brut_validated") or 0)
            for l in repo.list_expected_lines(str(periode["id"]))
            if str(l.get("employee_id") or "") == employee_id
            and l.get("ijss_brut_validated") is not None
        ),
        2,
    )
    from app.modules.payslips.application.commands import _fetch_existing_payslip

    existant = _fetch_existing_payslip(employee_id, year, month)
    if not existant:
        from app.modules.ijss_tracking.application.apply_to_payslip import (
            _ecrire_saisie_ijss,
        )

        _ecrire_saisie_ijss(
            employee_id, company_id, year, month, total, str(ligne["id"])
        )
        repo.update_expected_line(
            str(ligne["id"]),
            {
                "applied_to_payslip_at": datetime.now(UTC).isoformat(),
                "applied_ijss_brut": total,
            },
        )
        return {
            "statut": "en_attente_du_bulletin",
            "message": f"IJ enregistrées ({montant:.2f} €). Le bulletin du mois les prendra à sa génération.",
            "montant": montant,
        }

    from app.modules.payslips.application.commands import refuser_si_remis
    from app.modules.payslips.application.dto import PayslipBadRequestError

    try:
        refuser_si_remis(existant, year, month)
    except PayslipBadRequestError:
        # Le montant reste noté sur l'arrêt ; le bulletin remis ne bouge pas.
        return {
            "statut": "bulletin_remis",
            "message": (
                f"IJ enregistrées ({montant:.2f} €). Le bulletin du mois est déjà remis : "
                "il ne change pas. Versez le maintien retenu sur le bulletin suivant, "
                "avec la prime « Rappel de maintien de salaire »."
            ),
            "montant": montant,
        }

    if total != montant:
        # Deux arrêts le même mois : la saisie porte la somme du salarié.
        repo.update_expected_line(str(ligne["id"]), {"ijss_brut_validated": total})
    try:
        apply_validated_ijss_to_payslip(company_id, str(ligne["id"]), user_id)
    finally:
        if total != montant:
            repo.update_expected_line(
                str(ligne["id"]), {"ijss_brut_validated": montant}
            )
    return {
        "statut": "bulletin_recalcule",
        "message": f"IJ enregistrées ({montant:.2f} €) et bulletin du mois recalculé.",
        "montant": montant,
    }


def ajouter_justificatif(
    company_id: str,
    absence_id: str,
    kind: str,
    storage_path: str,
    filename: str | None,
    user_id: str,
) -> dict[str, Any]:
    if kind not in TYPES_JUSTIFICATIF:
        raise ValueError("Type de justificatif inconnu.")
    if (
        not storage_path
        or ".." in storage_path
        or not storage_path.startswith(f"{user_id}/")
    ):
        raise ValueError("Fichier introuvable : déposez-le de nouveau.")
    arret = _arret_de_la_societe(company_id, absence_id)
    ins = (
        _client()
        .table(TABLE_JUSTIFICATIFS)
        .insert(
            {
                "company_id": company_id,
                "absence_request_id": str(arret["id"]),
                "kind": kind,
                "storage_path": storage_path,
                "filename": filename,
                "created_by": user_id,
            }
        )
        .execute()
    )
    if not ins.data:
        raise RuntimeError("Le justificatif n'a pas été enregistré.")
    return ins.data[0]


def supprimer_justificatif(company_id: str, justificatif_id: str) -> None:
    res = (
        _client()
        .table(TABLE_JUSTIFICATIFS)
        .delete()
        .eq("id", justificatif_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not res.data:
        raise LookupError("Justificatif introuvable.")
