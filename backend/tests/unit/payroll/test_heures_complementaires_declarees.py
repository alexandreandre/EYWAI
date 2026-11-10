"""Heures complémentaires du mois déclarées depuis le bulletin (page client du 10/11, C2).

Même principe que les heures sup déclarées : pour un salarié à temps partiel,
la gestionnaire tape les heures de chaque palier ; elles remplacent celles du
planning pour ce bulletin, même nulles, et le bulletin garde ce que le planning
donnait. Majorations : 10 % jusqu'au dixième des heures du contrat, 25 % au-delà
(C. trav. L3123-29, à défaut d'accord de branche, L3123-21 ; ouverts le
10/11/2026 sur code.travail.gouv.fr). Sans déclaration, rien ne bouge.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.corrections_manuelles import (
    CLE_HEURES_COMPLEMENTAIRES_DECLAREES,
    HeuresComplementairesDeclarees,
    RegularisationInvalide,
    ranger_correction_manuelle,
)
from app.modules.payslips.domain.corrections import (
    CorrectionsBulletin,
    corrections_pour_revenir,
    refus_des_heures_complementaires,
    resume_des_corrections,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))


def _calendrier(hc=None):
    cal = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "travail_base", "heures": 4.0})
        jour = date.fromordinal(jour.toordinal() + 1)
    for iso, (type_ev, heures) in (hc or {}).items():
        cal.append({"date_complete": iso, "type": type_ev, "heures": heures})
    return cal


def _calcul(declarees=None, cal=None):
    contexte = build_test_contexte(duree_hebdo=20.0, salaire_base=1300.0, is_temps_partiel=True)
    contexte.year = 2026
    if declarees is not None:
        contexte.contrat.setdefault("saisie_du_mois", {})[CLE_HEURES_COMPLEMENTAIRES_DECLAREES] = declarees
    resultat = calculer_salaire_brut(contexte, cal or _calendrier(), *JANVIER, [])
    return contexte, resultat


def _lignes_hc(resultat):
    return [l for l in resultat["lignes_composants_brut"] if l["libelle"].startswith("Heures complémentaires")]


CAL_HC = {"2026-01-15": ("travail_hc10", 3.0), "2026-01-16": ("travail_hc25", 1.0)}


def test_sans_declaration_les_heures_du_planning_restent():
    contexte, resultat = _calcul(cal=_calendrier(CAL_HC))
    assert [l["quantite"] for l in _lignes_hc(resultat)] == [3.0, 1.0]
    assert getattr(contexte, "heures_complementaires_declarees", None) is None


def test_les_heures_declarees_remplacent_le_planning():
    contexte, resultat = _calcul({"hc1": 5.0, "hc2": 2.5}, cal=_calendrier(CAL_HC))
    hc10, hc25 = _lignes_hc(resultat)
    assert hc10["libelle"] == "Heures complémentaires majorées à 10%"
    assert hc10["quantite"] == 5.0
    assert hc25["quantite"] == 2.5
    assert contexte.heures_complementaires_declarees == {"hc1": 5.0, "hc2": 2.5, "planning": 4.0}
    assert resultat["heures_complementaires"] == pytest.approx(7.5)


def test_zero_declare_retire_les_heures_du_planning():
    _, resultat = _calcul({"hc1": 0.0, "hc2": 0.0}, cal=_calendrier(CAL_HC))
    assert _lignes_hc(resultat) == []


def test_la_declaration_se_range_a_part_des_primes():
    declaration = HeuresComplementairesDeclarees(hc1=4.0, hc2=1.0)
    saisie = {**declaration.saisie_du_mois({"employee_id": "e"}), "id": "s1"}
    saisies_data: dict = {}
    assert ranger_correction_manuelle(saisie, saisies_data)
    assert saisies_data[CLE_HEURES_COMPLEMENTAIRES_DECLAREES] == {"hc1": 4.0, "hc2": 1.0}
    assert "primes" not in saisies_data


@pytest.mark.parametrize("hc1,hc2", [(-1.0, 0.0), (0.0, 301.0)])
def test_des_heures_hors_bornes_sont_refusees(hc1, hc2):
    with pytest.raises(RegularisationInvalide):
        HeuresComplementairesDeclarees(hc1=hc1, hc2=hc2)


def test_refusees_hors_temps_partiel():
    corrections = CorrectionsBulletin(heures_complementaires=(2.0, 0.0))
    assert refus_des_heures_complementaires(corrections, temps_partiel=False, forfait_jours=False)
    assert refus_des_heures_complementaires(corrections, temps_partiel=True, forfait_jours=False) is None
    assert refus_des_heures_complementaires(CorrectionsBulletin(), temps_partiel=False, forfait_jours=False) is None


def test_le_resume_et_la_restauration():
    corrections = CorrectionsBulletin(heures_complementaires=(2.0, 0.5))
    assert resume_des_corrections(corrections) == (
        "Heures complémentaires 2 h au 1er palier et 0,5 h au 2d palier"
    )
    courant = {"heures_complementaires_declarees": {"hc1": 1.0, "hc2": 0.0, "planning": 1.0}}
    cible = {"heures_complementaires_declarees": {"hc1": 3.0, "hc2": 0.0, "planning": 1.0}}
    assert corrections_pour_revenir(courant, cible).heures_complementaires == (3.0, 0.0)
    assert corrections_pour_revenir(courant, {}).heures_complementaires_au_planning
    assert corrections_pour_revenir({}, {}).heures_complementaires is None
    assert not corrections_pour_revenir({}, {}).heures_complementaires_au_planning


def test_le_pipeline_transmet_la_declaration_et_le_bulletin_la_garde():
    from pathlib import Path

    from app.modules.payroll.documents import payslip_run_heures
    from app.modules.payroll.engine import bulletin

    source = Path(payslip_run_heures.__file__).read_text(encoding="utf-8")
    assert '[CLE_HEURES_COMPLEMENTAIRES_DECLAREES] = (' in source
    assert 'bulletin["heures_complementaires_declarees"]' in Path(bulletin.__file__).read_text(encoding="utf-8")
