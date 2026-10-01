"""Annoter les bulletins périmés et assembler l'empreinte depuis les lectures.

Les lectures sont groupées par salarié (calendriers de la fenêtre, absences,
saisies des mois demandés, fiche, société, notes de frais) — pas une requête
par bulletin. L'empreinte à la génération réutilise les mêmes pièces déjà
lues par le générateur, sans aller relire la base.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from app.modules.payroll.application.compensation_semaines import CLE_REGLAGE
from app.modules.payroll.domain.empreinte_entrees import (
    construire_entrees,
    empreinte,
    etat_a_recalculer,
    mois_de_la_fenetre,
    poser_empreinte,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import (
    LecturesEmpreinte,
    lire_lectures_salarie,
)

_CLES_FICHE = (
    "salaire_de_base",
    "classification_conventionnelle",
    "duree_hebdomadaire",
    "is_temps_partiel",
    "statut",
    "is_forfait_jour",
    "hire_date",
    "seniority_reference_date",
    "prior_service_months",
    "contract_end_date",
    "contract_type",
    "elements_variables",
    "avantages_en_nature",
    "specificites_paie",
    "job_title",
    "date_conclusion_contrat",
    "date_debut_execution",
    "exit_last_working_day",
)

_CLES_SAISIE = (
    "name",
    "amount",
    "catalog_prime_id",
    "is_socially_taxed",
    "is_taxable",
    "payroll_quantity",
    "sur_le_net",
    "export_code",
    "quantity_kind",
    "situation_repas",
    "description",
    "participation_campaign_id",
    "participation_bulletin_id",
)


def _extrait(source: Mapping[str, Any] | None, cles: Sequence[str]) -> dict[str, Any]:
    row = source or {}
    return {cle: row.get(cle) for cle in cles}


def _iso_jour(entree: Mapping[str, Any], year: int, month: int) -> str | None:
    try:
        jour = int(entree["jour"])
        annee = int(entree.get("annee") or year)
        mois = int(entree.get("mois") or month)
        return date(annee, mois, jour).isoformat()
    except (KeyError, TypeError, ValueError):
        return None


def _liste_prevu(row: Mapping[str, Any] | None) -> list:
    bloc = (row or {}).get("planned_calendar") or {}
    if not isinstance(bloc, Mapping):
        return []
    jours = bloc.get("calendrier_prevu") or []
    return list(jours) if isinstance(jours, list) else []


def _liste_reel(row: Mapping[str, Any] | None) -> list:
    bloc = (row or {}).get("actual_hours") or {}
    if not isinstance(bloc, Mapping):
        return []
    jours = bloc.get("calendrier_reel") or []
    return list(jours) if isinstance(jours, list) else []


def _source_absence_par_date(absences: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    par_date: dict[str, str] = {}
    for row in absences:
        type_demande = str(row.get("type") or "")
        for jour in row.get("selected_days") or []:
            iso = str(jour)[:10]
            if par_date.get(iso) != "conge_paye":
                par_date[iso] = type_demande
    return par_date


def _avec_source_absence(
    prevu: list, absences: Iterable[Mapping[str, Any]], year: int, month: int
) -> list[dict[str, Any]]:
    source = _source_absence_par_date(absences)
    sorties: list[dict[str, Any]] = []
    for entree in prevu:
        if not isinstance(entree, Mapping):
            continue
        copie = dict(entree)
        if copie.get("type") == "conges_payes":
            iso = _iso_jour(copie, year, month)
            if iso and iso in source:
                copie["source_absence"] = source[iso]
        sorties.append(copie)
    return sorties


def _absences_de_la_fenetre(
    absences: Iterable[Mapping[str, Any]], year: int, month: int
) -> list[dict[str, Any]]:
    premier, _, dernier = mois_de_la_fenetre(year, month)
    debut = date(premier[0], premier[1], 1).isoformat()
    fin = date(
        dernier[0], dernier[1], calendar.monthrange(dernier[0], dernier[1])[1]
    ).isoformat()
    retenues: list[dict[str, Any]] = []
    for row in absences:
        jours = [str(j)[:10] for j in (row.get("selected_days") or [])]
        if any(debut <= j <= fin for j in jours):
            retenues.append({"type": row.get("type"), "selected_days": jours})
    return retenues


def _calendriers_de_la_fenetre(
    calendriers: Mapping[tuple[int, int], Mapping[str, Any]],
    absences: Iterable[Mapping[str, Any]],
    year: int,
    month: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for y, m in mois_de_la_fenetre(year, month):
        row = calendriers.get((y, m)) or {}
        out[f"{y:04d}-{m:02d}"] = {
            "prevu": _avec_source_absence(_liste_prevu(row), absences, y, m),
            "reel": [dict(e) for e in _liste_reel(row) if isinstance(e, Mapping)],
        }
    return out


def _notes_du_mois(notes: Iterable[Mapping[str, Any]], year: int, month: int) -> list[dict[str, Any]]:
    prefixe = f"{year:04d}-{month:02d}"
    retenues: list[dict[str, Any]] = []
    for note in notes:
        jour = str(note.get("date") or "")[:10]
        if jour.startswith(prefixe):
            retenues.append({"type": note.get("type"), "amount": note.get("amount"), "date": jour})
    return retenues


def _fenetre_pour_empreinte(
    company: Mapping[str, Any] | None,
    year: int,
    month: int,
    fenetre_variables: Mapping[str, Any] | None = None,
    surcharges_fenetre: Mapping[tuple[int, int], date] | None = None,
) -> dict[str, str]:
    """Fenêtre réellement utilisée : celle du générateur, ou la même règle + surcharge."""
    if fenetre_variables and fenetre_variables.get("debut") and fenetre_variables.get("fin"):
        return {
            "debut": str(fenetre_variables["debut"])[:10],
            "fin": str(fenetre_variables["fin"])[:10],
        }
    from app.modules.payroll.application.periode_variables_service import (
        _bornes_regle,
        _mois_precedent,
    )
    from app.shared.domain.periode_variables import resoudre_fenetre

    societe = company or {}
    bornes = _bornes_regle(societe, year, month)
    annee_prec, mois_prec = _mois_precedent(year, month)
    surcharges = surcharges_fenetre or {}
    fin_precedente = surcharges.get((annee_prec, mois_prec))
    if fin_precedente is None:
        fin_precedente = _bornes_regle(societe, annee_prec, mois_prec)[1]
    fenetre = resoudre_fenetre(
        bornes_regle=bornes,
        fin_mois_precedent=fin_precedente,
        surcharge=surcharges.get((year, month)),
    )
    return {"debut": fenetre.debut.isoformat(), "fin": fenetre.fin.isoformat()}


def parametres_societe_pour_empreinte(company: Mapping[str, Any] | None) -> dict[str, Any]:
    societe = company or {}
    reglages = societe.get("settings") or {}
    if not isinstance(reglages, Mapping):
        reglages = {}
    return {
        "idcc": societe.get("idcc"),
        "effectif": societe.get("effectif"),
        "taux_at_mp": societe.get("taux_at_mp"),
        "taux_vm": societe.get("taux_vm"),
        "taux_fnal": societe.get("taux_fnal"),
        "paie_jour_de_fin": societe.get("paie_jour_de_fin"),
        "paie_occurrence": societe.get("paie_occurrence"),
        "paniers_non_soumis_dans_mns": reglages.get("paniers_non_soumis_dans_mns"),
        "jour_solidarite": reglages.get("jour_solidarite"),
        "date_paiement": reglages.get("date_paiement"),
        CLE_REGLAGE: reglages.get(CLE_REGLAGE) is True,
    }


def entrees_depuis_lectures(
    *,
    year: int,
    month: int,
    calendriers: Mapping[tuple[int, int], Mapping[str, Any]],
    absences: Iterable[Mapping[str, Any]],
    saisies: Iterable[Mapping[str, Any]],
    employee: Mapping[str, Any],
    company: Mapping[str, Any] | None,
    notes_de_frais: Iterable[Mapping[str, Any]] | None = None,
    fenetre_variables: Mapping[str, Any] | None = None,
    surcharges_fenetre: Mapping[tuple[int, int], date] | None = None,
) -> dict[str, Any]:
    """Pièces déjà lues → dictionnaire d'empreinte. Sans I/O."""
    absences_list = list(absences)
    return construire_entrees(
        {
            "calendriers": _calendriers_de_la_fenetre(calendriers, absences_list, year, month),
            "absences": _absences_de_la_fenetre(absences_list, year, month),
            "saisies": [_extrait(s, _CLES_SAISIE) for s in saisies],
            "fiche": _extrait(employee, _CLES_FICHE),
            "notes_de_frais": _notes_du_mois(notes_de_frais or [], year, month),
            "parametres_societe": parametres_societe_pour_empreinte(company),
            "fenetre_variables": _fenetre_pour_empreinte(
                company, year, month, fenetre_variables, surcharges_fenetre
            ),
        }
    )


