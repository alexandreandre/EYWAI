"""Annoter les bulletins périmés et assembler l'empreinte depuis les lectures.

Les lectures sont groupées par salarié (calendriers de la fenêtre, absences,
saisies des mois demandés, fiche, société, notes de frais, et les compléments :
mutuelles, départs, congés, salaire daté, réglages société) — pas une requête
par bulletin. L'empreinte à la génération réutilise les mêmes pièces déjà
lues par le générateur, sans aller relire la base ; seuls les compléments
sont relus, après le calcul, par les mêmes lectures que la liste.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Callable, Iterable, Mapping, Sequence

from app.shared.domain.effectif_seuils import effectif_retenu, palier_effectif
from app.shared.pas_taux import zone_du_code_postal
from app.modules.payroll.engine.baremes_loader import SEUIL_EFFECTIF_VERSEMENT_MOBILITE
from app.modules.payroll.application.compensation_semaines import CLE_REGLAGE
from app.modules.payroll.application.monthly_specificites import (
    resolve_monthly_specificites,
)
from app.modules.payroll.domain.empreinte_entrees import (
    MESSAGE_A_REGENERER,
    PARTIE_FICHE,
    a_recalculer,
    construire_entrees,
    ecart_au_centime,
    empreinte,
    empreinte_complementaire_valide,
    empreinte_cumuls,
    empreinte_partie,
    etat_a_recalculer,
    message_a_recalculer,
    message_mois_d_avant_a_recalculer,
    mois_de_la_fenetre,
    parties_changees,
    poser_empreinte,
    poser_empreinte_complementaire,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import (
    Complements,
    LecturesEmpreinte,
    lire_bulletin_enregistre,
    lire_complements,
    lire_empreintes_des_bulletins,
    lire_lectures_salarie,
    poser_empreintes_verifiees,
)
from app.shared.domain.employment_rules import (
    is_forfait_jour,
    mois_du_contrat_en_cours,
    premier_mois_du_contrat,
)

logger = logging.getLogger(__name__)

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


#: Clés de `specificites_paie` que seules la DSN (export et import) lisent :
#: les poser ou les corriger ne change aucun bulletin.
_SPECIFICITES_DSN_SEULE = frozenset({"affiliations_psc", "dsn_reprise"})


def _extrait(source: Mapping[str, Any] | None, cles: Sequence[str]) -> dict[str, Any]:
    row = source or {}
    return {cle: row.get(cle) for cle in cles}


def _fiche(employee: Mapping[str, Any] | None) -> dict[str, Any]:
    """La fiche hachée, sans les clés de `specificites_paie` propres à la DSN.

    Une fiche qui ne les porte pas est extraite telle quelle : son empreinte
    reste celle d'avant cette exclusion.
    """
    fiche = _extrait(employee, _CLES_FICHE)
    specificites = fiche.get("specificites_paie")
    if isinstance(specificites, Mapping) and _SPECIFICITES_DSN_SEULE & specificites.keys():
        fiche["specificites_paie"] = {
            cle: valeur
            for cle, valeur in specificites.items()
            if cle not in _SPECIFICITES_DSN_SEULE
        }
    return fiche


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


def parametres_societe_pour_empreinte(
    company: Mapping[str, Any] | None, annee: int
) -> dict[str, Any]:
    societe = company or {}
    reglages = societe.get("settings") or {}
    if not isinstance(reglages, Mapping):
        reglages = {}
    # L'effectif par palier : seul un seuil franchi change le bulletin. Sa
    # saisie pour l'année compte aussi (elle retire l'alerte du bulletin).
    effectif = effectif_retenu(societe, annee)
    parametres = {
        "idcc": societe.get("idcc"),
        "effectif": palier_effectif(effectif.valeur),
        "effectif_saisi": effectif.saisi_pour_l_annee,
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
            "fiche": _fiche(employee),
            "notes_de_frais": _notes_du_mois(notes_de_frais or [], year, month),
            "parametres_societe": parametres_societe_pour_empreinte(company, year),
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


# --- Empreinte complémentaire : ce que le moteur lit pour le mois ----------------

#: Colonnes qui ne disent rien du calcul : identifiants, horodatages, rappels.
_COLONNES_HORS_CALCUL = frozenset(
    {
        "id",
        "company_id",
        "employee_id",
        "created_at",
        "updated_at",
        "created_by",
        "rtt_forfeited_by_user_id",
        "rtt_year_end_reminder_enabled",
        "rtt_year_end_reminder_days_before",
    }
)

#: Ce que le moteur lit d'une formule de mutuelle (engine/calcul_cotisations.py,
#: engine/calcul_net.py) : ni les codes DSN, ni l'organisme.
_CHAMPS_MUTUELLE = (
    "libelle",
    "montant_salarial",
    "montant_patronal",
    "part_patronale_soumise_a_csg",
    "part_salariale_deductible_impot",
    "part_salariale_obligatoire",
    "is_active",
)

#: Indemnités de départ : la date du calcul et les identifiants changent sans
#: que le montant bouge.
_CLES_INDEMNITES_HORS_CALCUL = frozenset({"calculation_date", "exit_id", "employee_id"})

_SORTIES_ANNULEES = frozenset({"cancelled", "canceled", "annule", "annulee"})


def _sans(row: Mapping[str, Any] | None, cles: frozenset[str] = _COLONNES_HORS_CALCUL) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    return {k: v for k, v in row.items() if k not in cles}


def _cle_tri(valeur: Any) -> str:
    return json.dumps(valeur, sort_keys=True, ensure_ascii=False, default=str)


def _jour(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def _specificites(employee: Mapping[str, Any]) -> dict[str, Any]:
    brut = employee.get("specificites_paie")
    if isinstance(brut, str):
        try:
            brut = json.loads(brut)
        except ValueError:
            return {}
    return brut if isinstance(brut, dict) else {}


def _mutuelle_du_mois(
    mutuelles: Iterable[Mapping[str, Any]], employee: Mapping[str, Any], year: int, month: int
) -> list[dict[str, Any]]:
    """Les formules que le bulletin du mois retient (surcharge du mois comprise)."""
    bloc = resolve_monthly_specificites(_specificites(employee), year, month).get("mutuelle")
    if not isinstance(bloc, Mapping) or not bloc.get("adhesion"):
        return []
    par_id = {str(m.get("id")): m for m in mutuelles}
    ids = sorted({str(i) for i in (bloc.get("mutuelle_type_ids") or []) if i})
    return [{"id": i, **_extrait(par_id.get(i), _CHAMPS_MUTUELLE)} for i in ids]


def _ajustements_du_mois(ajustements: Iterable[Mapping[str, Any]], year: int) -> list[dict[str, Any]]:
    """Les lignes jusqu'à l'année du bulletin, comme `get_applicable_adjustment`."""
    retenues = []
    for row in ajustements:
        try:
            annee = int(row.get("year") or 0)
        except (TypeError, ValueError):
            continue
        if annee <= year:
            retenues.append(_sans(row))
    return sorted(retenues, key=_cle_tri)


def _bornes_du_mois(year: int, month: int, fenetre: Mapping[str, Any] | None) -> tuple[date, date]:
    """Mois civil ∪ fenêtre des variables : le départ et l'arrêt s'y rattachent."""
    debut = date(year, month, 1)
    fin = date(year, month, calendar.monthrange(year, month)[1])
    f_debut = _jour((fenetre or {}).get("debut"))
    f_fin = _jour((fenetre or {}).get("fin"))
    return (min(debut, f_debut) if f_debut else debut, max(fin, f_fin) if f_fin else fin)


def _depart_du_mois(
    sorties: Iterable[Mapping[str, Any]], bornes: tuple[date, date]
) -> list[dict[str, Any]]:
    """Le départ que le bulletin porte : type et indemnités (resolve_exit_state_for_payslip)."""
    retenues = []
    for row in sorties:
        if str(row.get("status") or "").lower() in _SORTIES_ANNULEES:
            continue
        dernier_jour = _jour(row.get("last_working_day"))
        if dernier_jour is None or not (bornes[0] <= dernier_jour <= bornes[1]):
            continue
        indemnites = row.get("calculated_indemnities")
        retenues.append(
            {
                "exit_type": row.get("exit_type"),
                "last_working_day": dernier_jour.isoformat(),
                "calculated_indemnities": _sans(indemnites, _CLES_INDEMNITES_HORS_CALCUL)
                if isinstance(indemnites, Mapping)
                else indemnites,
            }
        )
    return sorted(retenues, key=_cle_tri)


def _salaire_du_mois(historique: Iterable[Mapping[str, Any]], year: int, month: int) -> dict[str, Any]:
    """Les salaires datés jusqu'à la fin du mois (salaire du mois, prorata, rappel).

    Sans aucun, `salaire_actif_a_date` lit l'ancien salaire de la première
    entrée future : lui seul compte alors.
    """
    fin = date(year, month, calendar.monthrange(year, month)[1])
    lignes = [
        {
            "effective_date": jour.isoformat(),
            "ancien_salaire": row.get("ancien_salaire"),
            "nouveau_salaire": row.get("nouveau_salaire"),
        }
        for row in historique
        if (jour := _jour(row.get("effective_date"))) is not None
    ]
    lignes.sort(key=lambda l: (l["effective_date"], _cle_tri(l)))
    jusqu_au_mois = [l for l in lignes if l["effective_date"] <= fin.isoformat()]
    if jusqu_au_mois:
        return {"jusqu_au_mois": jusqu_au_mois}
    suivantes = [l for l in lignes if l["effective_date"] > fin.isoformat()]
    return {"ancien_salaire_suivant": suivantes[0]["ancien_salaire"] if suivantes else None}


def _arret_dans_le_mois(
    calendriers: Mapping[tuple[int, int], Mapping[str, Any]],
    year: int,
    month: int,
    bornes: tuple[date, date],
) -> bool:
    """Un jour d'arrêt typé : le moteur lit alors le réglage du maintien de salaire."""
    for y, m in mois_de_la_fenetre(year, month):
        for entree in _liste_prevu(calendriers.get((y, m))):
            if not isinstance(entree, Mapping) or not entree.get("arret_type"):
                continue
            iso = _iso_jour(entree, y, m)
            if iso and bornes[0].isoformat() <= iso <= bornes[1].isoformat():
                return True
    return False


