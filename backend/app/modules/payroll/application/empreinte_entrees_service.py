"""Annoter les bulletins périmés et assembler l'empreinte depuis les lectures.

Les lectures sont groupées par salarié (calendriers de la fenêtre, absences,
saisies des mois demandés, fiche, société, notes de frais) — pas une requête
par bulletin. L'empreinte à la génération réutilise les mêmes pièces déjà
lues par le générateur, sans aller relire la base.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from app.modules.payroll.application.compensation_semaines import CLE_REGLAGE
from app.modules.payroll.domain.empreinte_entrees import (
    a_recalculer,
    construire_entrees,
    empreinte,
    empreinte_cumuls,
    etat_a_recalculer,
    mois_de_la_fenetre,
    poser_empreinte,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import (
    LecturesEmpreinte,
    lire_empreintes_des_bulletins,
    lire_lectures_salarie,
)
from app.shared.domain.employment_rules import premier_mois_du_contrat

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
    parametres = {
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
    # Seulement s'il est réglé : une clé de plus pour tous périmerait tous les
    # bulletins déjà générés.
    if reglages.get("taux_assurance_chomage") is not None:
        parametres["taux_assurance_chomage"] = reglages.get("taux_assurance_chomage")
    return parametres


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


def _cumuls_precedents_changes(
    lectures: LecturesEmpreinte, year: int, month: int, stockee: str | None
) -> bool | None:
    """Les cumuls du mois d'avant ont-ils changé depuis le calcul de ce bulletin ?

    false au premier mois d'un contrat : le bulletin repart de zéro, il ne dépend
    pas du mois d'avant (contrats successifs). None sans empreinte stockée.
    """
    if premier_mois_du_contrat(lectures.employee, year, month):
        return False
    if not stockee:
        return None
    precedent = mois_de_la_fenetre(year, month)[0]
    actuels = (lectures.calendriers.get(precedent) or {}).get("cumuls")
    return stockee != empreinte_cumuls(actuels)


@dataclass(frozen=True)
class EtatDuBulletin:
    """Un bulletin calculé face aux lectures actuelles."""

    empreinte_actuelle: str | None = None
    #: Calendrier, absences, saisies, fiche… changés depuis le calcul.
    entrees_changees: bool | None = None
    #: Ses cumuls de départ (ceux du mois d'avant) : changés, inchangés ou sans
    #: objet (premier mois du contrat), inconnus (bulletin d'avant l'empreinte).
    cumuls_precedents_changes: bool | None = None
    #: Le mois de la chaîne dont les cumuls de départ ont changé depuis son
    #: calcul : ce bulletin, ou un mois d'avant encore à recalculer. Corriger
    #: septembre en novembre laisse octobre périmé, donc novembre aussi.
    cascade_depuis: tuple[int, int] | None = None

    @property
    def a_recalculer(self) -> bool | None:
        if self.cascade_depuis is not None:
            return True
        return a_recalculer(self.entrees_changees, self.cumuls_precedents_changes)


def _hash_ou_none(valeur: Any) -> str | None:
    return valeur if isinstance(valeur, str) and valeur else None


def _etats_par_mois(
    lectures: LecturesEmpreinte | None, lignes: Iterable[Mapping[str, Any]]
) -> dict[tuple[int, int], EtatDuBulletin]:
    """L'état de chaque bulletin, mois après mois, la cascade suivant la chaîne.

    La cascade ne suit que les cumuls : un mois d'avant aux entrées changées
    (une fiche modifiée périme tous les mois) ne périme pas celui-ci tant
    qu'il n'a pas été recalculé. Elle s'arrête à un bulletin repris, à un mois
    sans bulletin et au premier mois d'un contrat.
    """
    etats: dict[tuple[int, int], EtatDuBulletin] = {}
    for ligne in sorted(lignes, key=lambda l: (int(l["year"]), int(l["month"]))):
        periode = (int(ligne["year"]), int(ligne["month"]))
        if lectures is None or str(ligne.get("origine") or "calcule") == "importe":
            etats[periode] = EtatDuBulletin()
            continue
        annee, mois = periode
        try:
            actuelle = empreinte(_entrees_depuis_cache(lectures, annee, mois))
            propres = _cumuls_precedents_changes(
                lectures, annee, mois, _hash_ou_none(ligne.get("empreinte_cumuls_precedents"))
            )
        except (KeyError, TypeError, ValueError):
            etats[periode] = EtatDuBulletin()
            continue
        cascade = periode if propres else None
        if cascade is None and not premier_mois_du_contrat(lectures.employee, annee, mois):
            precedent = etats.get(mois_de_la_fenetre(annee, mois)[0])
            cascade = precedent.cascade_depuis if precedent else None
        etats[periode] = EtatDuBulletin(
            empreinte_actuelle=actuelle,
            entrees_changees=etat_a_recalculer(
                _hash_ou_none(ligne.get("empreinte_entrees")), actuelle
            ),
            cumuls_precedents_changes=propres,
            cascade_depuis=cascade,
        )
    return etats


#: Assez loin pour une correction tardive ; la chaîne s'arrête de toute façon
#: au premier mois repris ou sans bulletin.
MOIS_DE_CHAINE = 24


def etat_dans_la_chaine(employee_id: str, year: int, month: int) -> EtatDuBulletin | None:
    """L'état du bulletin de ce mois, cascade des mois d'avant comprise.

    Une lecture des empreintes des bulletins du salarié, une lecture groupée
    des entrées. None si le salarié ou ses bulletins sont illisibles.
    """
    borne = year * 12 + month
    lignes = [
        l
        for l in lire_empreintes_des_bulletins(employee_id)
        if borne - MOIS_DE_CHAINE <= int(l["year"]) * 12 + int(l["month"]) <= borne
    ]
    if not any((int(l["year"]), int(l["month"])) == (year, month) for l in lignes):
        return None
    periodes = sorted({(int(l["year"]), int(l["month"])) for l in lignes})
    lectures = lire_lectures_salarie(employee_id, periodes)
    if lectures is None:
        return None
    return _etats_par_mois(lectures, lignes).get((year, month))


def annoter_a_recalculer(employee_id: str, lignes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ajoute `a_recalculer` (true / false / null) à chaque ligne de la liste RH.

    Périmé quand ses entrées ont changé, ou quand un mois d'avant a été recalculé
    depuis (ses cumuls ne sont plus ceux du calcul, de proche en proche). Un
    bulletin repris n'est pas recalculable : `null`, comme un bulletin d'avant
    ce changement (sans empreinte). Une seule lecture groupée pour tous les
    mois du salarié.
    """
    if not lignes:
        return lignes
    periodes = sorted({(int(l["year"]), int(l["month"])) for l in lignes})
    lectures = lire_lectures_salarie(employee_id, periodes)
    try:
        etats = _etats_par_mois(lectures, lignes)
    except (KeyError, TypeError, ValueError):
        etats = {}
    annotées: list[dict[str, Any]] = []
    for ligne in lignes:
        copie = dict(ligne)
        copie.pop("empreinte_entrees", None)
        copie.pop("empreinte_cumuls_precedents", None)
        try:
            etat = etats.get((int(copie["year"]), int(copie["month"])))
        except (KeyError, TypeError, ValueError):
            etat = None
        copie["a_recalculer"] = etat.a_recalculer if etat else None
        annotées.append(copie)
    return annotées
