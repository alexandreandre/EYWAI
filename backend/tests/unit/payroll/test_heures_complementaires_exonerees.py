"""Heures complémentaires d'un temps partiel : réduction salariale et exonération d'impôt.

Sources :
- CSS art. L241-17, I, 5° : la réduction de cotisations salariales vise « les
  rémunérations versées aux salariés à temps partiel au titre des heures
  complémentaires de travail » ; taux 11,31 %, dans la limite des cotisations dues.
- CGI art. 81 quater, I : exonération d'impôt des rémunérations du I de
  L241-17, dans la limite annuelle de 7 500 €.
- BOSS, « Exonérations heures supplémentaires et complémentaires », § 110 à 140
  (heures éligibles d'un temps partiel : celles au-delà du contrat) et § 290
  (majoration de 10 % jusqu'au dixième du contrat, 25 % au-delà).
- Urssaf, « Déduction forfaitaire patronale » : les heures complémentaires n'y
  ouvrent pas droit ; elle reste réservée aux heures supplémentaires.

Le moteur ne retenait que les lignes « Heures suppl. majorées » : une heure
complémentaire restait cotisée en plein et imposable. Cas de l'enquête du
10/10/2026 (MAJI, juin 2026, contrat de 8,08 h) : une heure complémentaire à
10 % de 16,50 €, saisie au bulletin ; avec la règle, net à payer +1,87 €
(11,31 % de 16,50) et net imposable −13,53 €, comme la DSN du cabinet
(net fiscal 427,18 €, rubrique 017 de 16,50 €).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .fixtures.baremes_snapshot import baremes_snapshot_csg_unifie
from .helpers import build_test_contexte, run_bulletin_pipeline_heures

pytestmark = pytest.mark.unit

DUREE = 8.08
SALAIRE = 525.0


def _baremes() -> dict:
    """Barèmes au format de production : CSG/CRDS en une entrée (la part des
    heures exonérées sort en « CSG/CRDS sur HS non déductible ») et taux de la
    réduction salariale de 11,31 % (`scraping/heuressupp`)."""
    baremes = baremes_snapshot_csg_unifie()
    baremes["heures_supp"]["reduction_salariale"] = {"taux_reduction": {"plafond_legal": 0.1131}}
    return baremes


def _contexte():
    return build_test_contexte(
        duree_hebdo=DUREE, salaire_base=SALAIRE, is_temps_partiel=True, baremes=_baremes()
    )


def _jours_ouvres(annee: int, mois: int, heures: float) -> list[dict]:
    jours = []
    d = date(annee, mois, 1)
    while d.month == mois:
        if d.weekday() < 5:
            jours.append({"date_complete": d.isoformat(), "type": "travail", "heures": heures})
        d = date.fromordinal(d.toordinal() + 1)
    return jours


def _bulletin(libelle_prime: str) -> dict:
    return run_bulletin_pipeline_heures(
        _contexte(),
        year=2026,
        month=6,
        calendrier=_jours_ouvres(2026, 6, round(DUREE / 5, 2)),
        primes_soumises=[{"prime_id": "saisie", "libelle": libelle_prime, "montant": 16.50}],
    )


def test_le_cas_de_l_enquete_une_heure_complementaire_saisie_au_bulletin():
    ordinaire = _bulletin("Prime exceptionnelle")
    complementaire = _bulletin("Heure complémentaire majorée 10%")

    assert complementaire["brut"] == ordinaire["brut"]
    assert round(complementaire["net_a_payer"] - ordinaire["net_a_payer"], 2) == 1.87
    assert round(complementaire["net_imposable"] - ordinaire["net_imposable"], 2) == -13.53
    # Pas de déduction forfaitaire patronale : les charges patronales ne bougent pas.
    assert complementaire["total_cotisations_patronales"] == ordinaire["total_cotisations_patronales"]


def test_les_heures_complementaires_du_calendrier_entrent_dans_la_remuneration_exoneree():
    calendrier = _jours_ouvres(2026, 6, round(DUREE / 5, 2)) + [
        {"date_complete": "2026-06-09", "type": "travail_hc10", "heures": 0.8},
        {"date_complete": "2026-06-09", "type": "travail_hc25", "heures": 1.2},
    ]
    resultat = calculer_salaire_brut(
        _contexte(), calendrier, date(2026, 6, 1), date(2026, 6, 30), []
    )
    lignes_hc = [
        l for l in resultat["lignes_composants_brut"] if str(l.get("libelle", "")).startswith("Heures complémentaires")
    ]

    assert len(lignes_hc) == 2
    assert resultat["remuneration_brute_heures_supp"] == pytest.approx(round(sum(l["gain"] for l in lignes_hc), 2))
    # Le nombre d'heures de la déduction patronale ne compte que les heures supplémentaires.
    assert resultat["total_heures_supp"] == 0.0
