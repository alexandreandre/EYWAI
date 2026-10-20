"""Un bulletin calculé après la clôture du départ n'est pas « À recalculer » aussitôt.

Tournage H.5, scène 12 (20/10/2026) : départ d'Inès clôturé, puis bulletin
d'octobre généré ; la page du bulletin disait aussitôt « À recalculer — La
fiche du salarié a changé depuis le calcul ». Le générateur lit la fiche
entière : salariée « parti », départ clôturé, sa sortie se lit sur le départ
du contrat en cours (`resolve_date_sortie` → `sortie_du_contrat_en_cours`),
31/10/2026. La relecture de l'empreinte ne lisait pas `employment_status` :
la salariée y passait pour « actif », sans sortie ; la date de sortie de la
fiche hachée différait.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.employees.application.contrat_du_mois import lecteur_contrats
from app.modules.payroll.application.empreinte_entrees_service import _fiche
from app.modules.payroll.documents.payslip_generator import resolve_date_sortie
from app.modules.payroll.infrastructure import empreinte_entrees_queries as lectures

pytestmark = pytest.mark.unit

#: La fiche d'Inès après la clôture : apprentie, partie, sans départ en cours.
FICHE = {
    "id": "e-ines",
    "company_id": "c-1",
    "salaire_de_base": 1100.0,
    "classification_conventionnelle": None,
    "duree_hebdomadaire": 35,
    "is_temps_partiel": False,
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
    "hire_date": "2026-09-01",
    "seniority_reference_date": None,
    "prior_service_months": None,
    "contract_end_date": None,
    "contract_type": "Apprentissage",
    "elements_variables": None,
    "avantages_en_nature": None,
    "specificites_paie": None,
    "job_title": "Apprentie assistante RH",
    "date_conclusion_contrat": None,
    "date_debut_execution": "2026-09-01",
    "current_exit_id": None,
    "employment_status": "parti",
    "first_name": "Inès",
}


class _Requete:
    def __init__(self, table):
        self.table, self.colonnes, self.seule = table, "*", False

    def select(self, colonnes="*", *_a, **_k):
        self.colonnes = colonnes
        return self

    def maybe_single(self):
        self.seule = True
        return self

    def execute(self):
        if self.table == "employees":
            # La base ne rend que les colonnes demandées.
            noms = [c.strip() for c in self.colonnes.split(",")]
            return SimpleNamespace(data={c: FICHE.get(c) for c in noms})
        return SimpleNamespace(data={} if self.seule else [])

    def __getattr__(self, _nom):
        return lambda *_a, **_k: self


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setattr(lectures, "supabase", SimpleNamespace(table=_Requete))
    monkeypatch.setattr(lectures, "_lire_surcharges_fenetre", lambda *_a: {})
    monkeypatch.setattr(lectures, "lire_complements", lambda *_a: None)
    monkeypatch.setattr(
        lecteur_contrats, "sortie_du_contrat", lambda employee_id, debut: "2026-10-31"
    )


def test_la_relecture_voit_la_sortie_du_depart_cloture_comme_le_generateur(base):
    lu = lectures.lire_lectures_salarie("e-ines", [(2026, 10)])
    au_calcul = {**FICHE, "exit_last_working_day": resolve_date_sortie(dict(FICHE))}
    assert au_calcul["exit_last_working_day"] == "2026-10-31"
    assert lu.employee["exit_last_working_day"] == "2026-10-31"
    assert _fiche(lu.employee) == _fiche(au_calcul)
