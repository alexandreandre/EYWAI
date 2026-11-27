"""SMIC de référence d'un mois d'arrêt maintenu en tout ou en partie (L15, relecture du 27/11).

Le salaire minimum se proratise sur le rapport entre la rémunération versée et celle que le salarié
aurait perçue présent (BOSS, allègements généraux, § 770 à 790 ; CSS D. 241-7, IV) ; maintien intégral :
le salaire minimum de la présence (§ 750).

Deux défauts, au générateur des heures :
- la part maintenue se rapportait à la seule retenue de base de l'arrêt, alors que ses heures
  comptent aussi la part d'heures sup structurelles (ligne « Heures sup. du contrat non faites ») :
  à 39 h, le SMIC de référence était trop haut ;
- un mois entièrement en arrêt de 22 jours ouvrés retenait 154 h pour 151,67 h au contrat.

Règle : mois au salaire retenu en entier, heures du contrat × maintien ÷ salaire du mois complet ;
mois en partie travaillé, heures de l'arrêt × (1 − maintien ÷ retenue de l'arrêt, base et heures sup).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest

from app.modules.payroll.engine.heures_reduction_generale import (
    heures_remunerees_pour_la_reduction,
)
from tests.unit.payroll.profils_salaries import banc  # noqa: F401

pytestmark = pytest.mark.unit


def _heures(**k):
    base = dict(
        heures_base_mois=151.67, heures_activite_partielle=0.0, heures_absence_non_payees=0.0,
        heures_arret=0.0, retenue_arret_base=0.0, retenue_arret_heures_sup=0.0, maintien_verse=0.0,
        total_heures_supp=0.0, heures_sup_conjoncturelles=0.0, heures_complementaires=0.0,
        heures_normales_regularisees=0.0, heures_retablies_par_rappels=0.0,
        salaire_retenu_en_entier=False, salaire_du_mois_complet=2500.0,
    )
    base.update(k)
    return round(heures_remunerees_pour_la_reduction(**base), 2)


# 1) La règle, valeurs exactes.
@pytest.mark.parametrize("heures_sup,salaire", ((0.0, 2500.0), (17.33, 2785.72)))
def test_mois_entier_maintenu_en_entier_garde_les_heures_du_contrat(heures_sup, salaire):
    """§ 750 : maintien intégral, le SMIC de la présence (151,67 h ; 169 h à 39 h)."""
    assert _heures(
        heures_arret=140.0 + heures_sup * 20 / 21.67, retenue_arret_base=2500.0, maintien_verse=salaire,
        total_heures_supp=heures_sup, salaire_retenu_en_entier=True, salaire_du_mois_complet=salaire,
    ) == round(151.67 + heures_sup, 2)


def test_mois_entier_maintien_partiel_a_35_h():
    """Octobre, 22 jours ouvrés : 154 h retenues pour 151,67 h au contrat ; 755,97 € maintenus."""
    assert _heures(
        heures_arret=154.0, retenue_arret_base=2538.46, maintien_verse=755.97,
        salaire_retenu_en_entier=True,
    ) == round(151.67 * 755.97 / 2500.0, 2) == 45.86


def test_mois_entier_maintien_partiel_a_39_h():
    """Février, 2 785,72 € à 39 h, 828,46 € maintenus : 169 × 828,46 ÷ 2 785,72 = 50,26 h."""
    assert _heures(
        heures_arret=156.0, retenue_arret_base=2437.57, retenue_arret_heures_sup=348.22,
        maintien_verse=828.46, total_heures_supp=17.33, salaire_retenu_en_entier=True,
        salaire_du_mois_complet=2785.72,
    ) == 50.26


def test_mois_entier_avec_un_arret_reporte_du_mois_precedent():
    """Octobre entier en arrêt (2 925 €, 1 492,29 € maintenus) et arrêt de septembre reporté (119 h,
    2 260,23 € retenus, 1 197,26 € maintenus) : les heures d'octobre au prorata de leur maintien, moins la
    part non maintenue des jours de septembre, comptés au mois de septembre (BOSS § 790)."""
    attendu = round(151.67 * 1492.29 / 2925.0 - 119.0 * (1 - 1197.26 / 2260.23), 2)
    assert _heures(
        heures_arret=154.0 + 119.0, retenue_arret_base=2925.0 + 2260.23, maintien_verse=1492.29 + 1197.26,
        salaire_retenu_en_entier=True, salaire_du_mois_complet=2925.0,
        heures_arret_d_autres_mois=119.0, retenue_arret_d_autres_mois=2260.23, maintien_d_autres_mois=1197.26,
    ) == attendu == 21.41


def test_mois_entier_sans_maintien_aucune_heure_sauf_les_conjoncturelles():
    assert _heures(
        heures_absence_non_payees=140.0, total_heures_supp=19.33, heures_sup_conjoncturelles=2.0,
        salaire_retenu_en_entier=True, salaire_du_mois_complet=2785.72,
    ) == 2.0


def test_mois_partiel_la_part_maintenue_se_rapporte_a_la_base_et_aux_heures_sup():
    """10 jours d'arrêt à 39 h : 70 h de base (1 218,79 €) et 8 h sup (174,11 €), 197,26 € maintenus."""
    attendu = round(169.0 - 78.0 * (1 - 197.26 / (1218.79 + 174.11)), 2)
    assert _heures(
        heures_arret=78.0, retenue_arret_base=1218.79, retenue_arret_heures_sup=174.11,
        maintien_verse=197.26, total_heures_supp=17.33,
    ) == attendu == 102.05