def empreinte_des_lectures(**kwargs: Any) -> str:
    return empreinte(entrees_depuis_lectures(**kwargs))


def poser_empreinte_depuis_lectures(payslip_data: Mapping[str, Any] | None, **kwargs: Any) -> dict[str, Any]:
    """Pose l'empreinte sur le JSON du bulletin, sans muter l'original."""
    return poser_empreinte(payslip_data, empreinte_des_lectures(**kwargs))


def _entrees_depuis_cache(lectures: LecturesEmpreinte, year: int, month: int) -> dict[str, Any]:
    return entrees_depuis_lectures(
        year=year,
        month=month,
        calendriers=lectures.calendriers,
        absences=lectures.absences,
        saisies=lectures.saisies_par_mois.get((year, month), []),
        employee=lectures.employee,
        company=lectures.company,
        notes_de_frais=lectures.notes_de_frais,
        surcharges_fenetre=lectures.surcharges_fenetre,
    )


def empreinte_actuelle(employee_id: str, year: int, month: int) -> str | None:
    """Empreinte des lectures actuelles ; None si le salarié est illisible."""
    lectures = lire_lectures_salarie(employee_id, [(year, month)])
    if lectures is None:
        return None
    return empreinte(_entrees_depuis_cache(lectures, year, month))


