"""Refaire l'import d'un fichier déjà validé.

Le 03/10/2026, après la correction du lecteur (deux salariés sautés sur trois
relevés Cegid déjà validés), leurs heures ont été rattrapées par un script :
l'écran ne savait pas relire un fichier déjà importé sans tout réécrire. Ce
module porte les trois temps de la relecture :

1. **Le refus** : un fichier déjà importé (même empreinte) n'est pas relu sans
   qu'on le demande ; le refus nomme le lot précédent (date, qui, combien de
   jours) et propose « Refaire l'import de ce fichier ».
2. **La revue** : le fichier est relu avec le lecteur actuel ; la proposition
   porte le lot précédent et les jours corrigés à la main depuis
   (`domain.corrections_a_la_main`).
3. **L'enregistrement** : ces jours ne sont pas réécrits, la valeur du
   calendrier reste (pour reprendre celle du fichier, on la saisit au
   calendrier) ; le nouveau lot garde le lien vers l'ancien
   (`summary_json.previous_committed_batch_id`, comme l'import de planning).

Ce qu'a écrit un lot validé est son aperçu (`preview_json`) : la revue y
remplace les jours relus avant l'enregistrement (`appliquer_revue_au_lot`).
Mesuré sur la base de test le 03/10/2026 : les jours des trois relevés Comitech
validés le 01/10 sont, au centime, ceux du calendrier.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain.corrections_a_la_main import (
    Cle,
    CorrectionALaMain,
    ValeurJour,
    corrections_a_la_main,
    jours_du_calendrier_reel,
)
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    CorrectionALaMainImport,
    LotPrecedent,
    ReimportInfo,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee
from app.shared.domain.temps_local import en_heure_locale

CODE_DEJA_IMPORTE = "deja_importe"


# ----- Le lot précédent -----


def lot_precedent_du_fichier(company_id: str, file_hash: str) -> dict[str, Any] | None:
    """Le dernier lot validé qui a écrit ce fichier."""
    lots = timesheet_import_repository.lots_valides_du_fichier(company_id, file_hash)
    return lots[0] if lots else None


def _jours_ecrits_du_resume(summary: dict[str, Any]) -> int | None:
    valeur = summary.get("committed_days")
    try:
        return None if valeur is None else int(valeur)
    except (TypeError, ValueError):
        return None


def fiche_du_lot(lot: dict[str, Any], *, fichier: str | None = None) -> dict[str, Any]:
    """Ce que l'écran dit du lot précédent : quand, par qui, combien de jours."""
    return LotPrecedent(
        batch_id=str(lot["id"]),
        fichier=fichier,
        filename=lot.get("filename"),
        valide_le=lot.get("completed_at") or lot.get("updated_at"),
        valide_par=timesheet_import_repository.nom_utilisateur(lot.get("user_id")),
        jours_ecrits=_jours_ecrits_du_resume(lot.get("summary_json") or {}),
    ).model_dump()


def fichiers_deja_importes(
    company_id: str, fichiers: Sequence[tuple[str, str]]
) -> list[dict[str, Any]]:
    """`[{filename, file_hash, lot_precedent}]` des fichiers `(nom, empreinte)` déjà validés."""
    deja: list[dict[str, Any]] = []
    for filename, file_hash in fichiers:
        lot = lot_precedent_du_fichier(company_id, file_hash)
        if lot:
            deja.append(
                {
                    "filename": filename,
                    "file_hash": file_hash,
                    "lot_precedent": fiche_du_lot(lot, fichier=filename),
                }
            )
    return deja


