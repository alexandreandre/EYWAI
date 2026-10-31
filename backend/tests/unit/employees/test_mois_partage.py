"""Un contrat finit le 10/11, un autre commence le 17/11 : novembre est partagé [D3].

Le bulletin de l'ancien contrat, dans ce mois, se calcule sur la fiche rangée
avec lui, même si le mois est celui où le contrat de la fiche commence.
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
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.employees.test_mois_d_un_contrat_passe import FICHE_DU_CDD

pytestmark = pytest.mark.unit

_LECTEUR = "app.modules.employees.application.contrat_du_mois.lecteur_contrats"

CDD = {**FICHE_DU_CDD, "contract_end_date": "2026-11-10"}
PRECEDENT = ContratPrecedent(contract_type="CDD", debut=date(2026, 7, 1), fin=date(2026, 11, 10))
DEMANDE = Demande(
    date_debut=date(2026, 11, 17),
    contract_type="CDD",
    date_fin=date(2027, 2, 26),
    duree_hebdomadaire=35,
    salaire_mensuel=2100,
    job_title="Peintre",
    reprendre_anciennete=True,
)


def _apres_nouveau_contrat() -> tuple[dict, dict]:
    _, nouvelle, _ = ecritures(CDD, PRECEDENT, DEMANDE)
    periode = {
        "id": "periode-1",
        "employee_id": "emp-1",
        "company_id": "co-1",
        "contract_type": "CDD",
        "date_debut": "2026-07-01",
        "date_fin": "2026-11-10",
        "fiche": fiche_rangee(CDD, nouvelle),
    }
    return {**CDD, **nouvelle}, periode


class TestFicheDuContratRange:
    def test_au_mois_partage_la_fiche_rangee(self):
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_range", return_value=periode) as lire:
            du_mois = fiche_du_mois(fiche, 2026, 11, contract_period_id="periode-1")
        lire.assert_called_once_with("periode-1")
        assert du_mois["hire_date"] == "2026-07-01"
        assert du_mois["contract_end_date"] == "2026-11-10"
        assert du_mois["employment_status"] == "parti"

    def test_sans_contrat_le_mois_partage_est_celui_de_la_fiche(self):
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, _ = _apres_nouveau_contrat()
        assert fiche_du_mois(fiche, 2026, 11) == fiche

    def test_un_contrat_sans_fiche_rangee_est_refuse(self):
        """Jamais le calcul d'un contrat sur la fiche d'un autre."""
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_range", return_value={**periode, "fiche": None}):
            with pytest.raises(ValueError, match="contrat précédent"):
                fiche_du_mois(fiche, 2026, 11, contract_period_id="periode-1")

    def test_un_contrat_d_un_autre_salarie_est_refuse(self):
        from app.modules.employees.application.contrat_du_mois import fiche_du_mois

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_range", return_value={**periode, "employee_id": "emp-2"}):
            with pytest.raises(ValueError, match="contrat précédent"):
                fiche_du_mois(fiche, 2026, 11, contract_period_id="periode-1")


class TestMoisPartage:
    def test_le_mois_ou_l_un_finit_et_l_autre_commence(self):
        from app.modules.employees.application.contrat_du_mois import mois_partage

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois", return_value=periode) as lire:
            assert mois_partage(fiche, 2026, 11)["id"] == "periode-1"
        lire.assert_called_once_with("emp-1", 2026, 11)

    def test_les_autres_mois_ne_sont_pas_partages(self):
        from app.modules.employees.application.contrat_du_mois import mois_partage

        fiche, periode = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois", return_value=periode) as lire:
            assert mois_partage(fiche, 2026, 12) is None
            assert mois_partage(fiche, 2026, 10) is None
        lire.assert_not_called()

    def test_un_contrat_qui_commence_au_premier_ne_partage_rien(self):
        from app.modules.employees.application.contrat_du_mois import mois_partage

        fiche, _ = _apres_nouveau_contrat()
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois", return_value=None):
            assert mois_partage(fiche, 2026, 11) is None

    def test_le_lecteur_trouve_le_contrat_qui_finit_dans_le_mois(self, monkeypatch):
        from app.modules.employees.application.contrat_du_mois import LecteurContrats

        _, periode = _apres_nouveau_contrat()
        sans_fiche = {**periode, "id": "periode-0", "fiche": None}
        BaseEnMemoire({"employee_contract_periods": [sans_fiche, periode]}).brancher(monkeypatch)
        lecteur = LecteurContrats()
        assert lecteur.contrat_qui_finit_dans_le_mois("emp-1", 2026, 11)["id"] == "periode-1"
        assert lecteur.contrat_qui_finit_dans_le_mois("emp-1", 2026, 10) is None
        assert lecteur.contrat_range("periode-1")["date_fin"] == "2026-11-10"
        assert lecteur.contrat_range("inconnu") is None
