"""
Commandes (use cases en écriture) du module payslips.

Logique applicative : décision forfait jour vs heures, délégation aux providers
(services legacy). Les routers n'appellent que ces commandes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.core.database import supabase
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.onboarding.domain.profile import (
    missing_payroll_fields,
    payroll_block_reason,
)
from app.shared.domain.pluriel import pluriel
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    GeneratePayslipResult,
    PayslipArretsIllisiblesError,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
    PayslipHeuresSurArretError,
    PayslipValidatedError,
    PayslipNotFoundError,
)
from app.modules.payslips.domain.historique import (
    AUTEUR_SYSTEME,
    chemin_pdf_de_version,
    pdfs_sortis,
    plafonner,
    prochaine_version,
)
from app.modules.payslips.application import effets_du_bulletin as effets
from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.infrastructure.providers import (
    payslip_generator_provider,
)
from app.modules.payslips.infrastructure.readers import employee_statut_reader
from app.modules.payroll.documents.verrou_generation import verrou_de_generation
from app.modules.notifications.application.employee_document_alerts import (
    NOTIFICATION_TYPE_PAYSLIP,
    notify_employee_new_document,
)
from app.modules.employees.application.service import enrich_employee_with_exit_context
from app.shared.domain.employment_rules import payslip_employment_period_block_reason
from app.shared.reprise_paie import raison_de_blocage_avant_bascule

if TYPE_CHECKING:
    from app.modules.schedules.domain.periode_a_saisir import PeriodeASaisir

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


def _prenom(employee: dict[str, Any]) -> str:
    return (
        str(employee.get("first_name") or "").strip()
        or str(employee.get("last_name") or "").strip()
        or "La personne"
    )


def _periode_a_saisir(employee: dict[str, Any], year: int, month: int):
    """La période à saisir du salarié pour ce mois — mois civil ∪ fenêtre des variables.

    Les arrêts validés sont exigés : sans eux, la garde des heures sur un jour
    d'arrêt laisserait passer un week-end d'arrêt sans rien dire.
    """
    from app.modules.schedules.application.periode_a_saisir_service import (
        ArretsIllisibles,
        charger_periode_a_saisir,
    )

    try:
        return charger_periode_a_saisir(
            str(employee.get("company_id") or "").strip(),
            employee,
            year,
            month,
            arrets_obligatoires=True,
        )
    except ArretsIllisibles as exc:
        logger.warning(
            "[generation] Arrêts validés illisibles pour l'employé %s : %s",
            employee.get("id"),
            exc,
        )
        raise PayslipArretsIllisiblesError(
            f"Les arrêts de {_prenom(employee)} n'ont pas pu être lus : impossible de "
            "vérifier les heures saisies pendant un arrêt. Réessayez dans un instant ; "
            "rien n'a été calculé."
        ) from exc


def _check_calendar_guard(
    employee: dict[str, Any], cmd: GeneratePayslipInput, periode: "PeriodeASaisir"
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
    from app.modules.schedules.domain.periode_a_saisir import libelle_plages, raisons_en_clair

    details = resume_api(periode)
    debut, fin = periode.fenetre
    if periode.statut != "a_saisir":
        return None
    bloquants = [j.jour for j in periode.bloquants]
    message = (
        f"{cmd.month:02d}/{cmd.year} — {pluriel(len(bloquants), 'jour')} à saisir dans la fenêtre "
        f"des variables ({debut:%d/%m} → {fin:%d/%m}) : {libelle_plages(bloquants)} "
        f"({raisons_en_clair(periode.bloquants)}). "
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
            f"Généré malgré {pluriel(len(bloquants), 'jour non saisi', 'jours non saisis')} "
            f"({libelle_plages(bloquants)}) — forçage explicite."
        ),
        **details,
    }


def _check_heures_sur_jour_d_arret(
    employee: dict[str, Any], periode: "PeriodeASaisir"
) -> None:
    """Garde « heures saisies un jour d'arrêt ou d'absence non travaillée ».

    Le moteur compte ces heures comme travaillées (souvent en heures sup) et
    n'y retient plus l'absence : 70,75 h sup à 50 % pour une salariée en arrêt
    tout septembre (30/09/2026). Refus (422) dès qu'un jour de la période à
    saisir — mois civil ∪ fenêtre des variables, dans les bornes du contrat —
    est dans ce cas. Aucun forçage : la seule sortie est une correction.
    Le bac à sable (`generate_en_bac_a_sable`) ne passe pas par ici.
    """
    from app.modules.schedules.domain.conflits_arret import message_de_refus

    conflits = getattr(periode, "conflits", ()) or ()
    if not conflits:
        return
    prenom = _prenom(employee)
    jours = [c.en_detail() for c in conflits]
    logger.info(
        "[generation] Refus heures_sur_jour_d_arret pour l'employé %s : %s",
        employee.get("id"),
        jours,
    )
    raise PayslipHeuresSurArretError(message_de_refus(prenom, conflits), {"jours": jours})


def _fetch_existing_payslip(
    employee_id: str, year: int, month: int
) -> dict[str, Any] | None:
    """Bulletin existant de la période (statut + contenu), None sinon."""
    r = (
        supabase.table("payslips")
        .select(
            "id, status, payslip_data, url, edit_history, pdf_notes, "
            "manually_edited, pdf_storage_path"
        )
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def archiver_version(
    existing: dict[str, Any],
    *,
    edited_by: str | None,
    edited_by_name: str | None,
    changes_summary: str,
    action: str,
) -> None:
    """Garde la version courante du bulletin (données et PDF) dans l'historique.

    Le PDF est copié sous le numéro de la version : le lien signé seul
    expirait au bout d'une heure. Au-delà du plafond, les versions les plus
    anciennes sortent de l'historique, et leurs PDF du stockage.
    """
    from app.modules.payslips.application.impression import archiver_pdf, supprimer_pdfs

    history = existing.get("edit_history") or []
    if not isinstance(history, list):
        history = []
    version = prochaine_version(history)
    chemin_pdf = (
        archiver_pdf(
            existing.get("pdf_storage_path"),
            chemin_pdf_de_version(str(existing["pdf_storage_path"]), version),
        )
        if existing.get("pdf_storage_path")
        else None
    )
    avant = [*history, {
        "version": version,
        "edited_at": datetime.now(timezone.utc).isoformat(),
        "edited_by": edited_by,
        "edited_by_name": edited_by_name or AUTEUR_SYSTEME,
        "changes_summary": changes_summary,
        "action": action,
        "previous_payslip_data": existing.get("payslip_data") or {},
        "previous_pdf_url": existing.get("url"),
        "pdf_storage_path": chemin_pdf,
    }]
    # Une campagne de backtest régénère le même bulletin des dizaines de fois :
    # sans plafond, `edit_history` enflerait indéfiniment. On garde les versions
    # les plus récentes, seules utiles pour revenir en arrière.
    garde = plafonner(avant)
    supabase.table("payslips").update({"edit_history": garde}).eq(
        "id", existing["id"]
    ).execute()
    supprimer_pdfs(pdfs_sortis(avant, garde))


def _archive_before_regeneration(
    existing: dict[str, Any], cmd: GeneratePayslipInput
) -> None:
    """Archive le bulletin AVANT que le générateur ne l'écrase.

    La version précédente reste consultable (données et PDF) et restaurable.
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
            and derniere.get("action") in ("regeneration", "correction")
            and derniere.get("previous_payslip_data") == existing.get("payslip_data")
            and derniere.get("previous_pdf_url") == existing.get("url")
        ):
            return
    archiver_version(
        existing,
        edited_by=cmd.requested_by,
        edited_by_name=cmd.requested_by_name,
        changes_summary=cmd.motif
        or (
            "Régénération d'un bulletin validé (forçage explicite)"
            if existing.get("status") == "valide"
            else "Régénération d'un brouillon — version précédente conservée"
        ),
        action="correction" if cmd.motif else "regeneration",
    )


