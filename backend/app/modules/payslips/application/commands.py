"""
Commandes (use cases en écriture) du module payslips.

Logique applicative : décision forfait jour vs heures, délégation aux providers
(services legacy). Les routers n'appellent que ces commandes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.core.database import supabase
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.onboarding.domain.profile import (
    missing_payroll_fields,
    payroll_block_reason,
)
from app.modules.payslips.application.dto import (
    EditPayslipInput,
    GeneratePayslipInput,
    GeneratePayslipResult,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
    PayslipValidatedError,
    PayslipNotFoundError,
    RestorePayslipInput,
)
from app.modules.payslips.domain.heures_sup import (
    quantites_heures_sup_conjoncturelles,
)
from app.modules.payslips.domain.primes_editees import (
    diff_primes,
    sans_marques_de_saisie,
)
from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.application.primes_editees import (
    appliquer_primes_editees,
    verifier_appartenance,
)
from app.modules.payslips.infrastructure.providers import (
    payslip_editor_provider,
    payslip_generator_provider,
)
from app.modules.payslips.infrastructure.readers import employee_statut_reader
from app.modules.notifications.application.employee_document_alerts import (
    NOTIFICATION_TYPE_PAYSLIP,
    notify_employee_new_document,
)
from app.modules.employees.application.service import enrich_employee_with_exit_context
from app.shared.domain.employment_rules import payslip_employment_period_block_reason
from app.shared.reprise_paie import raison_de_blocage_avant_bascule

_employee_repository = EmployeeRepository()
logger = logging.getLogger(__name__)

_PAYSLIP_MONTH_LABELS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _payslip_notification_label(year: int, month: int) -> str:
    if 1 <= month <= 12:
        return f"Bulletin de paie — {_PAYSLIP_MONTH_LABELS[month - 1]} {year}"
    return f"Bulletin de paie — {month:02d}/{year}"


def _notify_payslip_available(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> bool:
    """Notifie le salarié ; renvoie False en cas d'échec (l'appelant décide
    s'il pose le marqueur d'idempotence — jamais sur un échec, sinon le
    salarié n'est jamais notifié et jamais re-tenté)."""
    try:
        notify_employee_new_document(
            employee_id,
            company_id,
            _payslip_notification_label(year, month),
            page_path="payslips",
            notification_type=NOTIFICATION_TYPE_PAYSLIP,
        )
        return True
    except Exception as exc:
        logger.warning(
            "[doc_notif] Bulletin non notifié pour %s (%02d/%d): %s",
            employee_id,
            month,
            year,
            exc,
        )
        return False


def _periode_a_saisir(employee: dict[str, Any], year: int, month: int):
    """La période à saisir du salarié pour ce mois — mois civil ∪ fenêtre des variables."""
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periode_a_saisir,
    )

    return charger_periode_a_saisir(
        str(employee.get("company_id") or "").strip(), employee, year, month
    )


def _check_calendar_guard(
    employee: dict[str, Any], cmd: GeneratePayslipInput
) -> dict[str, Any] | None:
    """Garde « période à saisir incomplète ».

    Juge l'union du mois civil et de la fenêtre des variables — ce que lit le
    moteur — via `charger_periode_a_saisir`. Refuse (422) si un jour de la
    fenêtre manque, sauf `force_calendrier_incomplet` explicite (tracé, warning
    en réponse). Des jours manquants hors fenêtre (fin du mois civil après la
    fenêtre) ne bloquent pas et ne font pas d'alerte : c'est la règle de la
    société, vraie tous les mois, pas un problème à signaler.
    """
    from app.modules.schedules.application.periode_a_saisir_service import resume_api
    from app.modules.schedules.domain.periode_a_saisir import libelle_plages

    periode = _periode_a_saisir(employee, cmd.year, cmd.month)
    details = resume_api(periode)
    debut, fin = periode.fenetre
    if periode.statut != "a_saisir":
        return None
    bloquants = [j.jour for j in periode.bloquants]
    message = (
        f"{cmd.month:02d}/{cmd.year} — {len(bloquants)} jour(s) à saisir dans la fenêtre "
        f"des variables ({debut:%d/%m} → {fin:%d/%m}) : {libelle_plages(bloquants)}. "
        "Complétez le planning avant de générer, ou forcez explicitement la génération."
    )
    if not cmd.force_calendrier_incomplet:
        raise PayslipCalendarIncompleteError(message, details)
    logger.warning(
        "[generation] Calendrier %02d/%d incomplet pour l'employé %s (%s) : "
        "génération FORCÉE par %s (%s).",
        cmd.month,
        cmd.year,
        cmd.employee_id,
        libelle_plages(bloquants),
        cmd.requested_by or "inconnu",
        cmd.requested_by_name or "nom inconnu",
    )
    return {
        "code": "calendrier_incomplet_force",
        "message": (
            f"Généré malgré {len(bloquants)} jour(s) non saisis "
            f"({libelle_plages(bloquants)}) — forçage explicite."
        ),
        **details,
    }


