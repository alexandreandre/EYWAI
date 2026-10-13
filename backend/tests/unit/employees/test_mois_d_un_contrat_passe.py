"""Après « Nouveau contrat », les mois de l'ancien contrat restent corrigeables [D4].

Relevé du 12/10/2026 (vidéo H) : la fiche porte le nouveau contrat (entrée le
01/11/2026) ; les bulletins validés du CDD précédent n'étaient plus ni
régénérables (« pas encore présent dans l'entreprise (entrée le 01/11/2026) »)
ni supprimables (un validé se supprime après « Régénérer »), et le salarié
n'était plus supprimable (409 : il a des bulletins).

Le contrat rangé garde la fiche qu'il avait (les champs que « Nouveau
contrat » remplace) ; un mois de ce contrat se calcule sur elle.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.employees.domain.nouveau_contrat import (
    ContratPrecedent,
    Demande,
    ecritures,
    fiche_rangee,
)
from app.modules.payslips.application import commands
from app.modules.payslips.application.dto import PayslipBadRequestError
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

_LECTEUR = "app.modules.employees.application.contrat_du_mois.lecteur_contrats"

#: La fiche du CDD, juste avant « Nouveau contrat ».
FICHE_DU_CDD = {
    "id": "emp-1",
    "company_id": "co-1",
    "employment_status": "parti",
    "current_exit_id": None,
    "hire_date": "2026-07-01",
    "date_debut_execution": None,
    "date_conclusion_contrat": "2026-06-20",
    "contract_type": "CDD",
    "contract_end_date": "2026-10-15",
    "duree_hebdomadaire": 35,
    "is_temps_partiel": False,
    "job_title": "Opérateur",
    "seniority_reference_date": None,
    "specificites_paie": {},
    "nir": "1850574001234",
    "date_naissance": "1985-05-01",
    "adresse": {"ville": "Lyon"},
    "coordonnees_bancaires": {"iban": "FR7630001007941234567890185"},
    "salaire_de_base": {"type": "mensuel", "valeur": 1950},
    "statut": "Non-Cadre",
}
PRECEDENT = ContratPrecedent(contract_type="CDD", debut=date(2026, 7, 1), fin=date(2026, 10, 15))
DEMANDE = Demande(
    date_debut=date(2026, 11, 1),
    contract_type="CDI",
    date_fin=None,
    duree_hebdomadaire=39,
    salaire_mensuel=2100,
    job_title="Chef d'équipe",
    reprendre_anciennete=False,
)


def _apres_nouveau_contrat() -> tuple[dict, dict]:
    """(la fiche après « Nouveau contrat », la ligne du contrat rangé)."""
    _, nouvelle, _ = ecritures(FICHE_DU_CDD, PRECEDENT, DEMANDE)
    rangee = fiche_rangee(FICHE_DU_CDD, nouvelle)
    periode = {
        "id": "periode-1",
        "employee_id": "emp-1",
        "company_id": "co-1",
        "contract_type": "CDD",
        "date_debut": "2026-07-01",
        "date_fin": "2026-10-15",
        "fiche": rangee,
    }
    return {**FICHE_DU_CDD, **nouvelle}, periode


class TestFicheRangee:
    def test_le_contrat_range_garde_les_champs_que_le_nouveau_remplace(self):
        _, nouvelle, _ = ecritures(FICHE_DU_CDD, PRECEDENT, DEMANDE)
        rangee = fiche_rangee(FICHE_DU_CDD, nouvelle)
        assert rangee["hire_date"] == "2026-07-01"
        assert rangee["contract_type"] == "CDD"
        assert rangee["contract_end_date"] == "2026-10-15"
        assert rangee["duree_hebdomadaire"] == 35
        assert rangee["date_conclusion_contrat"] == "2026-06-20"
        assert rangee["job_title"] == "Opérateur"
        # Le statut et le départ ne sont pas ceux d'un contrat : ils restent hors de la fiche rangée.
        assert "employment_status" not in rangee
        assert "current_exit_id" not in rangee


class TestFicheDuMois:
    def test_un_mois_de_l_ancien_contrat_se_lit_sur_sa_fiche(self):
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_passe_du_mois", return_value=periode) as lire:
            du_mois = fiche_du_mois(fiche, 2026, 10)
        lire.assert_called_once_with("emp-1", 2026, 10)
        assert du_mois["hire_date"] == "2026-07-01"
        assert du_mois["contract_type"] == "CDD"
        assert du_mois["contract_end_date"] == "2026-10-15"
        assert du_mois["duree_hebdomadaire"] == 35
        assert du_mois["employment_status"] == "parti"
        assert du_mois["current_exit_id"] is None

    def test_un_mois_du_contrat_en_cours_ne_lit_rien(self):
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, _ = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_passe_du_mois") as lire:
            assert fiche_du_mois(fiche, 2026, 11) == fiche
        lire.assert_not_called()

    def test_un_contrat_range_sans_sa_fiche_ne_change_rien(self):
        """Contrat passé saisi à la main (ou avant la colonne) : la fiche n'est pas
        connue, le mois reste refusé comme avant plutôt que calculé faux."""
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_passe_du_mois", return_value={**periode, "fiche": None}):
            assert fiche_du_mois(fiche, 2026, 10) == fiche

    def test_le_lecteur_trouve_le_contrat_du_mois(self, monkeypatch):
        from app.modules.employees.application.contrat_du_mois import LecteurContrats

        _, periode = _apres_nouveau_contrat()
        autre = {**periode, "id": "periode-0", "date_debut": "2025-01-06", "date_fin": "2025-03-31"}
        BaseEnMemoire({"employee_contract_periods": [autre, periode]}).brancher(monkeypatch)
        assert LecteurContrats().contrat_passe_du_mois("emp-1", 2026, 10)["id"] == "periode-1"
        assert LecteurContrats().contrat_passe_du_mois("emp-1", 2026, 7)["id"] == "periode-1"
        assert LecteurContrats().contrat_passe_du_mois("emp-1", 2025, 6) is None


class TestGenerable:
    @pytest.fixture
    def fiche(self):
        fiche, periode = _apres_nouveau_contrat()
        with patch.object(commands._employee_repository, "get_by_id_only", return_value=fiche), patch.object(
            commands, "raison_de_blocage_avant_bascule", return_value=None
        ), patch(f"{_LECTEUR}.contrat_passe_du_mois", return_value=periode), patch(
            f"{_LECTEUR}.sortie_du_contrat", return_value="2026-10-15"
        ):
            yield

    def test_le_dernier_mois_de_l_ancien_contrat_se_regenere(self, fiche):
        employe = commands.salarie_generable("emp-1", 2026, 10)
        assert employe["contract_type"] == "CDD"
        assert employe["hire_date"] == "2026-07-01"
        assert employe["exit_last_working_day"] == "2026-10-15"

    def test_un_mois_entre_deux_contrats_reste_refuse(self, fiche):
        with patch(f"{_LECTEUR}.contrat_passe_du_mois", return_value=None):
            with pytest.raises(PayslipBadRequestError, match="pas encore présent"):
                commands.salarie_generable("emp-1", 2026, 6)


class TestRangement:
    def test_creer_range_le_contrat_avec_sa_fiche(self, monkeypatch):
        from tests.unit.employees.test_nouveau_contrat_service import EMP, SOC, _Base, _payload

        from app.modules.employees.application import nouveau_contrat as service

        b = _Base(bulletins={(2026, 5)})
        monkeypatch.setattr(service, "supabase", b)
        monkeypatch.setattr(service, "lire_bascule", lambda _c: None)
        ranges: list = []

        def ranger(employee_id, company_id, payload, fiche=None):
            ranges.append(fiche)
            return {"id": "periode-1"}

        monkeypatch.setattr(service, "add_contract_period", ranger)
        monkeypatch.setattr(service, "apply_salary_update", lambda *a, **k: {"id": "s"})
        monkeypatch.setattr(service, "get_employee_by_id", lambda e, c: {"id": e})
        service.creer(EMP, SOC, _payload(), "rh-1")
        assert ranges[0]["hire_date"] == "2026-01-19"
        assert ranges[0]["contract_type"] == "CDD"
        assert ranges[0]["contract_end_date"] == "2026-05-31"

    def test_la_fiche_est_ecrite_avec_le_contrat(self, monkeypatch):
        from app.modules.employees.application import contract_periods

        base = BaseEnMemoire({"employee_contract_periods": []})
        base.brancher(monkeypatch)
        contract_periods.add_contract_period(
            "emp-1",
            "co-1",
            contract_periods.ContractPeriodIn(
                contract_type="CDD", date_debut=date(2026, 7, 1), date_fin=date(2026, 10, 15)
            ),
            fiche={"hire_date": "2026-07-01", "contract_type": "CDD"},
        )
        assert base.ligne("employee_contract_periods", employee_id="emp-1")["fiche"] == {
            "hire_date": "2026-07-01",
            "contract_type": "CDD",
        }

    def test_sans_la_colonne_le_contrat_se_range_quand_meme(self, monkeypatch):
        """Migration pas encore appliquée : le rangement ne doit pas faire échouer
        « Nouveau contrat » (la fiche reviendrait en arrière)."""
        from app.modules.employees.application import contract_periods

        base = BaseEnMemoire({"employee_contract_periods": []})
        base.brancher(monkeypatch)
        insert_reel = type(base.table("employee_contract_periods")).insert

        def insert(self, valeur):
            if "fiche" in valeur:
                raise RuntimeError(
                    "Could not find the 'fiche' column of 'employee_contract_periods' in the schema cache"
                )
            return insert_reel(self, valeur)

        monkeypatch.setattr(type(base.table("employee_contract_periods")), "insert", insert)
        ligne = contract_periods.add_contract_period(
            "emp-1",
            "co-1",
            contract_periods.ContractPeriodIn(
                contract_type="CDD", date_debut=date(2026, 7, 1), date_fin=date(2026, 10, 15)
            ),
            fiche={"hire_date": "2026-07-01"},
        )
        assert ligne["contract_type"] == "CDD"
        assert "fiche" not in base.ligne("employee_contract_periods", employee_id="emp-1")