def _apres_regeneration(existant: dict[str, Any]) -> None:
    """Ce que la régénération ne sait pas garder d'elle-même.

    - La note du PDF vit dans sa colonne, mais le générateur imprime le bulletin
      du moteur, qui ne la connaît pas : on réimprime le PDF avec elle.
    - Les retouches manuelles ont été archivées, pas conservées : le bulletin
      n'est plus « modifié à la main ».

    Jamais bloquant : le bulletin est déjà recalculé et enregistré.
    """
    payslip_id = str(existant["id"])
    try:
        if existant.get("manually_edited"):
            supabase.table("payslips").update({"manually_edited": False}).eq(
                "id", payslip_id
            ).execute()
        if existant.get("pdf_notes"):
            from app.modules.payslips.application.impression import reimprimer_bulletin

            reimprimer_bulletin(payslip_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Après régénération du bulletin %s : note ou marque non reprise.",
            payslip_id,
            exc_info=True,
        )


def _signaler_documents_de_sortie(employee: dict[str, Any], year: int, month: int) -> None:
    """Le solde de tout compte et l'attestation employeur reprennent les montants
    du bulletin ; calculé après eux, il les met « à revoir » sur le départ.

    Seulement pour un salarié qui part ou est parti. Jamais bloquant : le
    bulletin est déjà enregistré.
    """
    statut = str(employee.get("employment_status") or "").lower()
    if not employee.get("current_exit_id") and statut not in _STATUTS_PARTIS:
        return
    try:
        from app.modules.employee_exits.application import bulletin_recalcule

        bulletin_recalcule.signaler_bulletin_recalcule(
            str(employee["id"]), str(employee["company_id"]), year, month
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Documents de sortie de %s non signalés après le bulletin %02d/%d.",
            employee.get("id"),
            month,
            year,
            exc_info=True,
        )


