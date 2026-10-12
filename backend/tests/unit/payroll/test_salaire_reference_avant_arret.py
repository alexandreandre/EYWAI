"""Salaire de référence de l'indemnité de licenciement : les mois d'avant l'arrêt
maladie.

Cour de cassation, chambre sociale, 23 mai 2017, n° 15-22.223, publié au
bulletin (Légifrance JURITEXT000034813531, ouvert le 11/10/2026), au visa des
articles L1234-9 et R1234-4 du Code du travail : « le salaire de référence à
prendre en considération pour le calcul de l'indemnité légale ou
conventionnelle de licenciement est, selon la formule la plus avantageuse pour
le salarié, celui des douze ou des trois derniers mois précédant l'arrêt de
travail pour maladie ».

Martine signalait l'arrêt (« à vérifier ») mais calculait sur les mois de
l'arrêt, payés au maintien ou pas du tout : l'indemnité baissait avec la
maladie. Elle prend désormais les mois qui précèdent l'arrêt le plus récent des
mois de référence, et le dit dans le détail de l'indemnité.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.salaire_reference_sortie import MoisDeSalaire, calculer_salaire_de_reference
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


def _mois(debut: tuple[int, int], fin: tuple[int, int]):
    annee, mois = debut
    while (annee, mois) <= fin:
        yield annee, mois
        annee, mois = (annee, mois + 1) if mois < 12 else (annee + 1, 1)


def _historique() -> list[MoisDeSalaire]:
    """3 000 € par mois, puis un arrêt maladie de juin à septembre 2026 (1 000 €)."""
    return [
        MoisDeSalaire(a, m, 1000.0 if (a, m) >= (2026, 6) else 3000.0, arret_maladie=(a, m) >= (2026, 6))
        for a, m in _mois((2025, 1), (2026, 9))
    ]


def test_la_reference_est_celle_des_mois_qui_precedent_l_arret():
    reference = calculer_salaire_de_reference(_historique(), repli_contrat=2500.0)

    assert reference.retenu == 3000.0
    assert reference.moyenne_douze_mois == 3000.0
    assert reference.mois_lus == 12
    assert "juin 2026" in reference.arret
    assert "Cass. soc., 23 mai 2017, n° 15-22.223" in reference.arret
    assert not any("à vérifier" in a and "rrêt" in a for a in reference.alertes)


def test_sans_bulletin_avant_l_arret_le_salaire_du_contrat_est_pris_et_signale():
    mois = [MoisDeSalaire(2026, m, 1000.0, arret_maladie=True) for m in range(6, 10)]
    reference = calculer_salaire_de_reference(mois, repli_contrat=2500.0)

    assert reference.retenu == 2500.0
    assert reference.formule == "contrat"
    assert any("avant l'arrêt" in a for a in reference.alertes)


def test_sans_bulletin_avant_l_arret_la_reference_ne_baisse_pas_sous_les_bulletins_disponibles():
    """Rejeu d'un départ réel de juin 2026 : arrêt en janvier, premier mois repris
    dans Martine ; retomber sur le salaire du contrat (plus bas que le brut des
    bulletins, heures structurelles et primes comprises) faisait baisser
    l'indemnité de 700 €. Les mois d'avant l'arrêt manquent : le plus favorable
    du contrat et des bulletins disponibles, signalé à vérifier."""
    mois = [MoisDeSalaire(2026, 1, 1500.0, arret_maladie=True)] + [
        MoisDeSalaire(2026, m, 3000.0) for m in range(2, 6)
    ]
    reference = calculer_salaire_de_reference(mois, repli_contrat=2500.0)

    assert reference.retenu == 3000.0
    assert any("avant l'arrêt" in a and "à vérifier" in a for a in reference.alertes)


def _base() -> BaseEnMemoire:
    lignes = []
    for a, m in _mois((2025, 1), (2026, 9)):
        arret = (a, m) >= (2026, 6)
        lignes.append(
            {
                "employee_id": "emp-1",
                "year": a,
                "month": m,
                "payslip_data": {
                    "salaire_brut": 1000.0 if arret else 3000.0,
                    "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 3000.0}],
                    "details_absences": (
                        [{"libelle": "Absence maladie", "perte": 2000.0}] if arret else []
                    ),
                },
            }
        )
    return BaseEnMemoire({"payslips": lignes})


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_detail_de_l_indemnite_dit_l_arret_et_la_reference_d_avant(_iccp):
    salarie = {
        "id": "emp-1",
        "hire_date": "2016-01-01",
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 3000.0},
        "baremes": {"pss": {"annuel": 48060.0}},
    }
    depart = {
        "id": "exit-1",
        "exit_type": "licenciement",
        "exit_request_date": "2026-10-01",
        "last_working_day": "2026-10-31",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
    }
    dossier = calculer_indemnites_sortie(salarie, depart, _base())

    indemnite = dossier["indemnite_licenciement"]
    assert indemnite["salaire_reference"] == 3000.0
    assert "arrêt maladie" in indemnite["calcul"]
    assert "Cass. soc., 23 mai 2017" in indemnite["calcul"]