def _fetch_existing_payslip(
    employee_id: str, year: int, month: int
) -> dict[str, Any] | None:
    """Bulletin existant de la période (statut + contenu), None sinon."""
    r = (
        supabase.table("payslips")
        .select("id, status, payslip_data, url, edit_history")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


#: Versions antérieures gardées dans `edit_history` avant écrasement.
VERSIONS_CONSERVEES = 10


def _archive_before_regeneration(
    existing: dict[str, Any], cmd: GeneratePayslipInput
) -> None:
    """Archive le bulletin validé AVANT que le générateur ne l'écrase.

    Même format que l'historique d'édition manuelle (payslip_editor) : la
    version précédente reste consultable et restaurable.
    """
    history = existing.get("edit_history") or []
    if not isinstance(history, list):
        history = []
    # F2 : si le générateur a échoué après une première archive, la
    # re-tentative repasse ici — ne pas empiler un doublon du même état.
    if history:
        derniere = history[-1]
        if (
            isinstance(derniere, dict)
            and derniere.get("action") == "regeneration"
            and derniere.get("previous_payslip_data") == existing.get("payslip_data")
            and derniere.get("previous_pdf_url") == existing.get("url")
        ):
            return
    history.append(
        {
            "version": len(history) + 1,
            "edited_at": datetime.now().isoformat(),
            "edited_by": cmd.requested_by,
            "edited_by_name": cmd.requested_by_name,
            "changes_summary": (
                "Régénération d'un bulletin validé (forçage explicite)"
                if existing.get("status") == "valide"
                else "Régénération d'un brouillon — version précédente conservée"
            ),
            "action": "regeneration",
            "previous_payslip_data": existing.get("payslip_data", {}),
            "previous_pdf_url": existing.get("url"),
        }
    )
    # Une campagne de backtest régénère le même bulletin des dizaines de fois :
    # sans plafond, `edit_history` enflerait indéfiniment. On garde les versions
    # les plus récentes, seules utiles pour revenir en arrière.
    supabase.table("payslips").update(
        {"edit_history": history[-VERSIONS_CONSERVEES:]}
    ).eq("id", existing["id"]).execute()


def _reset_payslip_flags_after_regeneration(payslip_id: str) -> None:
    """Après régénération forcée : le bulletin redevient un brouillon.

    Le statut « valide » portait sur l'ANCIEN contenu ; les acquittements
    d'alertes vivent dans payslip_data et sont déjà balayés par l'upsert du
    générateur. manually_edited est remis à False : les retouches manuelles
    ont été archivées, pas conservées.
    """
    supabase.table("payslips").update(
        {"status": "brouillon", "manually_edited": False}
    ).eq("id", payslip_id).execute()


def _check_validated_guard(
    cmd: GeneratePayslipInput,
) -> dict[str, Any] | None:
    """Garde « bulletin validé », et rend le bulletin existant s'il y en a un.

    La garde refuse (409) d'écraser un bulletin validé sans forçage explicite.
    Mais le bulletin est rendu **quel que soit son statut** : l'appelant doit
    l'archiver avant de le laisser réécrire, brouillon compris. Un brouillon
    écrasé sans copie est définitivement perdu — c'est ce qui est arrivé aux
    bulletins de Colorplast le 26/08/2026.
    """
    existing = _fetch_existing_payslip(cmd.employee_id, cmd.year, cmd.month)
    if not existing:
        return None
    if existing.get("status") != "valide":
        return existing
    if not cmd.regenerer_bulletin_valide:
        raise PayslipValidatedError(
            f"Un bulletin validé existe déjà pour {cmd.month:02d}/{cmd.year}. "
            "Le régénérer archivera la version validée et exigera une "
            "nouvelle validation."
        )
    logger.warning(
        "[generation] Bulletin validé %s (%02d/%d) régénéré par %s (%s) : "
        "version archivée, statut remis à brouillon.",
        existing.get("id"),
        cmd.month,
        cmd.year,
        cmd.requested_by or "inconnu",
        cmd.requested_by_name or "nom inconnu",
    )
    return existing


_STATUTS_PARTIS = ("parti", "sorti", "inactif")


def _sortie_dans_ou_apres_le_mois(employee: dict[str, Any], year: int, month: int) -> bool:
    brut = employee.get("exit_last_working_day") or employee.get("contract_end_date")
    if not brut:
        return False
    return str(brut)[:10] >= f"{year:04d}-{month:02d}-01"


def _raison_de_blocage_du_salarie(
    employee: dict[str, Any], year: int, month: int
) -> str | None:
    """Un parti garde le droit à son dernier bulletin.

    « Ce collaborateur n'est pas actif » refusait le solde de tout compte de
    Demory, sorti le 24/07 (retour Gaëlle 12/09). Si la sortie est datée dans
    le mois demandé ou après, seule la complétude de la fiche compte ; la
    garde de période, juste derrière, refuse toujours les mois postérieurs à
    la sortie. Sans date de sortie, le refus de statut reste entier.
    """
    statut = str(employee.get("employment_status") or "actif").lower()
    if statut in _STATUTS_PARTIS and _sortie_dans_ou_apres_le_mois(employee, year, month):
        manquants = missing_payroll_fields(employee)
        if manquants:
            return (
                "Impossible de générer un bulletin : fiche paie incomplète. "
                f"Manque : {', '.join(manquants)}."
            )
        return None
    return payroll_block_reason(employee)


def generate_payslip(cmd: GeneratePayslipInput) -> GeneratePayslipResult:
    """
    Génère un bulletin pour un employé / période.
    Logique applicative : récupère le statut employé (via port), choisit forfait jour ou heures,
    délègue au provider (services legacy).

    Gardes (lot 3 — génération sûre), côté serveur, jamais dans les générateurs :
    - calendrier du mois `a_saisir` → PayslipCalendarIncompleteError (422),
      sauf `force_calendrier_incomplet` explicite (tracé, warning en réponse).
    """
    employee = _employee_repository.get_by_id_only(cmd.employee_id)
    if not employee:
        raise PayslipNotFoundError("Employé non trouvé.")
    employee = enrich_employee_with_exit_context(employee)
    block_reason = _raison_de_blocage_du_salarie(employee, cmd.year, cmd.month)
    if block_reason:
        raise PayslipBadRequestError(block_reason)
    period_block_reason = payslip_employment_period_block_reason(
        employee, cmd.year, cmd.month
    )
    if period_block_reason:
        raise PayslipBadRequestError(period_block_reason)
    # Reprise de paie : un mois payé par le logiciel précédent est importé, pas
    # recalculé. Le refus est ici, côté serveur, jamais dans les générateurs.
    bascule_block_reason = raison_de_blocage_avant_bascule(
        employee.get("company_id"), cmd.year, cmd.month
    )
    if bascule_block_reason:
        raise PayslipBadRequestError(bascule_block_reason)

    calendar_warning = _check_calendar_guard(employee, cmd)
    bulletin_existant = _check_validated_guard(cmd)
    if bulletin_existant:
        _archive_before_regeneration(bulletin_existant, cmd)
    validated_existing = (
        bulletin_existant
        if (bulletin_existant or {}).get("status") == "valide"
        else None
    )

    statut = employee_statut_reader.get_employee_statut(cmd.employee_id)
    if is_forfait_jour(statut):
        result = payslip_generator_provider.generate_forfait(
            employee_id=cmd.employee_id,
            year=cmd.year,
            month=cmd.month,
        )
    else:
        result = payslip_generator_provider.generate_heures(
            employee_id=cmd.employee_id,
            year=cmd.year,
            month=cmd.month,
        )

    # Lot 3 : plus AUCUNE notification à la génération — le salarié n'est
    # prévenu qu'à la VALIDATION du bulletin (comparison_service), une fois.

    warnings: list[Any] = list(result.get("warnings") or [])
    if calendar_warning:
        warnings.append(calendar_warning)
    if validated_existing and str(result.get("status") or "") == "success":
        _reset_payslip_flags_after_regeneration(str(validated_existing["id"]))
        warnings.append(
            {
                "code": "bulletin_valide_regenere",
                "message": (
                    f"Le bulletin validé de {cmd.month:02d}/{cmd.year} a été "
                    "régénéré : ancienne version archivée, nouvelle version en "
                    "brouillon à revalider."
                ),
            }
        )

    return GeneratePayslipResult(
        status=result["status"],
        message=result["message"],
        download_url=result["download_url"],
        payslip_id=result.get("payslip_id"),
        warnings=warnings or None,
    )


def _fetch_payslip_status(payslip_id: str) -> dict[str, Any] | None:
    """Statut et origine du bulletin, pour les gardes qui n'ont que son id.

    `origine` vient de la migration de reprise (20260917090000). Tant qu'elle
    n'est pas appliquée partout, demander la colonne ferait échouer la lecture,
    donc la suppression et l'édition d'un bulletin : on retombe alors sur le
    statut seul, et la garde des bulletins importés ne s'applique simplement
    pas — la bascule de la société, elle, refuse déjà de les recalculer.
    """
    for colonnes in ("id, status, origine", "id, status"):
        try:
            r = (
                supabase.table("payslips")
                .select(colonnes)
                .eq("id", payslip_id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:  # noqa: BLE001 — colonne absente : on réessaie sans
            if "origine" not in colonnes:
                raise
            logger.warning(
                "Colonne payslips.origine absente (migration de reprise non appliquée) : "
                "lecture du statut seul. %s",
                exc,
            )
            continue
        return r.data if r and r.data else None
    return None


MESSAGE_BULLETIN_IMPORTE = (
    "Ce bulletin a été payé par le logiciel précédent et repris tel quel : il ne se "
    "modifie pas, ne se supprime pas et ne se recalcule pas."
)


def _refuser_si_importe(payslip_id: str) -> None:
    """Un bulletin repris à la bascule (origine « importe ») est intouchable : il ne
    pourrait pas être recalculé, et sa chaîne de cumuls fait foi."""
    existing = _fetch_payslip_status(payslip_id)
    if existing and str(existing.get("origine") or "") == "importe":
        raise PayslipBadRequestError(MESSAGE_BULLETIN_IMPORTE)


def delete_payslip(payslip_id: str) -> None:
    """
    Supprime un bulletin (BDD + storage) et déclenche recalc COR.

    Lot 3 : un bulletin VALIDÉ ne se supprime pas — sinon delete+regen
    contourne l'archive de la régénération forcée. Le protocole : régénérer
    en forçant (qui archive et repasse en brouillon), puis supprimer.
    """
    _refuser_si_importe(payslip_id)
    existing = _fetch_payslip_status(payslip_id)
    if existing and existing.get("status") == "valide":
        raise PayslipValidatedError(
            "Ce bulletin est validé : sa suppression directe est refusée. "
            "Régénérez-le en forçant (l'ancienne version sera archivée), "
            "puis supprimez le brouillon si nécessaire."
        )
    from app.modules.payslips.infrastructure.repository import payslip_repository

    payslip_repository.delete(payslip_id)


def _set_payslip_status_brouillon(payslip_id: str) -> None:
    """Repasse un bulletin en brouillon (contenu modifié → revalidation)."""
    supabase.table("payslips").update({"status": "brouillon"}).eq(
        "id", payslip_id
    ).execute()


def _etait_valide(payslip_id: str) -> bool:
    existing = _fetch_payslip_status(payslip_id)
    return bool(existing and existing.get("status") == "valide")


# Libellés des saisies posées quand une RH corrige les heures supplémentaires
# depuis le bulletin. Ils doivent rester reconnaissables par le générateur :
# « heures » + « sup », jamais « struct », et « 50 » uniquement sur le second
# palier (cf. `payslip_generator._is_heures_sup_conjoncturelle_input`).
LIBELLE_HS_DECLAREES = "Heures supplémentaires (corrigées au bulletin)"
LIBELLE_HS_DECLAREES_50 = (
    "Heures supplémentaires majorées à 50 % (corrigées au bulletin)"
)


def _fetch_payslip_for_recalc(payslip_id: str) -> dict[str, Any] | None:
    """Bulletin complet nécessaire au recalcul (données, salarié, période)."""
    r = (
        supabase.table("payslips")
        .select("id, employee_id, company_id, year, month, payslip_data")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def _remplacer_heures_sup_declarees(
    *,
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    heures_25: float,
    heures_50: float,
) -> None:
    """Pose les deux paliers d'heures supplémentaires comme saisies du mois.

    Les déclarations précédentes du même mois sont retirées d'abord : le moteur
    additionne toutes les lignes reconnues, en laisser une ancienne doublerait
    les heures. Les deux paliers sont toujours écrits ensemble, faute de quoi le
    palier omis retomberait à zéro (cf. `domain.heures_sup`).
    """
    from app.modules.payroll.documents.payslip_generator import (
        _is_heures_sup_conjoncturelle_input,
    )

    existantes = (
        supabase.table("monthly_inputs")
        .select("*")
        .match(
            {
                "employee_id": employee_id,
                "year": year,
                "month": month,
                "company_id": str(company_id),
            }
        )
        .execute()
    )
    for row in existantes.data or []:
        if _is_heures_sup_conjoncturelle_input(row):
            supabase.table("monthly_inputs").delete().eq("id", row["id"]).execute()
            logger.info(
                "[edition] HS déclarée remplacée (%s, %s/%s) : %s",
                employee_id,
                month,
                year,
                row.get("name"),
            )

    base = {
        "employee_id": employee_id,
        "company_id": str(company_id),
        "year": year,
        "month": month,
        "amount": 0,
        "is_socially_taxed": True,
        "is_taxable": True,
    }
    supabase.table("monthly_inputs").insert(
        [
            {**base, "name": LIBELLE_HS_DECLAREES, "payroll_quantity": heures_25},
            {**base, "name": LIBELLE_HS_DECLAREES_50, "payroll_quantity": heures_50},
        ]
    ).execute()


def _declarer_heures_sup_corrigees(
    cmd: EditPayslipInput, avant: dict[str, Any]
) -> bool:
    """Redéclare au moteur les heures supplémentaires corrigées sur le bulletin.

    Rend True si une déclaration a été écrite ; la régénération est faite une
    seule fois par `edit_payslip`, primes comprises. Corriger la quantité d'heures
    supplémentaires sur le bulletin ne changeait que le brut : cotisations et
    net restaient ceux du calcul d'origine, et le bulletin devenait incohérent
    sans que rien ne le signale. Le moteur sait reprendre ces heures depuis une
    saisie déclarée — c'est ce chemin qu'on emprunte, plutôt que de recalculer
    une seconde fois dans l'éditeur.

    Deux cas restent au simple enregistrement, parce que le moteur ne les
    appliquerait pas — écrire une déclaration qu'il ignore laisserait des
    saisies fantômes, en désaccord visible avec le bulletin :

    - **remise à zéro des deux paliers** : il n'y voit pas une déclaration et
      repasse au calendrier ;
    - **total inchangé** : il compare le total déclaré à celui du calendrier et
      ne bouge que s'ils diffèrent. Déplacer une heure d'un palier à l'autre
      (12 h + 3,5 h corrigé en 13 h + 2,5 h) le laisse donc immobile, alors que
      les taux diffèrent. L'écran ne l'annonce pas non plus.

    Ce second cas se corrige dans le calendrier du mois, pas ici.
    """
    heures_avant = quantites_heures_sup_conjoncturelles(avant.get("payslip_data"))
    heures_apres = quantites_heures_sup_conjoncturelles(cmd.payslip_data)
    if heures_apres == (0.0, 0.0):
        return False
    if abs(sum(heures_apres) - sum(heures_avant)) <= 0.001:
        return False

    _remplacer_heures_sup_declarees(
        employee_id=avant["employee_id"],
        company_id=avant["company_id"],
        year=avant["year"],
        month=avant["month"],
        heures_25=heures_apres[0],
        heures_50=heures_apres[1],
    )
    logger.info(
        "[edition] Heures supplémentaires corrigées au bulletin %s : %s -> %s.",
        cmd.payslip_id,
        heures_avant,
        heures_apres,
    )
    return True


def _regenerer(cmd: EditPayslipInput, avant: dict[str, Any]) -> str | None:
    """Recalcule le bulletin par le moteur ; rend le message d'erreur s'il échoue.

    Les variables du mois sont déjà écrites : elles sont la vérité. Un échec
    du moteur ne les défait pas, il est rendu pour que l'écran propose
    « Régénérer ».
    """
    try:
        generate_payslip(
            GeneratePayslipInput(
                employee_id=avant["employee_id"],
                year=avant["year"],
                month=avant["month"],
                # Le bulletin existe déjà : ces deux gardes ont été franchies à sa
                # première génération. Les réopposer bloquerait une correction.
                force_calendrier_incomplet=True,
                regenerer_bulletin_valide=True,
                requested_by=cmd.current_user_id,
                requested_by_name=cmd.current_user_name,
            )
        )
    except Exception as exc:  # noqa: BLE001 — l'erreur est rendue à l'écran
        logger.exception("[edition] Recalcul du bulletin %s impossible", cmd.payslip_id)
        return str(exc)
    return None


def edit_payslip(cmd: EditPayslipInput) -> dict[str, Any]:
    """Sauvegarde les modifications d'un bulletin. Délègue au provider legacy.

    Lot 3 : éditer un bulletin VALIDÉ le repasse en brouillon — le salarié
    ne doit jamais voir un contenu qui n'a pas été revalidé (l'éditeur
    conserve l'historique, le statut doit suivre le contenu).

    Corriger les heures supplémentaires, ou ajouter, corriger, retirer une
    prime saisie, déclenche en plus un recalcul complet par le moteur : sans
    lui, seul le brut suivait la correction et le bulletin repartait avec les
    bases, les cotisations, le net et les cumuls d'avant (spec 2026-09-23).
    """
    _refuser_si_importe(cmd.payslip_id)
    etait_valide = _etait_valide(cmd.payslip_id)
    avant = _fetch_payslip_for_recalc(cmd.payslip_id)
    diff = diff_primes(avant.get("payslip_data") if avant else None, cmd.payslip_data)
    periode = (
        {
            "employee_id": avant["employee_id"],
            "company_id": avant["company_id"],
            "year": avant["year"],
            "month": avant["month"],
        }
        if avant
        else None
    )
    # Avant d'enregistrer : une saisie d'une autre fiche ne doit laisser aucune trace.
    if periode and not diff.vide:
        verifier_appartenance(diff.ids_touches, **periode)

    result = payslip_editor_provider.save_edited(
        payslip_id=cmd.payslip_id,
        # Sans les marques « nouvelle saisie » : l'écart est déjà calculé, et un
        # échec du moteur ne doit pas faire recréer la prime au prochain
        # enregistrement.
        new_payslip_data=sans_marques_de_saisie(cmd.payslip_data),
        changes_summary=cmd.changes_summary,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
        pdf_notes=cmd.pdf_notes,
        internal_note=cmd.internal_note,
    )
    if etait_valide:
        _set_payslip_status_brouillon(cmd.payslip_id)
        logger.warning(
            "[edition] Bulletin validé %s modifié par %s : repassé en brouillon.",
            cmd.payslip_id,
            cmd.current_user_id,
        )
    if not avant:
        return result
    # Après l'enregistrement : l'historique garde ainsi trace de la saisie
    # avant que le moteur ne réécrive le bulletin. Une seule régénération,
    # heures sup et primes comprises.
    a_recalculer = _declarer_heures_sup_corrigees(cmd, avant)
    if not diff.vide:
        appliquer_primes_editees(diff, **periode)
        a_recalculer = True
    if a_recalculer:
        erreur = _regenerer(cmd, avant)
        if erreur:
            result = {**result, "recalcul_erreur": erreur}
    return result


def restore_payslip_version(cmd: RestorePayslipInput) -> dict[str, Any]:
    """Restaure une version d'un bulletin. Délègue au provider legacy.

    Même règle que l'édition : restaurer sur un bulletin validé le repasse
    en brouillon.
    """
    etait_valide = _etait_valide(cmd.payslip_id)
    result = payslip_editor_provider.restore_version(
        payslip_id=cmd.payslip_id,
        version=cmd.version,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
    )
    if etait_valide:
        _set_payslip_status_brouillon(cmd.payslip_id)
    return result