def _conserver_avertissements_forces(
    payslip_id: str | None, avertissements: list[dict[str, Any]]
) -> None:
    """Garde sur le bulletin ce que le forçage a signalé.

    L'avertissement n'était que dans la réponse de génération : une fois le suivi
    fermé ou la page rechargée, la ligne du bulletin forcé ne portait plus aucune
    alerte. Clé propre (`avertissements_forces`), lue par la liste ; la prochaine
    génération réécrit `payslip_data` et l'efface avec lui.
    """
    if not payslip_id:
        return
    ligne = (
        supabase.table("payslips")
        .select("payslip_data")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    donnees = (ligne.data or {}).get("payslip_data") if ligne else None
    if not isinstance(donnees, dict):
        return
    supabase.table("payslips").update(
        {"payslip_data": {**donnees, "avertissements_forces": avertissements}}
    ).eq("id", payslip_id).execute()


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


# `en_sortie` : départ créé, pas encore clos. Sans lui, « Générer le bulletin
# de sortie », proposé juste après « Créer le départ », était refusé (02/10).
_STATUTS_PARTIS = ("parti", "sorti", "inactif", "en_sortie")


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
    salarié 086, sorti le 24/07 (retour Gaëlle 12/09). Si la sortie est datée dans
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


def salarie_generable(employee_id: str, year: int, month: int) -> dict[str, Any]:
    """Le salarié, si son bulletin du mois peut être (re)calculé ; lève sinon.

    Ces refus d'entrée valent aussi pour une correction : elle les oppose avant
    d'écrire la moindre variable du mois.
    """
    employee = _employee_repository.get_by_id_only(employee_id)
    if not employee:
        raise PayslipNotFoundError("Employé non trouvé.")
    employee = enrich_employee_with_exit_context(employee)
    block_reason = _raison_de_blocage_du_salarie(employee, year, month)
    if block_reason:
        raise PayslipBadRequestError(block_reason)
    period_block_reason = payslip_employment_period_block_reason(employee, year, month)
    if period_block_reason:
        raise PayslipBadRequestError(period_block_reason)
    # Reprise de paie : un mois payé par le logiciel précédent est importé, pas
    # recalculé. Le refus est ici, côté serveur, jamais dans les générateurs.
    bascule_block_reason = raison_de_blocage_avant_bascule(
        employee.get("company_id"), year, month
    )
    if bascule_block_reason:
        raise PayslipBadRequestError(bascule_block_reason)
    # Ce que le bulletin du mois a retenu (prêts…) doit pouvoir être défait avant
    # d'être refait : sinon, refus ici, avant la moindre écriture.
    effets.refuser_si_effets_non_defaisables(employee_id, year, month)
    return employee


def generate_payslip(cmd: GeneratePayslipInput) -> GeneratePayslipResult:
    """
    Génère un bulletin pour un employé / période.
    Logique applicative : récupère le statut employé (via port), choisit forfait jour ou heures,
    délègue au provider (services legacy).

    Gardes (lot 3 — génération sûre), côté serveur, jamais dans les générateurs :
    - heures saisies un jour d'arrêt ou d'absence non travaillée →
      PayslipHeuresSurArretError (422), sans forçage possible ;
    - calendrier du mois `a_saisir` → PayslipCalendarIncompleteError (422),
      sauf `force_calendrier_incomplet` explicite (tracé, warning en réponse).
    """
    employee = salarie_generable(cmd.employee_id, cmd.year, cmd.month)

    # Une seule génération à la fois pour ce salarié et ce mois : tout ce qui
    # écrit (archive, calcul, bulletin, cumuls) se fait sous le verrou.
    with verrou_de_generation(cmd.employee_id, cmd.year, cmd.month):
        return _generer_sous_verrou(cmd, employee)


def _generer_sous_verrou(
    cmd: GeneratePayslipInput, employee: dict[str, Any]
) -> GeneratePayslipResult:
    """Suite de `generate_payslip`, une fois les refus d'entrée passés et le verrou pris."""
    periode = _periode_a_saisir(employee, cmd.year, cmd.month)
    # D'abord le refus sans forçage : une génération forcée pour un calendrier
    # incomplet ne doit pas s'arrêter ensuite sur lui.
    _check_heures_sur_jour_d_arret(employee, periode)
    calendar_warning = _check_calendar_guard(employee, cmd, periode)
    bulletin_existant = _check_validated_guard(cmd)
    if bulletin_existant:
        _archive_before_regeneration(bulletin_existant, cmd)
    # Échéance de prêt, avance, CET, modulation : ce que l'ancien calcul a écrit
    # est défait, le nouveau le refait une seule fois.
    effets.defaire_effets_du_bulletin(
        cmd.employee_id,
        cmd.year,
        cmd.month,
        payslip_id=str(bulletin_existant["id"]) if bulletin_existant else None,
    )
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

    if bulletin_existant and str(result.get("status") or "") == "success":
        _apres_regeneration(bulletin_existant)
    if str(result.get("status") or "") == "success":
        _signaler_documents_de_sortie(employee, cmd.year, cmd.month)

    warnings: list[Any] = list(result.get("warnings") or [])
    if calendar_warning:
        warnings.append(calendar_warning)
        if str(result.get("status") or "") == "success":
            _conserver_avertissements_forces(result.get("payslip_id"), [calendar_warning])
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
        salaire_brut=result.get("salaire_brut"),
        net_a_payer=result.get("net_a_payer"),
        heures_sup=result.get("heures_sup"),
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


def delete_payslip(payslip_id: str) -> bool:
    """
    Supprime un bulletin (BDD + storage) et déclenche recalc COR.

    Lot 3 : un bulletin VALIDÉ ne se supprime pas — sinon delete+regen
    contourne l'archive de la régénération forcée. Le protocole : régénérer
    en forçant (qui archive et repasse en brouillon), puis supprimer.

    Faux si le bulletin n'existait déjà plus (supprimé depuis un autre écran).
    """
    _refuser_si_importe(payslip_id)
    existing = _fetch_payslip_status(payslip_id)
    if existing is None:
        return False
    if existing.get("status") == "valide":
        raise PayslipValidatedError(
            "Ce bulletin est validé : sa suppression directe est refusée. "
            "Régénérez-le en forçant (l'ancienne version sera archivée), "
            "puis supprimez le brouillon si nécessaire."
        )
    # L'échéance de prêt redevient due, l'avance se rouvre, les dépôts CET et les
    # heures créditées en modulation reviennent : le bulletin n'existera plus.
    effets.defaire_avant_suppression(payslip_id)
    from app.modules.payslips.infrastructure.repository import payslip_repository

    return payslip_repository.delete(payslip_id)


def _set_payslip_status_brouillon(payslip_id: str) -> None:
    """Repasse un bulletin en brouillon (contenu modifié → revalidation)."""
    supabase.table("payslips").update({"status": "brouillon"}).eq(
        "id", payslip_id
    ).execute()