def annoter_a_recalculer(employee_id: str, lignes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ajoute `a_recalculer` (true / false / null) à chaque ligne de la liste RH.

    Un bulletin repris n'est pas recalculable : `null`, comme un bulletin
    d'avant ce changement (sans empreinte). Une seule lecture groupée pour
    tous les mois du salarié.
    """
    if not lignes:
        return lignes
    periodes = sorted({(int(l["year"]), int(l["month"])) for l in lignes})
    lectures = lire_lectures_salarie(employee_id, periodes)
    annotées: list[dict[str, Any]] = []
    for ligne in lignes:
        copie = dict(ligne)
        hash_stockee = copie.pop("empreinte_entrees", None)
        if not isinstance(hash_stockee, str) or not hash_stockee:
            hash_stockee = None
        if str(copie.get("origine") or "calcule") == "importe":
            copie["a_recalculer"] = None
            annotées.append(copie)
            continue
        if lectures is None:
            copie["a_recalculer"] = None
            annotées.append(copie)
            continue
        try:
            actuelle = empreinte(
                _entrees_depuis_cache(lectures, int(copie["year"]), int(copie["month"]))
            )
        except (KeyError, TypeError, ValueError):
            copie["a_recalculer"] = None
            annotées.append(copie)
            continue
        copie["a_recalculer"] = etat_a_recalculer(hash_stockee, actuelle)
        annotées.append(copie)
    return annotées
