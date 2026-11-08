"""Licenciement pour inaptitude : indemnités et motif DSN (R-263).

Cas du registre : 10 ans d'ancienneté, 2 500 € de référence, 2 mois de préavis.
Martine proposait 6 250 € ; la loi donne 12 500 € et 5 000 €.

Sources ouvertes le 08/11/2026 :
- Code du travail, art. L1226-14 (code.travail.gouv.fr) : la rupture « ouvre
  droit, pour le salarié, à une indemnité compensatrice d'un montant égal à
  celui de l'indemnité compensatrice de préavis prévue à l'article L. 1234-5
  ainsi qu'à une indemnité spéciale de licenciement qui, sauf dispositions
  conventionnelles plus favorables, est égale au double de l'indemnité prévue
  par l'article L. 1234-9 ».
- Art. L1226-16 : ces indemnités « sont calculées sur la base du salaire moyen
  qui aurait été perçu par l'intéressé au cours des trois derniers mois ».
- Art. L1226-4 (origine non professionnelle) : « le préavis n'est pas exécuté
  [...] Le préavis est néanmoins pris en compte pour le calcul de l'indemnité
  mentionnée à l'article L. 1234-9. [...] l'inexécution du préavis ne donne pas
  lieu au versement d'une indemnité compensatrice ».
- Art. R1234-2 : un quart de mois par année jusqu'à dix ans.
- service-public.gouv.fr F31225 (vérifié le 11/08/2025) : l'indemnité spéciale
  « est versée sans condition d'ancienneté ».
- Cahier technique DSN 2026.1 : motifs 091 et 092 (S21.G00.62.002) ; types 009
  et 032 (S21.G00.52.001).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.dsn_export.domain.evenements import bloc_fin_contrat, indemnites_de_rupture
from app.modules.employee_exits.application.commands import notes_du_dossier_a_la_creation
from app.modules.employee_exits.schemas.requests import EmployeeExitCreate, EmployeeExitUpdate
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
_SANS_ICCP = {"montant": 0.0, "description": "ICCP", "details": {}}


def _salarie(hire_date: str = "2016-10-01") -> dict:
    return {
        "id": "emp-1",
        "hire_date": hire_date,
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2500.0},
        "baremes": {"pss": {"annuel": 48060.0, "mensuel": 4005.0}},
    }


def _depart(origine: str | None, **extra) -> dict:
    notes = {"inaptitude_origine": origine} if origine else {}
    return {
        "id": "exit-1",
        "exit_type": "licenciement",
        "exit_request_date": "2026-09-30",
        "last_working_day": "2026-09-30",
        "notice_period_days": 60,
        "notice_indemnity_type": "not_applicable",
        "is_gross_misconduct": False,
        "exit_notes": notes,
        **extra,
    }


def _calcul(salarie: dict, depart: dict) -> dict:
    with patch(_ICCP, return_value=_SANS_ICCP):
        return calculer_indemnites_sortie(salarie, depart, supabase_client=None)


def test_origine_professionnelle_le_cas_du_registre():
    res = _calcul(_salarie(), _depart("professionnelle"))
    assert res["indemnite_licenciement"]["montant"] == pytest.approx(12500.0, abs=0.01)
    assert res["indemnite_licenciement"]["libelle_bulletin"] == "Indemnité spéciale de licenciement"
    assert res["indemnite_preavis"]["montant"] == pytest.approx(5000.0, abs=0.01)
    assert res["indemnite_preavis"]["libelle_bulletin"] == "Indemnité compensatrice d'inaptitude"
    assert res["total_gross_indemnities"] == pytest.approx(17500.0, abs=0.01)
    assert "L1226-14" in res["indemnite_licenciement"]["calcul"]


def test_origine_professionnelle_sans_condition_d_anciennete():
    res = _calcul(_salarie("2026-05-01"), _depart("professionnelle"))
    # Cinq mois : la moitié d'un quart de mois × 5/12, doublée.
    assert res["indemnite_licenciement"]["montant"] == pytest.approx(2 * 2500 / 4 * 5 / 12, abs=0.01)


def test_origine_professionnelle_le_preavis_ne_prolonge_pas_l_anciennete():
    res = _calcul(_salarie(), _depart("professionnelle", notice_end_date="2026-11-30"))
    assert res["anciennete_annees"] == pytest.approx(10.0, abs=0.01)


def test_origine_professionnelle_preavis_non_saisi_le_dit():
    res = _calcul(_salarie(), _depart("professionnelle", notice_period_days=0))
    assert res["indemnite_preavis"]["montant"] == 0.0
    assert any("préavis" in a.lower() for a in res["indemnite_preavis"]["alertes"])


def test_origine_professionnelle_convention_plus_favorable_retenue():
    depart = _depart("professionnelle")
    depart["exit_notes"]["indemnite_conventionnelle"] = 15000.0
    res = _calcul(_salarie(), depart)
    assert res["indemnite_licenciement"]["montant"] == pytest.approx(15000.0, abs=0.01)
    assert res["indemnite_licenciement"]["montant_legal"] == pytest.approx(12500.0, abs=0.01)


def test_origine_non_professionnelle_pas_de_compensatrice_et_preavis_compte():
    res = _calcul(_salarie(), _depart("non_professionnelle", notice_indemnity_type="paid", notice_end_date="2026-11-30"))
    assert res["indemnite_preavis"]["montant"] == 0.0
    # Dix ans et deux mois : 10 × 1/4 + 2/12 × 1/3 de mois.
    attendu = 2500 * (10 / 4 + (2 / 12) / 3)
    assert res["indemnite_licenciement"]["montant"] == pytest.approx(attendu, abs=0.02)


def test_licenciement_ordinaire_inchange():
    res = _calcul(_salarie(), _depart(None, notice_end_date="2026-09-30", notice_period_days=0))
    assert res["indemnite_licenciement"]["montant"] == pytest.approx(6250.0, abs=0.01)
    assert res["indemnite_preavis"]["montant"] == 0.0


@pytest.mark.parametrize("origine,motif", [("professionnelle", "092"), ("non_professionnelle", "091"), (None, "020")])
def test_motif_dsn(origine, motif):
    employee = {
        "date_fin_contrat": "2026-09-30",
        "sortie_dsn": {
            "exit_type": "licenciement",
            "last_working_day": "2026-09-30",
            "exit_request_date": "2026-09-01",
            "exit_notes": {"inaptitude_origine": origine} if origine else {},
        },
    }
    bloc, _ = bloc_fin_contrat(employee, date(2026, 9, 1), date(2026, 9, 30))
    assert bloc["S21.G00.62.002"] == motif


def test_les_lignes_portent_les_types_dsn_de_l_inaptitude():
    bulletin = {
        "calcul_du_brut": [{"libelle": "Indemnité compensatrice d'inaptitude", "gain": 5000.0}],
    }
    assert indemnites_de_rupture(bulletin, sortie=True) == [("032", 5000.0, True)]
    bulletin = {"calcul_du_brut": [{"libelle": "Indemnité spéciale de licenciement", "gain": 900.0}]}
    assert indemnites_de_rupture(bulletin, sortie=True) == [("009", 900.0, True)]


def test_la_saisie_range_l_origine_dans_les_notes():
    notes = notes_du_dossier_a_la_creation("licenciement", {"inaptitude_origine": "professionnelle"})
    assert notes == {"inaptitude_origine": "professionnelle"}
    assert notes_du_dossier_a_la_creation("demission", {"inaptitude_origine": "professionnelle"}) is None
    assert EmployeeExitCreate.model_fields["inaptitude_origine"] is not None
    assert EmployeeExitUpdate.model_fields["inaptitude_origine"] is not None


def test_le_recu_et_le_bulletin_disent_l_indemnite_compensatrice():
    from types import SimpleNamespace

    from app.modules.payroll.engine.indemnites_sortie_brut import lignes_indemnites_sortie_soumises
    from app.modules.payroll.solde_de_tout_compte.common.socle_commun import compute_preavis_section

    res = _calcul(_salarie(), _depart("professionnelle"))
    lignes = lignes_indemnites_sortie_soumises(SimpleNamespace(exit_indemnities=res))
    assert ("Indemnité compensatrice d'inaptitude", 5000.0) in [(l["libelle"], l["gain"]) for l in lignes]

    section, montant, versee = compute_preavis_section(_depart("professionnelle"), res)
    assert versee and montant == pytest.approx(5000.0, abs=0.01)
    assert "L1226-14" in str(section)
