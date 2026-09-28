"""Corriger un bulletin : écrire ses variables du mois, puis le recalculer.

L'écran envoyait le bulletin retouché ligne à ligne, et le serveur
l'enregistrait tel quel : un montant retouché laissait les bases, les
cotisations, le net et les cumuls de l'ancien calcul, et les droits d'accès du
bulletin n'étaient pas vérifiés sur les données reçues (audit du 28/09).

Désormais l'écran n'envoie que des corrections (heures sup, primes du mois,
notes). Elles sont écrites comme variables du mois, sous le verrou de
génération, puis le moteur refait le bulletin en entier. Si le moteur échoue,
les variables restent écrites (elles sont la vérité), le bulletin est marqué
« recalcul en attente » et ne peut pas être validé en l'état.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from app.core.database import supabase
from app.modules.payroll.documents.verrou_generation import verrou_de_generation
from app.modules.payslips.application.commands import (
    _refuser_si_importe,
    archiver_version,
    _set_payslip_status_brouillon,
    generate_payslip,
)
from app.modules.payslips.application.dto import (
    CorrigerBulletinInput,
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipConflictError,
    PayslipNotFoundError,
    RestorePayslipInput,
)
from app.modules.payslips.application.impression import reimprimer_bulletin
from app.modules.payslips.application.primes_editees import (
    appliquer_primes_editees,
    verifier_appartenance,
)
from app.modules.payslips.domain.corrections import (
    CorrectionsBulletin,
    corrections_pour_revenir,
    resume_des_corrections,
)
from app.modules.payslips.domain.heures_sup import (
    LIBELLE_HS_DECLAREES,
    LIBELLE_HS_DECLAREES_50,
    LIBELLES_HS_DECLAREES,
)
from app.modules.payslips.domain.historique import entree_de_version
from app.modules.payslips.domain.primes_editees import primes_saisies_du_bulletin

logger = logging.getLogger(__name__)

MESSAGE_CONFLIT = (
    "Le bulletin a changé depuis son ouverture. Rechargez-le avant de le corriger."
)
MESSAGE_RIEN_A_ENREGISTRER = "Aucune modification à enregistrer."

_COLONNES = (
    "id, employee_id, company_id, year, month, status, updated_at, url, "
    "payslip_data, pdf_notes, internal_notes, edit_history, pdf_storage_path"
)


def _lire_bulletin(payslip_id: str) -> dict[str, Any] | None:
    r = (
        supabase.table("payslips")
        .select(_COLONNES)
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def _relire_en_entier(payslip_id: str) -> dict[str, Any] | None:
    """La ligne complète, pour la réponse (le détail du bulletin l'exige)."""
    r = (
        supabase.table("payslips")
        .select("*")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def _instant(valeur: Any) -> datetime | None:
    if not valeur:
        return None
    try:
        return datetime.fromisoformat(str(valeur).replace("Z", "+00:00"))
    except ValueError:
        return None


def _refuser_si_modifie_depuis(bulletin: dict[str, Any], base_updated_at: str | None) -> None:
    if not base_updated_at:
        return
    lu, actuel = _instant(base_updated_at), _instant(bulletin.get("updated_at"))
    if lu is None or actuel is None:
        if str(base_updated_at) != str(bulletin.get("updated_at")):
            raise PayslipConflictError(MESSAGE_CONFLIT)
        return
    if lu != actuel:
        raise PayslipConflictError(MESSAGE_CONFLIT)


def _periode(bulletin: dict[str, Any]) -> dict[str, Any]:
    return {
        "employee_id": str(bulletin["employee_id"]),
        "company_id": str(bulletin["company_id"]),
        "year": int(bulletin["year"]),
        "month": int(bulletin["month"]),
    }


# --- Variables du mois ---


def _retirer_heures_sup_declarees(periode: dict[str, Any]) -> None:
    """Retire les seules déclarations faites depuis le bulletin : les autres
    saisies d'heures (reprise, règles de la société) ne sont pas les nôtres."""
    (
        supabase.table("monthly_inputs")
        .delete()
        .match(periode)
        .in_("name", list(LIBELLES_HS_DECLAREES))
        .execute()
    )


def _declarer_heures_sup(periode: dict[str, Any], hs25: float, hs50: float) -> None:
    """Pose les deux paliers ensemble, toujours : le moteur les lit par paire."""
    _retirer_heures_sup_declarees(periode)
    base = {
        **periode,
        "amount": 0,
        "is_socially_taxed": True,
        "is_taxable": True,
        "manual_override": True,
    }
    supabase.table("monthly_inputs").insert(
        [
            {**base, "name": LIBELLE_HS_DECLAREES, "payroll_quantity": round(hs25, 2)},
            {**base, "name": LIBELLE_HS_DECLAREES_50, "payroll_quantity": round(hs50, 2)},
        ]
    ).execute()


def _ecrire_variables(corrections: CorrectionsBulletin, periode: dict[str, Any]) -> None:
    if corrections.revenir_au_planning:
        _retirer_heures_sup_declarees(periode)
    if corrections.heures_sup is not None:
        _declarer_heures_sup(periode, *corrections.heures_sup)
    if not corrections.primes.vide:
        appliquer_primes_editees(corrections.primes, **periode)


# --- Notes ---


def _note_pdf_changee(bulletin: dict[str, Any], pdf_notes: str | None) -> bool:
    if pdf_notes is None:
        return False
    return (pdf_notes.strip() or None) != (bulletin.get("pdf_notes") or None)


def _enregistrer_notes(
    bulletin: dict[str, Any],
    cmd: CorrigerBulletinInput,
    note_pdf_changee: bool,
    note_interne: str | None,
) -> None:
    changements: dict[str, Any] = {}
    if note_pdf_changee:
        changements["pdf_notes"] = (cmd.pdf_notes or "").strip() or None
    if note_interne:
        notes = bulletin.get("internal_notes")
        notes = list(notes) if isinstance(notes, list) else []
        notes.append(
            {
                "id": str(uuid.uuid4()),
                "author_id": cmd.current_user_id,
                "author_name": cmd.current_user_name,
                "timestamp": datetime.now().isoformat(),
                "content": note_interne,
            }
        )
        changements["internal_notes"] = notes
    if changements:
        supabase.table("payslips").update(changements).eq("id", bulletin["id"]).execute()


def _archiver_avant_reimpression(bulletin: dict[str, Any], cmd: CorrigerBulletinInput, motif: str) -> None:
    """Seule la note change : on garde quand même la version d'avant."""
    archiver_version(
        bulletin,
        edited_by=cmd.current_user_id,
        edited_by_name=cmd.current_user_name,
        changes_summary=motif,
        action="notes",
    )


# --- Recalcul ---


def _message_d_erreur(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        detail = detail.get("message") or detail
    return str(detail or exc) or exc.__class__.__name__


def _marquer_recalcul_en_attente(payslip_id: str, erreur: str) -> None:
    """Le bulletin enregistré ne reflète plus ses variables : on le dit sur lui."""
    try:
        bulletin = _lire_bulletin(payslip_id) or {}
        donnees = dict(bulletin.get("payslip_data") or {})
        donnees["recalcul_en_attente"] = {
            "depuis": datetime.now().isoformat(),
            "erreur": erreur,
        }
        supabase.table("payslips").update({"payslip_data": donnees}).eq(
            "id", payslip_id
        ).execute()
    except Exception:  # noqa: BLE001 — la réponse porte déjà l'erreur
        logger.exception("[correction] Marque « recalcul en attente » non posée sur %s", payslip_id)


def _recalculer(bulletin: dict[str, Any], cmd: CorrigerBulletinInput, motif: str) -> str | None:
    """Régénère le bulletin ; rend le message d'erreur s'il échoue."""
    try:
        resultat = generate_payslip(
            GeneratePayslipInput(
                employee_id=str(bulletin["employee_id"]),
                year=int(bulletin["year"]),
                month=int(bulletin["month"]),
                # Le bulletin existe déjà : ces deux gardes ont été franchies à
                # sa première génération. Les réopposer bloquerait une correction.
                force_calendrier_incomplet=True,
                regenerer_bulletin_valide=True,
                requested_by=cmd.current_user_id,
                requested_by_name=cmd.current_user_name,
                motif=motif,
            )
        )
        if str(getattr(resultat, "status", "success")) != "success":
            raise RuntimeError(getattr(resultat, "message", None) or "Recalcul impossible.")
    except Exception as exc:  # noqa: BLE001 — l'erreur est rendue à l'écran
        logger.exception("[correction] Recalcul du bulletin %s impossible", bulletin["id"])
        erreur = _message_d_erreur(exc)
        _marquer_recalcul_en_attente(str(bulletin["id"]), erreur)
        return erreur
    return None


def corriger_bulletin(cmd: CorrigerBulletinInput) -> dict[str, Any]:
    """Écrit les corrections comme variables du mois, puis recalcule le bulletin.

    Rend `{"payslip", "new_pdf_url", "recalcule", "recalcul_erreur"}`.
    """
    bulletin = _lire_bulletin(cmd.payslip_id)
    if not bulletin:
        raise PayslipNotFoundError("Bulletin non trouvé")
    _refuser_si_importe(cmd.payslip_id)
    _refuser_si_modifie_depuis(bulletin, cmd.base_updated_at)

    corrections = cmd.corrections
    note_pdf_changee = _note_pdf_changee(bulletin, cmd.pdf_notes)
    note_interne = (cmd.internal_note or "").strip() or None
    if not (corrections.change_des_variables or note_pdf_changee or note_interne):
        raise PayslipBadRequestError(MESSAGE_RIEN_A_ENREGISTRER)

    periode = _periode(bulletin)
    # Avant toute écriture : une saisie d'une autre fiche ne laisse aucune trace.
    verifier_appartenance(corrections.primes.ids_touches, **periode)
    motif = (cmd.changes_summary or "").strip() or resume_des_corrections(corrections)

    recalcule, erreur = False, None
    with verrou_de_generation(periode["employee_id"], periode["year"], periode["month"]):
        if bulletin.get("status") == "valide":
            # D'abord : le salarié ne doit jamais voir comme validé un contenu
            # qui ne l'a pas été.
            _set_payslip_status_brouillon(cmd.payslip_id)
            logger.warning(
                "[correction] Bulletin validé %s corrigé par %s : repassé en brouillon.",
                cmd.payslip_id,
                cmd.current_user_id,
            )
        _enregistrer_notes(bulletin, cmd, note_pdf_changee, note_interne)
        if corrections.change_des_variables:
            _ecrire_variables(corrections, periode)
            erreur = _recalculer(bulletin, cmd, motif)
            recalcule = erreur is None
        elif note_pdf_changee:
            _archiver_avant_reimpression(bulletin, cmd, motif)
            reimprimer_bulletin(cmd.payslip_id)

    frais = _relire_en_entier(cmd.payslip_id) or bulletin
    return {
        "payslip": frais,
        "new_pdf_url": frais.get("url"),
        "recalcule": recalcule,
        "recalcul_erreur": erreur,
    }


# --- Restauration ---

MESSAGE_RIEN_A_RESTAURER = (
    "Cette version a déjà les mêmes heures sup et les mêmes primes que le "
    "bulletin : rien à restaurer. Le reste (planning, absences, salaire) se "
    "corrige à sa source."
)


def _saisies_existantes(ids: set[str], periode: dict[str, Any]) -> set[str]:
    if not ids:
        return set()
    r = (
        supabase.table("monthly_inputs")
        .select("id")
        .in_("id", sorted(ids))
        .match(periode)
        .execute()
    )
    return {str(row["id"]) for row in r.data or []}


def restaurer_version(cmd: RestorePayslipInput) -> dict[str, Any]:
    """Revient aux heures sup et aux primes d'une version, puis recalcule.

    La restauration recopiait l'ancien bulletin sans revenir sur les variables
    du mois : le prochain recalcul l'effaçait, et le PDF gardait les cotisations
    et le net de la version courante (audit du 28/09).
    """
    bulletin = _lire_bulletin(cmd.payslip_id)
    if not bulletin:
        raise PayslipNotFoundError("Bulletin non trouvé")
    _refuser_si_importe(cmd.payslip_id)
    historique = bulletin.get("edit_history")
    entree = entree_de_version(historique if isinstance(historique, list) else [], cmd.version)
    if entree is None:
        raise PayslipNotFoundError("Version introuvable")
    cible = entree.get("previous_payslip_data")
    if not isinstance(cible, dict) or not cible:
        raise PayslipBadRequestError("Les données de cette version sont introuvables.")

    periode = _periode(bulletin)
    corrections = corrections_pour_revenir(
        bulletin.get("payslip_data"),
        cible,
        saisies_existantes=_saisies_existantes(set(primes_saisies_du_bulletin(cible)), periode),
    )
    if not corrections.change_des_variables:
        raise PayslipBadRequestError(MESSAGE_RIEN_A_RESTAURER)
    return corriger_bulletin(
        CorrigerBulletinInput(
            payslip_id=cmd.payslip_id,
            corrections=corrections,
            current_user_id=cmd.current_user_id,
            current_user_name=cmd.current_user_name,
            changes_summary=f"Retour à la version {cmd.version}",
        )
    )