def test_mois_partiel_a_35_h_inchange():
    assert _heures(heures_arret=70.0, retenue_arret_base=1250.0, maintien_verse=164.34) == round(
        151.67 - round(70.0 * (1 - 164.34 / 1250.0), 2), 2
    )


# 2) Le vrai chemin du bulletin (banc de profils), heures et 39 h.
ARRET = {"type": "arret_maladie", "arret_type": "maladie_simple"}


def _ouvres(m, d1=1, d2=None):
    d2 = d2 or calendar.monthrange(2026, m)[1]
    return [d for d in range(d1, d2 + 1) if date(2026, m, d).weekday() < 5]


def _jours_de(m, d1, d2):
    j, out = date(2026, m, d1), []
    while j <= date(2026, m, d2):
        out.append(j.isoformat())
        j += timedelta(days=1)
    return out


CAS = {
    "février entier": (2, {d: ARRET for d in _ouvres(2)}, (1, 28)),
    "octobre entier, 22 jours": (10, {d: ARRET for d in _ouvres(10)}, (1, 31)),
    "arrêt puis sans solde": (
        2, {**{d: ARRET for d in _ouvres(2, 1, 13)}, **{d: "absence_non_remuneree" for d in _ouvres(2, 14)}}, (1, 13),
    ),
    "dix jours d'arrêt": (2, {d: ARRET for d in _ouvres(2, 2, 13)}, (2, 13)),
}


def _bulletin(banc, duree, salaire, cas, jours=None):  # noqa: F811
    mois, jours_cas, (d1, d2) = CAS[cas]
    absences = [{"id": "a1", "type": "arret_maladie", "arret_type": "maladie_simple", "status": "validated",
                 "selected_days": _jours_de(mois, d1, d2)}]
    return banc.generer(
        "heures", jours=jours_cas if jours is None else jours, mois=mois, absences=absences,
        fiche_en_plus={"duree_hebdomadaire": duree, "salaire_de_base": {"valeur": salaire}, "hire_date": "2015-01-05"},
    )


def _smic_reference(donnees):
    bloc = donnees["structure_cotisations"]["bloc_allegements"]
    lignes = bloc if isinstance(bloc, list) else bloc.get("lignes", [])
    return next(l for l in lignes if "générale" in str(l.get("libelle")))["smic_reference_mois"]


def _perte(donnees, debut):
    return sum(float(l.get("perte") or 0) for l in donnees.get("details_absences") or []
               if str(l.get("libelle")).startswith(debut))


@pytest.mark.parametrize("duree,salaire,heures_contrat", ((35, 2500.0, 151.67), (39, 2785.72, 169.0)))
@pytest.mark.parametrize("cas", list(CAS))
def test_banc_heures_de_l_arret_maintenu_en_partie(banc, duree, salaire, heures_contrat, cas):  # noqa: F811
    donnees = _bulletin(banc, duree, salaire, cas)
    plein = _bulletin(banc, duree, salaire, cas, jours={})
    smic_horaire = _smic_reference(plein) / heures_contrat
    maintien = float(donnees["bloc_maintien"]["maintien"]["maintien_verse"])
    assert maintien > 0
    if cas == "dix jours d'arrêt":
        heures_arret = sum(float(l.get("quantite") or 0) for l in donnees["details_absences"]
                           if str(l.get("libelle")).startswith(("Absence arrêt", "Heures sup. du contrat non faites")))
        retenue = _perte(donnees, "Absence arrêt") + _perte(donnees, "Heures sup. du contrat non faites")
        attendu = heures_contrat - round(heures_arret * (1 - maintien / retenue), 2)
    else:
        attendu = heures_contrat * maintien / salaire
    assert _smic_reference(donnees) == pytest.approx(round(smic_horaire * attendu, 2), abs=0.011)