def _reglages_societe_du_mois(
    complements: Complements,
    *,
    employee: Mapping[str, Any],
    company: Mapping[str, Any] | None,
    calendriers: Mapping[tuple[int, int], Mapping[str, Any]],
    year: int,
    month: int,
    bornes: tuple[date, date],
) -> dict[str, Any]:
    """Réglages société lus par le moteur hors de `parametres_societe_pour_empreinte`."""
    reglages = (company or {}).get("settings") or {}
    if not isinstance(reglages, Mapping):
        reglages = {}
    paie = reglages.get("parametres_paie")
    parties: dict[str, Any] = {
        "prime_anciennete": (paie.get("prime_anciennete") if isinstance(paie, Mapping) else None) or {},
    }
    if is_forfait_jour(employee.get("statut"), employee.get("is_forfait_jour")):
        parties["forfait_jours_ouvres_mois"] = reglages.get("forfait_jours_ouvres_mois")
    if _arret_dans_le_mois(calendriers, year, month, bornes):
        parties["maintien"] = _sans(complements.maintien)
    jei = complements.jei
    if isinstance(jei, Mapping) and jei.get("jei_enabled"):
        parties["jei"] = _sans(jei)
    return parties


def complements_du_mois(
    complements: Complements,
    *,
    year: int,
    month: int,
    employee: Mapping[str, Any],
    company: Mapping[str, Any] | None,
    calendriers: Mapping[tuple[int, int], Mapping[str, Any]],
    fenetre: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Les données de la liste complémentaire que le bulletin du mois lit. Sans I/O."""
    bornes = _bornes_du_mois(year, month, fenetre)
    return {
        "mutuelle": _mutuelle_du_mois(complements.mutuelles, employee, year, month),
        "conges_ajustements": _ajustements_du_mois(complements.ajustements_conges, year),
        "conges_reglages": {
            "conges": _sans(complements.reglages_conges),
            "anciennete": _sans(complements.conges_anciennete),
        },
        "depart": _depart_du_mois(complements.sorties, bornes),
        "salaire": _salaire_du_mois(complements.historique_salaire, year, month),
        "reglages_societe": _reglages_societe_du_mois(
            complements,
            employee=employee,
            company=company,
            calendriers=calendriers,
            year=year,
            month=month,
            bornes=bornes,
        ),
        "adresse_societe": _adresse_societe(company, year),
    }


def _adresse_societe(company: Mapping[str, Any] | None, year: int) -> dict[str, Any]:
    """Ce que le moteur lit de l'adresse de la société ([B8], 12/10/2026).

    Le code postal décide de la zone du barème du prélèvement à la source : on
    hache la zone, pas le code (déménager dans la même zone ne change rien). La
    ville décide du versement mobilité, dû à partir de 11 salariés ou quand
    l'effectif est inconnu (`baremes_loader.resoudre_taux_vm_pour_paie`).

    Partie à part, sans version à gérer : un bulletin calculé avant elle n'en a
    pas et `parties_changees` ne compare que les parties stockées des deux côtés.
    """
    societe = company or {}
    parties: dict[str, Any] = {"zone_pas": zone_du_code_postal(societe.get("adresse_code_postal"))}
    effectif = effectif_retenu(societe, year).valeur or 0
    if effectif <= 0 or effectif >= SEUIL_EFFECTIF_VERSEMENT_MOBILITE:
        parties["ville_versement_mobilite"] = str(societe.get("adresse_ville") or "").strip().upper()
    return parties


#: Le planning que le calcul du mois lit à coup sûr (lot 43) : le prévu du mois
#: civil et de la fenêtre des variables (arrêts, congés, fériés, horaire), le réel
#: de la fenêtre (heures, absences injustifiées) et les absences qui y touchent.
#: Ce qui change hors d'elle (le mois suivant posé, la semaine à cheval, les
#: pointages d'après la fenêtre) ne change que rarement le calcul : un brouillon
#: est alors recalculé au bac à sable avant de dire « À recalculer », comme un
#: validé (voir `_a_verifier`). Partie à part, sans version à gérer : un bulletin
#: calculé avant elle n'en a pas, et `parties_changees` ne la compare pas.
PARTIE_PLANNING_DU_MOIS = "planning_du_mois"

#: Les parties qu'un changement du planning d'à côté fait bouger.
_PARTIES_DU_PLANNING = frozenset({"calendriers", "absences"})


def planning_du_mois(entrees: Mapping[str, Any], year: int, month: int) -> dict[str, Any]:
    """La partie `planning_du_mois`, tirée des entrées canoniques de l'empreinte."""
    debut_mois = date(year, month, 1)
    fin_mois = date(year, month, calendar.monthrange(year, month)[1])
    fenetre = entrees.get("fenetre_variables") or {}
    f_debut = _jour(fenetre.get("debut")) or debut_mois
    f_fin = _jour(fenetre.get("fin")) or fin_mois
    debut, fin = min(debut_mois, f_debut).isoformat(), max(fin_mois, f_fin).isoformat()
    fenetre_debut, fenetre_fin = f_debut.isoformat(), f_fin.isoformat()
    prevu: list[Any] = []
    reel: list[Any] = []
    for cle in sorted(entrees.get("calendriers") or {}):
        bloc = (entrees.get("calendriers") or {}).get(cle) or {}
        try:
            annee, mois = int(str(cle)[:4]), int(str(cle)[5:7])
        except ValueError:
            continue
        for entree in bloc.get("prevu") or []:
            iso = _iso_jour(entree, annee, mois) if isinstance(entree, Mapping) else None
            if iso and debut <= iso <= fin:
                prevu.append(entree)
        for entree in bloc.get("reel") or []:
            iso = _iso_jour(entree, annee, mois) if isinstance(entree, Mapping) else None
            if iso and fenetre_debut <= iso <= fenetre_fin:
                reel.append(entree)
    absences = [
        absence
        for absence in entrees.get("absences") or []
        if any(debut <= str(jour)[:10] <= fin for jour in (absence.get("selected_days") or []))
    ]
    return {"prevu": prevu, "reel": reel, "absences": absences}


def empreintes_des_parties(
    entrees: Mapping[str, Any],
    complements: Mapping[str, Any] | None,
    *,
    mois: tuple[int, int] | None = None,
) -> dict[str, str]:
    """Un hash par partie : celles de l'empreinte d'entrée, puis les compléments,
    puis (le mois donné) le planning que le calcul du mois lit à coup sûr."""
    parties = dict(entrees)
    parties.update(complements or {})
    if mois is not None:
        parties[PARTIE_PLANNING_DU_MOIS] = planning_du_mois(entrees, *mois)
    return {nom: empreinte_partie(valeur) for nom, valeur in parties.items()}


def _complements_ou_none(
    complements: Complements | None,
    entrees: Mapping[str, Any],
    *,
    year: int,
    month: int,
    employee: Mapping[str, Any],
    company: Mapping[str, Any] | None,
    calendriers: Mapping[tuple[int, int], Mapping[str, Any]],
) -> dict[str, Any] | None:
    if complements is None:
        return None
    return complements_du_mois(
        complements,
        year=year,
        month=month,
        employee=employee,
        company=company,
        calendriers=calendriers,
        fenetre=entrees.get("fenetre_variables"),
    )


def poser_empreinte_complementaire_depuis_lectures(
    payslip_data: Mapping[str, Any] | None, **kwargs: Any
) -> dict[str, Any]:
    """À la génération : un hash par partie, posé sur le JSON du bulletin.

    Les parties d'entrée viennent des pièces déjà lues par le générateur (les
    mêmes que l'empreinte d'entrée) ; les compléments sont lus ici, après le
    calcul, par les mêmes lectures que la liste. Illisibles : seules les
    parties d'entrée sont posées — jamais un bulletin refusé pour elles.
    """
    entrees = entrees_depuis_lectures(**kwargs)
    try:
        complements: Complements | None = lire_complements(kwargs["employee"], kwargs.get("company"))
    except Exception:  # noqa: BLE001 — l'empreinte est une aide, pas une garde de calcul
        logger.warning("Compléments de l'empreinte illisibles à la génération", exc_info=True)
        complements = None
    du_mois = _complements_ou_none(
        complements,
        entrees,
        year=kwargs["year"],
        month=kwargs["month"],
        employee=kwargs["employee"],
        company=kwargs.get("company"),
        calendriers=kwargs["calendriers"],
    )
    return poser_empreinte_complementaire(
        payslip_data,
        empreintes_des_parties(entrees, du_mois, mois=(kwargs["year"], kwargs["month"])),
    )


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
    #: Les parties changées (mutuelle, fiche, planning…) quand le bulletin porte
    #: l'empreinte complémentaire ; None pour un bulletin d'avant elle.
    parties_changees: tuple[str, ...] | None = None
    #: Validé recalculé au bac à sable et différent : ce qui change (« le net à
    #: payer passerait de … à … »).
    ecart_au_bac_a_sable: str | None = None
    #: Validé aux entrées changées dont le recalcul au bac à sable tourne hors de
    #: la requête : ni « À recalculer » ni à jour tant que le verdict n'est pas là.
    verification_en_cours: bool = False
    #: Seuls le planning ou les absences hors du mois et de sa fenêtre ont changé
    #: (`planning_du_mois` identique) : un brouillon est vérifié au bac à sable.
    seulement_hors_du_mois: bool = False

    @property
    def a_recalculer(self) -> bool | None:
        if self.cascade_depuis is not None:
            return True
        return a_recalculer(self.entrees_changees, self.cumuls_precedents_changes)

    @property
    def raison_a_recalculer(self) -> str | None:
        """Ce qui a changé dans ses entrées, dit simplement (« La mutuelle a
        changé… ») ; le message général s'il ne sait pas quoi ; None sinon."""
        if self.entrees_changees is not True:
            return None
        message = message_a_recalculer(self.parties_changees)
        if self.ecart_au_bac_a_sable:
            return f"{message} {self.ecart_au_bac_a_sable}"
        return message

    def raison_du_badge(self, periode: tuple[int, int]) -> str | None:
        """Tout ce qui met le bulletin « À recalculer » : ses entrées, puis la
        chaîne des cumuls (le mois d'avant, ou le plus ancien à recalculer)."""
        raisons = [self.raison_a_recalculer] if self.raison_a_recalculer else []
        if self.cascade_depuis is not None:
            raisons.append(
                MESSAGE_A_REGENERER
                if self.cascade_depuis == periode
                else message_mois_d_avant_a_recalculer(*self.cascade_depuis)
            )
        return " ".join(raisons) or None


def _hash_ou_none(valeur: Any) -> str | None:
    return valeur if isinstance(valeur, str) and valeur else None


#: Ce qu'un bulletin validé ignore : la fiche et les réglages de paie de la
#: société sont ceux d'aujourd'hui, pas ceux du mois. Les réglages ne sont pas
#: datés (taux AT, effectif, journée de solidarité se saisissent en janvier pour
#: la nouvelle année) : les suivre périmerait tous les bulletins validés de
#: l'année close, et les recalculer leur appliquerait les valeurs de l'année
#: suivante. Seul le filtre change : le contenu haché reste le même.
_PARTIES_IGNOREES_SI_VALIDE = frozenset(
    {PARTIE_FICHE, "parametres_societe", "reglages_societe", "adresse_societe"}
)


def _etats_par_mois(
    lectures: LecturesEmpreinte | None, lignes: Iterable[Mapping[str, Any]]
) -> dict[tuple[int, int], EtatDuBulletin]:
    """L'état de chaque bulletin, mois après mois, la cascade suivant la chaîne.

    La cascade ne suit que les cumuls : un mois d'avant aux entrées changées
    (une fiche modifiée périme tous les brouillons du contrat) ne périme pas
    celui-ci tant qu'il n'a pas été recalculé. Elle s'arrête à un bulletin
    repris, à un mois sans bulletin et au premier mois d'un contrat.

    Un mois d'un ancien contrat n'est jamais signalé (il ne se recalcule
    plus) ; un bulletin validé ne l'est pas pour une fiche ou un réglage de
    paie de la société modifiés depuis.
    """
    etats: dict[tuple[int, int], EtatDuBulletin] = {}
    for ligne in sorted(lignes, key=lambda l: (int(l["year"]), int(l["month"]))):
        periode = (int(ligne["year"]), int(ligne["month"]))
        if lectures is None or str(ligne.get("origine") or "calcule") == "importe":
            etats[periode] = EtatDuBulletin()
            continue
        annee, mois = periode
        if not mois_du_contrat_en_cours(lectures.employee, annee, mois):
            # Un ancien contrat : son bulletin ne se recalcule que sur demande
            # (sur la fiche rangée avec lui), rien à signaler.
            etats[periode] = EtatDuBulletin()
            continue
        #: Validé : une fiche ou un réglage de la société modifiés depuis (ils
        #: sont ceux d'aujourd'hui) ne le remettent pas en cause ; le reste, si.
        valide = str(ligne.get("status") or "") == "valide"
        try:
            entrees, parties = _parties_du_mois(lectures, annee, mois)
            actuelle = empreinte(entrees)
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
        stockees = empreinte_complementaire_valide(ligne.get("empreinte_complementaire"))
        hors_du_mois = False
        if stockees is not None:
            # Calculé avec l'empreinte complémentaire : elle seule décide, partie
            # par partie (elle contient celles de l'empreinte d'entrée).
            changees: tuple[str, ...] | None = parties_changees(stockees, parties)
            if valide:
                changees = tuple(p for p in changees if p not in _PARTIES_IGNOREES_SI_VALIDE)
            entrees_changees: bool | None = bool(changees)
            hors_du_mois = (
                bool(changees)
                and PARTIE_PLANNING_DU_MOIS in stockees
                and PARTIE_PLANNING_DU_MOIS in parties
                and set(changees) <= _PARTIES_DU_PLANNING
            )
        else:
            # Bulletin d'avant elle : l'empreinte d'entrée seule, comme avant.
            changees = None
            entrees_changees = etat_a_recalculer(
                _hash_ou_none(ligne.get("empreinte_entrees")), actuelle
            )
            if valide and entrees_changees:
                # Le hash global ne dit pas si c'est la fiche : on ne sait pas.
                entrees_changees = None
        etats[periode] = EtatDuBulletin(
            empreinte_actuelle=actuelle,
            entrees_changees=entrees_changees,
            cumuls_precedents_changes=propres,
            cascade_depuis=cascade,
            parties_changees=changees,
            seulement_hors_du_mois=hors_du_mois,
        )
    return etats


def _parties_du_mois(
    lectures: LecturesEmpreinte, year: int, month: int
) -> tuple[dict[str, Any], dict[str, str]]:
    """Les entrées du mois (empreinte d'entrée) et un hash par partie."""
    entrees = _entrees_depuis_cache(lectures, year, month)
    du_mois = _complements_ou_none(
        lectures.complements,
        entrees,
        year=year,
        month=month,
        employee=lectures.employee,
        company=lectures.company,
        calendriers=lectures.calendriers,
    )
    return entrees, empreintes_des_parties(entrees, du_mois, mois=(year, month))


# --- Un validé dont l'empreinte change : recalculé d'abord au bac à sable ----------
#
# Choix du 12/10/2026 (rejeu final A et C2) : poser le calendrier du mois suivant
# faisait passer « À recalculer » un bulletin validé dont le calcul ne change pas
# (l'empreinte hache M-1, M et M+1 entiers). Avant de le dire, Martine le
# recalcule au bac à sable, en lecture seule (rien ne peut être écrit), et le
# compare au centime au bulletin enregistré.
#
# Le recalcul ne fait jamais attendre l'écran (environ 6 s par bulletin, mesure
# du 13/10) : il tourne hors de la requête. Pendant ce temps, le bulletin est
# « à vérifier » : ni « À recalculer » ni à jour. Le verdict, gardé par état :
# identique, le bulletin est à jour (la liste repose ses empreintes, hors de la
# requête) ; différent, « À recalculer » en disant ce qui change ; sans verdict
# (bac à sable en échec), la règle d'avant : « À recalculer ».
#
# Seules ses ENTRÉES changées sont vérifiées ainsi : un mois d'avant recalculé
# depuis (cumuls de départ changés, cascade) est la chaîne de paie, il reste « À
# recalculer ». Un même état n'est vérifié qu'une fois par processus.
#
# Lot 43 (rejeu final C3, 13/10) : un BROUILLON passait aussi « À recalculer »
# quand on posait le mois suivant. Il est vérifié de même, mais seulement quand
# le changement est hors du mois et de sa fenêtre (`planning_du_mois` identique,
# seuls le planning ou les absences d'à côté ont bougé). Un changement du mois
# lui-même — le cas courant, la gestionnaire corrige son mois — le rend « À
# recalculer » tout de suite, sans bac à sable. Pendant la vérification, sa
# validation attend le verdict (`raisons_de_ne_pas_valider`).


@dataclass(frozen=True)
class VerdictBacASable:
    """Le validé recalculé au bac à sable, face au bulletin enregistré."""

    identique: bool
    #: Ce qui change, s'il change.
    ecart: str | None = None


_VERDICTS: dict[str, VerdictBacASable | None] = {}
#: Les états dont la vérification est lancée et pas finie.
_EN_COURS: set[str] = set()
_VERROU_VERDICTS = threading.Lock()
#: Au-delà, la mémoire des verdicts repart de zéro (chaque état garde sa clé).
_VERDICTS_MAX = 2000
#: Deux recalculs à la fois au plus : une mutuelle modifiée peut changer
#: l'empreinte de tous les validés de l'année, ils attendent leur tour.
_EXECUTEUR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bac-a-sable-valides")


def oublier_les_verdicts() -> None:
    """Vide la mémoire des verdicts (tests)."""
    with _VERROU_VERDICTS:
        _VERDICTS.clear()
        _EN_COURS.clear()


def _lancer_en_arriere_plan(tache: Callable[[], None]) -> None:
    """Hors de la requête (Cloud Run garde le processeur : `--no-cpu-throttling`)."""
    _EXECUTEUR.submit(tache)


def _cle_de_verdict(*morceaux: Any) -> str:
    texte = json.dumps(morceaux, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _calculer_au_bac_a_sable(
    employee_id: str, year: int, month: int, cumuls_precedents: Any
) -> dict[str, Any]:
    from app.modules.payslips.infrastructure.providers import payslip_generator_provider

    return payslip_generator_provider.generate_en_bac_a_sable(
        employee_id, year, month, cumuls_precedents
    )


def verifier_valide_au_bac_a_sable(
    employee_id: str,
    year: int,
    month: int,
    *,
    cumuls_precedents: Any,
    cumuls_du_mois: Any,
) -> VerdictBacASable | None:
    """Recalcule le bulletin au bac à sable, en lecture seule, et le compare au
    centime à celui enregistré (montants et cumuls du mois). None si on ne peut
    pas savoir : bulletin illisible, bac à sable refusé ou en échec.

    Limite connue, laissée telle quelle (décision du 13/10) : le bac à sable ne
    régénère pas les variables automatiques de la société (la génération les
    écrit dans les saisies du mois) ; il relit celles enregistrées. Un validé
    dont seules ces variables changeraient passe donc pour identique.
    """
    from app.core.lecture_seule import lecture_seule

    try:
        enregistre = lire_bulletin_enregistre(employee_id, year, month)
        donnees = (enregistre or {}).get("payslip_data")
        if not isinstance(donnees, Mapping):
            return None
        with lecture_seule():
            resultat = _calculer_au_bac_a_sable(employee_id, year, month, cumuls_precedents)
        recalcule = (resultat or {}).get("payslip_data")
        if not isinstance(recalcule, Mapping):
            return None
        ecart = ecart_au_centime(
            donnees,
            recalcule,
            cumuls_stockes=cumuls_du_mois,
            cumuls_recalcules=(resultat or {}).get("cumuls"),
        )
    except Exception:  # noqa: BLE001 — sans verdict, la règle d'avant s'applique
        logger.warning(
            "Bulletin validé %s %02d/%s non recalculé au bac à sable",
            employee_id,
            month,
            year,
            exc_info=True,
        )
        return None
    return VerdictBacASable(identique=ecart is None, ecart=ecart)


def _a_verifier(ligne: Mapping[str, Any], etat: EtatDuBulletin | None) -> bool:
    return (
        etat is not None
        and (str(ligne.get("status") or "") == "valide" or etat.seulement_hors_du_mois)
        and str(ligne.get("origine") or "calcule") != "importe"
        and etat.entrees_changees is True
        and etat.cascade_depuis is None
    )


def _verifier_puis_garder(
    cle: str,
    employee_id: str,
    annee: int,
    mois: int,
    cumuls_precedents: Any,
    cumuls_du_mois: Any,
    ecriture: tuple[str, dict[str, Any], str | None, str] | None,
) -> None:
    """La vérification hors de la requête : le verdict, puis (identique, depuis la
    liste) les empreintes d'aujourd'hui reposées sur le bulletin."""
    try:
        verdict = verifier_valide_au_bac_a_sable(
            employee_id,
            annee,
            mois,
            cumuls_precedents=cumuls_precedents,
            cumuls_du_mois=cumuls_du_mois,
        )
        with _VERROU_VERDICTS:
            if len(_VERDICTS) >= _VERDICTS_MAX:
                _VERDICTS.clear()
            _VERDICTS[cle] = verdict
        if verdict is not None and verdict.identique and ecriture is not None:
            payslip_id, parametres, empreinte_lue, statut = ecriture
            try:
                poser_empreintes_verifiees(payslip_id, parametres, empreinte_lue, statut=statut)
            except Exception:  # noqa: BLE001 — le verdict reste juste, gardé en mémoire
                logger.warning("Empreintes du bulletin %s non reposées", payslip_id, exc_info=True)
    finally:
        with _VERROU_VERDICTS:
            _EN_COURS.discard(cle)


def _verifier_les_valides(
    employee_id: str,
    lignes: Iterable[Mapping[str, Any]],
    etats: dict[tuple[int, int], EtatDuBulletin],
    lectures: LecturesEmpreinte | None,
    *,
    seulement: tuple[int, int] | None = None,
    persister: bool = False,
) -> dict[tuple[int, int], EtatDuBulletin]:
    """Les validés aux entrées changées : le verdict du bac à sable s'il est connu,
    sinon « à vérifier » et la vérification lancée hors de la requête (voir plus
    haut). `persister` : la vérification repose les empreintes d'un identique."""
    if lectures is None:
        return etats
    from app.core.lecture_seule import ecritures_permises

    for ligne in lignes:
        try:
            periode = (int(ligne["year"]), int(ligne["month"]))
        except (KeyError, TypeError, ValueError):
            continue
        if seulement is not None and periode != seulement:
            continue
        etat = etats.get(periode)
        if etat is None or not _a_verifier(ligne, etat):
            continue
        annee, mois = periode
        try:
            _entrees, actuelles = _parties_du_mois(lectures, annee, mois)
        except (KeyError, TypeError, ValueError):
            continue
        stockees = empreinte_complementaire_valide(ligne.get("empreinte_complementaire")) or {}
        cumuls_precedents = (lectures.calendriers.get(mois_de_la_fenetre(annee, mois)[0]) or {}).get(
            "cumuls"
        )
        cumuls_du_mois = (lectures.calendriers.get(periode) or {}).get("cumuls")
        cle = _cle_de_verdict(
            employee_id,
            periode,
            ligne.get("empreinte_entrees"),
            stockees,
            etat.empreinte_actuelle,
            actuelles,
            empreinte_cumuls(cumuls_precedents),
            empreinte_cumuls(cumuls_du_mois),
        )
        with _VERROU_VERDICTS:
            connu = cle in _VERDICTS
            verdict = _VERDICTS.get(cle)
            a_lancer = not connu and cle not in _EN_COURS
            if a_lancer:
                _EN_COURS.add(cle)
        if not connu:
            if a_lancer:
                ecriture = None
                if persister and ecritures_permises() and ligne.get("id"):
                    # Les parties qu'un validé ignore (fiche, réglages société)
                    # gardent leur empreinte d'origine : rien n'est dit sur elles.
                    parties = {
                        **stockees,
                        **{
                            nom: valeur
                            for nom, valeur in actuelles.items()
                            if not (nom in _PARTIES_IGNOREES_SI_VALIDE and nom in stockees)
                        },
                    }
                    ecriture = (
                        str(ligne["id"]),
                        {"empreinte_entrees": etat.empreinte_actuelle, "empreinte_complementaire": parties},
                        _hash_ou_none(ligne.get("empreinte_entrees")),
                        str(ligne.get("status") or ""),
                    )
                arguments = (cle, employee_id, annee, mois, cumuls_precedents, cumuls_du_mois, ecriture)
                try:
                    _lancer_en_arriere_plan(lambda arguments=arguments: _verifier_puis_garder(*arguments))
                except Exception:  # noqa: BLE001 — non lancée : la règle d'avant
                    logger.warning("Vérification du validé non lancée", exc_info=True)
                    with _VERROU_VERDICTS:
                        _EN_COURS.discard(cle)
                    continue
            # Une vérification déjà finie (lancée à côté, ou jouée sur place) donne
            # son verdict tout de suite ; sinon, « à vérifier ».
            with _VERROU_VERDICTS:
                connu = cle in _VERDICTS
                verdict = _VERDICTS.get(cle)
            if not connu:
                etats[periode] = replace(etat, entrees_changees=None, verification_en_cours=True)
                continue
        if verdict is None:
            continue
        if verdict.identique:
            etats[periode] = replace(etat, entrees_changees=False, parties_changees=())
        else:
            etats[periode] = replace(etat, ecart_au_bac_a_sable=verdict.ecart)
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
    etats = _etats_par_mois(lectures, lignes)
    # L'écran du bulletin, la validation, les exports : le verdict sans écriture
    # (reposer les empreintes changerait la date d'un bulletin peut-être ouvert,
    # et sa correction serait refusée pour conflit). La liste, elle, les repose.
    etats = _verifier_les_valides(employee_id, lignes, etats, lectures, seulement=(year, month))
    return etats.get((year, month))


def annoter_a_recalculer(employee_id: str, lignes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ajoute `a_recalculer` (true / false / null) à chaque ligne de la liste RH.

    Périmé quand ses entrées ont changé, ou quand un mois d'avant a été recalculé
    depuis (ses cumuls ne sont plus ceux du calcul, de proche en proche). Un
    bulletin repris ou d'un ancien contrat n'est pas recalculable : `null`,
    comme un bulletin d'avant ce changement (sans empreinte). Une seule
    lecture groupée pour tous les mois du salarié.
    """
    if not lignes:
        return lignes
    periodes = sorted({(int(l["year"]), int(l["month"])) for l in lignes})
    lectures = lire_lectures_salarie(employee_id, periodes)
    try:
        etats = _etats_par_mois(lectures, lignes)
    except (KeyError, TypeError, ValueError):
        etats = {}
    etats = _verifier_les_valides(employee_id, lignes, etats, lectures, persister=True)
    annotées: list[dict[str, Any]] = []
    for ligne in lignes:
        copie = dict(ligne)
        copie.pop("empreinte_entrees", None)
        copie.pop("empreinte_cumuls_precedents", None)
        copie.pop("empreinte_complementaire", None)
        try:
            periode = (int(copie["year"]), int(copie["month"]))
            etat = etats.get(periode)
        except (KeyError, TypeError, ValueError):
            etat = None
        copie["a_recalculer"] = etat.a_recalculer if etat else None
        copie["a_verifier"] = bool(etat and etat.verification_en_cours)
        copie["raison_a_recalculer"] = etat.raison_du_badge(periode) if etat else None
        annotées.append(copie)
    return annotées
