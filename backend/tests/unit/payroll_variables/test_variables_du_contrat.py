"""Variables automatiques d'un mois à deux contrats (D3).

Le CDD finit le 10/11, le nouveau contrat commence le 17/11. La fenêtre des
variables de novembre va du 21/10 au 20/11. Les variables du nouveau contrat ne
comptent que ses jours (17 au 20/11), et la génération ne touche jamais une
variable rangée avec l'ancien contrat.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll_variables.application import generate_monthly as gm
from app.modules.payroll_variables.infrastructure import repository as repo
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

SAL = "emp-1"
FENETRE = (date(2026, 10, 21), date(2026, 11, 20))


class TestBornesDuContrat:
    def test_un_contrat_qui_commence_dans_la_fenetre(self):
        assert gm._bornes_du_contrat({"hire_date": "2026-11-17"}, *FENETRE) == (
            date(2026, 11, 17),
            date(2026, 11, 20),
        )

    def test_un_contrat_en_cours_garde_la_fenetre(self):
        assert gm._bornes_du_contrat({"hire_date": "2020-01-06"}, *FENETRE) == FENETRE

    def test_le_debut_d_execution_l_emporte_sur_l_embauche(self):
        emp = {"hire_date": "2020-01-06", "date_debut_execution": "2026-11-02"}
        assert gm._bornes_du_contrat(emp, *FENETRE)[0] == date(2026, 11, 2)

    def test_un_contrat_qui_commence_apres_la_fenetre_n_a_aucun_jour(self):
        debut, fin = gm._bornes_du_contrat({"hire_date": "2026-11-23"}, *FENETRE)
        assert debut > fin

    def test_une_fin_de_contrat_sur_la_fiche_ne_coupe_rien(self):
        """Des fiches actives portent une fin de CDD dépassée (renouvellement non
        reporté : 25 sur le test le 31/10) ; leurs variables restent comptées. Le
        bulletin de l'ancien contrat ne relance jamais ses variables automatiques."""
        emp = {"hire_date": "2026-01-05", "contract_end_date": "2026-10-15"}
        assert gm._bornes_du_contrat(emp, *FENETRE) == FENETRE


def test_le_calendrier_ne_garde_que_les_jours_du_contrat():
    calendrier = [{"jour": 5, "heures": 7}, {"jour": 18, "heures": 7}, {"heures": 3}]
    garde = gm._dans_le_contrat(calendrier, 2026, 11, date(2026, 11, 17), date(2026, 11, 20))
    assert garde == [{"jour": 18, "heures": 7}]


def test_les_postes_comptes_sont_ceux_du_contrat(monkeypatch):
    """Un poste du 05/11 appartient à l'ancien contrat : il n'est pas payé au nouveau."""
    BaseEnMemoire(
        {
            "shifts": [
                {"employee_id": SAL, "is_locked": True, "shift_date": "2026-11-05", "shift_types": {"code": "NUIT"}},
                {"employee_id": SAL, "is_locked": True, "shift_date": "2026-11-18", "shift_types": {"code": "NUIT"}},
            ],
            "employee_schedules": [
                {
                    "employee_id": SAL,
                    "year": 2026,
                    "month": 11,
                    "payroll_events": {"planning_hours": [{"shift_type_code": "NUIT"}] * 2},
                }
            ],
        }
    ).brancher(monkeypatch)
    regle = {"rule_type": "per_shift_type", "conditions": {"shift_type_codes": ["NUIT"]}}
    bornes = (date(2026, 11, 17), date(2026, 11, 20))
    assert gm._resolve_quantity(regle, SAL, "co-1", 2026, 11, bornes=bornes) == 1.0


def test_sans_poste_dans_le_contrat_le_resume_du_mois_n_est_pas_lu(monkeypatch):
    """Le résumé du planning compte tout le mois : il ne sert pas quand le
    contrat commence ou finit dans la fenêtre."""
    BaseEnMemoire(
        {
            "shifts": [],
            "employee_schedules": [
                {
                    "employee_id": SAL,
                    "year": 2026,
                    "month": 11,
                    "payroll_events": {"planning_hours": [{"shift_type_code": "NUIT"}] * 2},
                }
            ],
        }
    ).brancher(monkeypatch)
    monkeypatch.setattr(gm, "_bornes_variables", lambda *_a: FENETRE)
    regle = {"rule_type": "per_shift_type", "conditions": {"shift_type_codes": ["NUIT"]}}
    assert gm._resolve_quantity(regle, SAL, "co-1", 2026, 11, bornes=(date(2026, 11, 17), date(2026, 11, 20))) == 0.0
    assert gm._resolve_quantity(regle, SAL, "co-1", 2026, 11) == 2.0


def test_une_variable_rangee_avec_l_ancien_contrat_n_est_pas_reecrite(monkeypatch):
    base = BaseEnMemoire(
        {
            "monthly_inputs": [
                {
                    "id": "prime-ancien",
                    "employee_id": SAL,
                    "year": 2026,
                    "month": 11,
                    "name": "Prime poste difficile",
                    "amount": 60,
                    "contract_period_id": "periode-1",
                }
            ]
        }
    )
    base.brancher(monkeypatch)
    repo.upsert_monthly_input(
        {"employee_id": SAL, "year": 2026, "month": 11, "name": "Prime poste difficile", "amount": 60}
    )
    lignes = base.lignes("monthly_inputs", employee_id=SAL)
    assert len(lignes) == 2
    assert {l.get("contract_period_id") for l in lignes} == {"periode-1", None}


def test_une_prime_fixe_reste_due_sans_jour_dans_la_fenetre(monkeypatch):
    monkeypatch.setattr(gm, "_bornes_variables", lambda *_a: FENETRE)
    vide = gm._bornes_du_contrat({"hire_date": "2026-11-23"}, *FENETRE)
    assert gm._resolve_quantity({"rule_type": "fixed_monthly"}, SAL, "co-1", 2026, 11, bornes=vide) == 1.0
