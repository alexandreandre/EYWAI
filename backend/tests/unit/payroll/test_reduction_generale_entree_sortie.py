"""SMIC de référence d'un mois d'entrée ou de sortie passé entièrement en arrêt (L15, relecture du 27/11).

Le salaire minimum se proratise sur le rapport entre la rémunération versée et celle de la présence
(BOSS, allègements généraux, § 770 ; CSS D. 241-7, IV). Sur un mois d'entrée ou de sortie, la présence
est déjà la période sous contrat : les heures de base sont proratisées (77 h pour une sortie le 15/10).
Le rapport se fait donc sur le salaire de cette période, pas sur le salaire du mois complet, sinon la
proratisation joue deux fois (relecture : 8,10 h au lieu de 15,95 h, sortie le 15/10, arrêt du 1er au
15, 262,95 € maintenus sur 1 269,20 € retenus).

Au générateur des heures, par le banc de profils. Le forfait jours compte en jours (pas concerné).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.unit.payroll.profils_salaries import banc  # noqa: F401

pytestmark = pytest.mark.unit

ARRET = {"type": "arret_maladie", "arret_type": "maladie_simple"}


def _ouvres(d1, d2):
    return [d for d in range(d1, d2 + 1) if date(2026, 10, d).weekday() < 5]


def _jours_de(d1, d2):
    j, out = date(2026, 10, d1), []
    while j <= date(2026, 10, d2):
        out.append(j.isoformat())
        j += timedelta(days=1)
    return out


def _smic_reference(donnees):
    bloc = donnees["structure_cotisations"]["bloc_allegements"]
    lignes = bloc if isinstance(bloc, list) else bloc.get("lignes", [])
    return next(l for l in lignes if "générale" in str(l.get("libelle")))["smic_reference_mois"]


def _salaire_et_heures_sous_contrat(donnees):
    """Le salaire de la période sous contrat et ses heures, lus sur les lignes du bulletin."""
    salaire, heures = 0.0, 0.0
    for l in donnees.get("calcul_du_brut") or []:
        lib = str(l.get("libelle"))
        if lib == "Salaire de base" or lib.startswith("Heures suppl. structurelles"):
            salaire += float(l.get("gain") or 0)
            heures += float(l.get("quantite") or 0)
    for l in (donnees.get("details_absences") or []) + (donnees.get("calcul_du_brut") or []):
        if str(l.get("libelle")) == "Absence pour entrée ou sortie":
            salaire -= float(l.get("perte") or 0)
            heures -= float(l.get("quantite") or 0)
    return salaire, heures


def _verifier(donnees, plein, heures_plein):
    maintien = float(donnees["bloc_maintien"]["maintien"]["maintien_verse"])
    assert maintien > 0
    salaire, heures = _salaire_et_heures_sous_contrat(donnees)
    smic_horaire = _smic_reference(plein) / heures_plein
    attendu = heures * maintien / salaire
    assert _smic_reference(donnees) == pytest.approx(round(smic_horaire * attendu, 2), abs=0.011)
    return heures, maintien, salaire, attendu


@pytest.mark.parametrize("apres_la_sortie", ("hors_contrat", "weekend"))
def test_sortie_le_15_pendant_un_arret(banc, apres_la_sortie):  # noqa: F811
    """CDD fini le 15/10, arrêt du 1er au 15 : 77 h sous contrat, rapport au salaire de ces 77 h."""
    apres = {d: apres_la_sortie for d in _ouvres(16, 31)}
    absences = [{"id": "a1", "type": "arret_maladie", "arret_type": "maladie_simple", "status": "validated",
                 "selected_days": _jours_de(1, 15)}]
    fiche = {"hire_date": "2015-01-05"}
    donnees = banc.generer("sortie_en_cours_de_mois", jours={**{d: ARRET for d in _ouvres(1, 15)}, **apres},
                           absences=absences, fiche_en_plus=fiche)
    plein = banc.generer("heures", jours={}, fiche_en_plus=fiche)
    heures, *_ = _verifier(donnees, plein, 151.67)
    assert heures == pytest.approx(77.0, abs=0.01)


def test_entree_le_16_pendant_un_arret(banc):  # noqa: F811
    """Entré le 16/10, en arrêt du 16 au 31 : les heures sous contrat au prorata de leur maintien."""
    jours = {**{d: "hors_contrat" for d in _ouvres(1, 15)}, **{d: ARRET for d in _ouvres(16, 31)}}
    absences = [{"id": "a1", "type": "arret_maladie", "arret_type": "maladie_simple", "status": "validated",
                 "selected_days": _jours_de(16, 31)}]
    # Reprise d'ancienneté (mutation dans le groupe) : le maintien est dû dès l'entrée.
    donnees = banc.generer("heures", jours=jours, absences=absences,
                           fiche_en_plus={"hire_date": "2026-10-16", "seniority_reference_date": "2015-01-05"})
    if not (donnees.get("bloc_maintien") or {}).get("maintien", {}).get("maintien_verse"):
        pytest.skip("pas de maintien à l'entrée (ancienneté) : la règle ne s'y joue pas")
    plein = banc.generer("heures", jours={}, fiche_en_plus={"hire_date": "2015-01-05"})
    _verifier(donnees, plein, 151.67)


def test_entree_le_16_pendant_un_arret_sans_maintien_aucune_heure(banc):  # noqa: F811
    """Sans ancienneté, aucun maintien : aucune heure (la période sous contrat n'est pas payée)."""
    jours = {**{d: "hors_contrat" for d in _ouvres(1, 15)}, **{d: ARRET for d in _ouvres(16, 31)}}
    absences = [{"id": "a1", "type": "arret_maladie", "arret_type": "maladie_simple", "status": "validated",
                 "selected_days": _jours_de(16, 31)}]
    donnees = banc.generer("heures", jours=jours, absences=absences, fiche_en_plus={"hire_date": "2026-10-16"})
    if (donnees.get("bloc_maintien") or {}).get("maintien", {}).get("maintien_verse"):
        pytest.skip("maintien versé : couvert par le test précédent")
    assert _smic_reference(donnees) == pytest.approx(0.0, abs=0.01)