def _quand(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        instant = datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    return en_heure_locale(instant).strftime("le %d/%m/%Y à %H:%M")


def _lot_en_clair(lot: dict[str, Any]) -> str:
    morceaux = [m for m in (_quand(lot.get("valide_le")),) if m]
    if lot.get("valide_par"):
        morceaux.append(f"par {lot['valide_par']}")
    return " ".join(morceaux)


def refus_deja_importe(deja: list[dict[str, Any]]) -> ScheduleAppError:
    """409 qui dit quand, par qui, et quoi faire ; le corps porte les lots précédents."""
    if len(deja) == 1:
        lot = deja[0]["lot_precedent"]
        quand = _lot_en_clair(lot)
        message = (
            f"« {deja[0]['filename']} » a déjà été importé"
            + (f" {quand}" if quand else "")
            + " : ses heures sont dans le calendrier. Pour corriger une journée, "
            "modifiez-la dans le calendrier ; pour relire tout le fichier avec le "
            "lecteur actuel, choisissez « Refaire l'import de ce fichier »."
        )
    else:
        detail = ", ".join(
            f"« {d['filename']} »"
            + (f" {_lot_en_clair(d['lot_precedent'])}" if _lot_en_clair(d["lot_precedent"]) else "")
            for d in deja
        )
        message = (
            f"{len(deja)} fichiers ont déjà été importés ({detail}) : leurs heures "
            "sont dans le calendrier. Pour corriger une journée, modifiez-la dans "
            "le calendrier ; pour les relire avec le lecteur actuel, choisissez "
            "« Refaire l'import de ces fichiers »."
        )
    return ScheduleAppError(
        "validation",
        message,
        status_code=409,
        detail={
            "code": CODE_DEJA_IMPORTE,
            "message": message,
            "fichiers": [
                {"filename": d["filename"], "lot_precedent": d["lot_precedent"]}
                for d in deja
            ],
        },
    )


def verifier_import(
    company_id: str,
    fichiers: Sequence[tuple[str, str]],
    *,
    refaire_import: bool,
) -> list[dict[str, Any]]:
    """Refuse un fichier déjà importé, sauf relecture demandée.

    Rend les fichiers déjà importés (vide pour un premier import) : la
    relecture en a besoin pour montrer les corrections faites depuis.
    """
    deja = fichiers_deja_importes(company_id, fichiers)
    if deja and not refaire_import:
        raise refus_deja_importe(deja)
    return deja


# ----- Ce qu'a écrit un lot validé -----


def _cle_jour(employee_id: str, jour: dict[str, Any], annee: int, mois: int) -> Cle | None:
    try:
        numero = int(jour.get("jour"))
        return (
            str(employee_id),
            int(jour.get("year") or annee),
            int(jour.get("month") or mois),
            numero,
        )
    except (TypeError, ValueError):
        return None


def _valeur(jour: dict[str, Any]) -> ValeurJour:
    heures = jour.get("heures")
    return ValeurJour(
        heures=None if heures is None else float(heures), type=jour.get("type")
    )


def _cles_gardees(summary: dict[str, Any]) -> set[Cle]:
    cles: set[Cle] = set()
    for c in summary.get("corrections_gardees") or []:
        try:
            cles.add((str(c["employee_id"]), int(c["annee"]), int(c["mois"]), int(c["jour"])))
        except (KeyError, TypeError, ValueError):
            continue
    return cles


def jours_ecrits_par_lot(lot: dict[str, Any]) -> dict[Cle, ValeurJour]:
    """Les jours réels qu'un lot validé a écrits au calendrier.

    Son aperçu relu (ou ses groupes de mois pour un tableur sur plusieurs mois),
    moins les salariés laissés hors de l'enregistrement, les lignes non
    identifiées et les corrections à la main qu'il a gardées.
    """
    summary = lot.get("summary_json") or {}
    preview = lot.get("preview_json") or {}
    if summary.get("multi_month") and summary.get("month_groups"):
        groupes = [
            (int(g["year"]), int(g["month"]), g.get("employees") or [])
            for g in summary["month_groups"]
        ]
        retenus = None
    else:
        groupes = [
            (int(preview.get("year") or 0), int(preview.get("month") or 0), preview.get("employees") or [])
        ]
        retenus = (summary.get("commit_request") or {}).get("employee_ids") or None
    gardees = _cles_gardees(summary)

    ecrits: dict[Cle, ValeurJour] = {}
    for annee, mois, employes in groupes:
        for emp in employes:
            employee_id = emp.get("employee_id")
            if not employee_id or emp.get("review_status") == "error":
                continue
            if retenus is not None and str(employee_id) not in {str(e) for e in retenus}:
                continue
            for jour in emp.get("days") or []:
                if (jour.get("nature") or "reel") != "reel":
                    continue
                cle = _cle_jour(employee_id, jour, annee, mois)
                if cle is not None and cle not in gardees:
                    ecrits[cle] = _valeur(jour)
    return ecrits


def _jours_ecrits_par_lots(lots: Iterable[dict[str, Any]]) -> dict[Cle, ValeurJour]:
    """Plusieurs lots précédents (import groupé) : le plus récent l'emporte."""
    ecrits: dict[Cle, ValeurJour] = {}
    for lot in sorted(lots, key=lambda x: str(x.get("completed_at") or "")):
        ecrits.update(jours_ecrits_par_lot(lot))
    return ecrits


def _lots(company_id: str, batch_ids: Iterable[str]) -> list[dict[str, Any]]:
    lots = []
    for batch_id in dict.fromkeys(str(b) for b in batch_ids if b):
        lot = timesheet_import_repository.get_batch(batch_id, company_id=company_id)
        if lot:
            lots.append(lot)
    return lots


def _calendrier_reel(
    employee_ids: Iterable[str], annee: int, mois: int
) -> dict[Cle, ValeurJour]:
    rows = schedule_repository.list_schedules_for_employees(
        sorted(set(employee_ids)), annee, mois
    )
    return _calendrier_reel_des_lignes(rows, annee, mois)


def _calendrier_reel_des_lignes(
    rows: dict[str, dict[str, Any]], annee: int, mois: int
) -> dict[Cle, ValeurJour]:
    en_base: dict[Cle, ValeurJour] = {}
    for employee_id, row in (rows or {}).items():
        reel = ((row or {}).get("actual_hours") or {}).get("calendrier_reel") or []
        en_base.update(jours_du_calendrier_reel(str(employee_id), annee, mois, reel))
    return en_base


# ----- La revue -----


def _jours_reel_de_la_proposition(
    proposal: AiCalendarProposalResponse,
) -> dict[Cle, ValeurJour]:
    jours: dict[Cle, ValeurJour] = {}
    for emp in proposal.employees:
        if not emp.employee_id or emp.review_status == "error":
            continue
        for d in emp.days:
            if d.nature != "reel":
                continue
            cle = (
                str(emp.employee_id),
                int(d.year or proposal.year),
                int(d.month or proposal.month),
                int(d.jour),
            )
            jours[cle] = ValeurJour(heures=d.heures, type=d.type)
    return jours


def _vers_schema(c: CorrectionALaMain) -> CorrectionALaMainImport:
    return CorrectionALaMainImport.model_validate(c.to_dict())


def _nom_normalise(nom: str | None) -> str:
    return " ".join((nom or "").split()).casefold()


def reappliquer_associations(
    proposal: AiCalendarProposalResponse,
    lots: Iterable[dict[str, Any]],
    roster: Sequence[Any] | None = None,
) -> tuple[AiCalendarProposalResponse, list[str]]:
    """Les lignes non reconnues reprennent le salarié associé à la main au lot précédent.

    Même société (les lots sont ceux du fichier de cette société), même nom lu.
    Un nom associé à deux salariés différents n'est pas deviné, et un salarié
    déjà porté par une autre ligne n'est pas pris.
    """
    connus: dict[str, set[tuple[str, str | None]]] = {}
    for lot in lots:
        for ligne in (lot.get("preview_json") or {}).get("employees") or []:
            nom = _nom_normalise(ligne.get("raw_name"))
            if nom and ligne.get("employee_id"):
                connus.setdefault(nom, set()).add(
                    (str(ligne["employee_id"]), ligne.get("matched_name"))
                )
    # Le lot validé ne garde pas le nom du salarié associé à la main : on le prend au roster.
    noms_roster = {
        str(r.id): f"{r.first_name} {r.last_name}".strip() for r in (roster or [])
    }
    pris = {e.employee_id for e in proposal.employees if e.employee_id}
    reprises: list[str] = []
    lignes = []
    for ligne in proposal.employees:
        candidats = connus.get(_nom_normalise(ligne.raw_name), set())
        ids = {c[0] for c in candidats}
        if not ligne.employee_id and len(ids) == 1 and next(iter(ids)) not in pris:
            eid = next(iter(ids))
            nom_affiche = noms_roster.get(eid) or next((c[1] for c in candidats if c[1]), None)
            pris.add(eid)
            reprises.append(ligne.raw_name)
            ligne = ligne.model_copy(
                update={
                    "employee_id": eid,
                    "matched_name": nom_affiche,
                    "match_confidence": "high",
                    "review_status": "ok" if ligne.days else "empty",
                }
            )
        lignes.append(ligne)
    if not reprises:
        return proposal, []
    from app.modules.schedules.application.ai_fill import _compute_review_summary

    return (
        proposal.model_copy(
            update={
                "employees": lignes,
                "review_summary": _compute_review_summary(lignes),
                "roster_not_in_document_count": max(
                    0, (proposal.roster_not_in_document_count or 0) - len(reprises)
                ),
            }
        ),
        reprises,
    )


def annoter_reimport(
    company_id: str,
    proposal: AiCalendarProposalResponse,
    deja: list[dict[str, Any]],
    roster: Sequence[Any] | None = None,
) -> tuple[AiCalendarProposalResponse, dict[str, Any]]:
    """La relecture porte le lot précédent et les jours corrigés à la main depuis.

    Rend aussi le résumé à poser sur le nouveau lot : le lien vers l'ancien et
    les empreintes, que l'enregistrement relira pour retrouver le dernier lot
    validé de chaque fichier.
    """
    ids_precedents = [d["lot_precedent"]["batch_id"] for d in deja]
    proposal, associations_reprises = reappliquer_associations(
        proposal, _lots(company_id, ids_precedents), roster
    )
    ecrits = _jours_ecrits_par_lots(_lots(company_id, ids_precedents))
    jours = _jours_reel_de_la_proposition(proposal)

    par_mois: dict[tuple[int, int], set[str]] = {}
    for employee_id, annee, mois, _ in jours:
        par_mois.setdefault((annee, mois), set()).add(employee_id)
    en_base: dict[Cle, ValeurJour] = {}
    for (annee, mois), employee_ids in sorted(par_mois.items()):
        en_base.update(_calendrier_reel(employee_ids, annee, mois))

    corrections = corrections_a_la_main(jours, ecrits, en_base)
    annotee = proposal.model_copy(
        update={
            "reimport": ReimportInfo(
                lots_precedents=[LotPrecedent(**d["lot_precedent"]) for d in deja],
                corrections_a_la_main=[_vers_schema(c) for c in corrections],
                associations_reprises=associations_reprises,
            )
        }
    )
    resume = {
        "reimport": True,
        "previous_committed_batch_id": ids_precedents[0] if ids_precedents else None,
        "reimport_fichiers": [
            {
                "filename": d["filename"],
                "file_hash": d["file_hash"],
                "previous_committed_batch_id": d["lot_precedent"]["batch_id"],
            }
            for d in deja
        ],
    }
    return annotee, resume


# ----- L'enregistrement -----


def _lots_precedents_du_resume(summary: dict[str, Any]) -> list[str]:
    """Les lots précédents connus à la relecture (un par fichier relu)."""
    ids = [
        str(f["previous_committed_batch_id"])
        for f in summary.get("reimport_fichiers") or []
        if f.get("previous_committed_batch_id")
    ]
    if not ids and summary.get("previous_committed_batch_id"):
        ids.append(str(summary["previous_committed_batch_id"]))
    return list(dict.fromkeys(ids))


@dataclass
class GardeDesCorrections:
    """À l'enregistrement d'une relecture : les jours corrigés à la main ne sont
    pas réécrits, la valeur du calendrier reste.

    Recalculé contre le calendrier du moment (il a pu bouger depuis la revue) et
    contre les jours réellement envoyés (une ligne réassociée à la revue).
    """

    ecrits: dict[Cle, ValeurJour]
    gardees: list[CorrectionALaMain] = field(default_factory=list)

    @classmethod
    def du_lot(cls, batch: dict[str, Any], *, company_id: str) -> GardeDesCorrections | None:
        summary = batch.get("summary_json") or {}
        if not summary.get("reimport"):
            return None
        lots = _lots(company_id, _lots_precedents_du_resume(summary))
        return cls(ecrits=_jours_ecrits_par_lots(lots))

    def filtrer(
        self,
        employees: list[PersistTimesheetEmployee],
        annee: int,
        mois: int,
        existing_rows: dict[str, dict[str, Any]],
    ) -> list[PersistTimesheetEmployee]:
        """Les salariés du mois, sans leurs jours réels corrigés à la main."""
        jours: dict[Cle, ValeurJour] = {}
        for emp in employees:
            for d in emp.days:
                if d.nature == "reel":
                    jours[(emp.employee_id, annee, mois, int(d.jour))] = ValeurJour(
                        heures=d.heures, type=d.type
                    )
        gardees = corrections_a_la_main(
            jours, self.ecrits, _calendrier_reel_des_lignes(existing_rows, annee, mois)
        )
        self.gardees.extend(gardees)
        a_garder = {c.cle for c in gardees}
        restants: list[PersistTimesheetEmployee] = []
        for emp in employees:
            days = [
                d
                for d in emp.days
                if not (
                    d.nature == "reel"
                    and (emp.employee_id, annee, mois, int(d.jour)) in a_garder
                )
            ]
            if days:
                restants.append(PersistTimesheetEmployee(employee_id=emp.employee_id, days=days))
        return restants

    def resume(self) -> dict[str, Any]:
        return {"corrections_gardees": [c.to_dict() for c in self.gardees]}


__all__ = [
    "CODE_DEJA_IMPORTE",
    "GardeDesCorrections",
    "annoter_reimport",
    "fiche_du_lot",
    "fichiers_deja_importes",
    "jours_ecrits_par_lot",
    "lot_precedent_du_fichier",
    "refus_deja_importe",
    "verifier_import",
]
