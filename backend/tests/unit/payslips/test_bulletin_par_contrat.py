"""Novembre a deux bulletins, un par contrat : chacun se lit, se défait et se
remplace par sa clé (D3, docs/superpowers/specs/2026-10-31-deux-contrats-meme-mois-design.md).

Le CDD finit le 10/11, le nouveau contrat commence le 17/11. Le bulletin de
l'ancien porte `contract_period_id` (son contrat rangé) ; celui du nouveau, une
clé nulle.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payslips.application import commands
from app.modules.payslips.application import effets_du_bulletin as effets
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipBadRequestError,
)
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = [pytest.mark.unit, pytest.mark.effets_en_base]

SAL, SOC, RANGE = "emp-1", "co-1", "periode-1"
_LECTEUR = "app.modules.employees.application.contrat_du_mois.lecteur_contrats"


def _bulletin(id_: str, entree: str, contrat: str | None = None) -> dict:
    return {
        "id": id_,
        "company_id": SOC,
        "employee_id": SAL,
        "year": 2026,
        "month": 11,
        "status": "brouillon",
        "contract_period_id": contrat,
        "pdf_storage_path": f"{SOC}/{SAL}/bulletins/{id_}.pdf",
        "payslip_data": {"en_tete": {"salarie": {"date_entree": entree}}},
    }


@pytest.fixture
def base(monkeypatch):
    b = BaseEnMemoire(
        {
            "payslips": [
                _bulletin("ancien", "2026-07-01", RANGE),
                _bulletin("nouveau", "2026-11-17"),
            ]
        }
    )
    b.brancher(monkeypatch)
    return b


class TestLectureParContrat:
    def test_le_bulletin_existant_est_celui_de_la_cle(self, base):
        assert commands._fetch_existing_payslip(SAL, 2026, 11)["id"] == "nouveau"
        assert commands._fetch_existing_payslip(SAL, 2026, 11, RANGE)["id"] == "ancien"

    def test_les_effets_visent_le_bulletin_de_la_cle(self, base):
        assert effets._bulletin_du_mois(SAL, 2026, 11) == "nouveau"
        assert effets._bulletin_du_mois(SAL, 2026, 11, RANGE) == "ancien"

    def test_le_pdf_remplace_est_celui_de_la_cle(self, base):
        from app.core import database
        from app.modules.payroll.documents.pdf_du_bulletin import chemin_enregistre

        client = database.supabase
        assert chemin_enregistre(client, SOC, SAL, 2026, 11).endswith("/nouveau.pdf")
        assert chemin_enregistre(client, SOC, SAL, 2026, 11, RANGE).endswith("/ancien.pdf")


class TestEffetsParMois:
    """Le CET et la modulation se défont par mois : le bulletin de l'ancien
    contrat n'y touche pas (le nouveau contrat est refusé si l'ancien en portait)."""

    @pytest.fixture
    def crochets(self):
        with patch(
            "app.modules.cet.application.payroll_hook.defaire_application_en_paie", return_value=0
        ) as cet, patch(
            "app.modules.modulation.application.payroll_hook.defaire_credits_de_paie", return_value=0
        ) as modulation, patch(
            "app.modules.employee_loans.application.annulation.defaire_retenues_du_bulletin",
            return_value=0,
        ) as prets, patch(
            "app.modules.saisies_avances.application.annulation.defaire_remboursements_du_bulletin",
            return_value=0,
        ):
            yield cet, modulation, prets

    def test_le_contrat_de_la_fiche_defait_ses_effets_du_mois(self, crochets):
        cet, modulation, prets = crochets
        effets.defaire_effets_du_bulletin(SAL, 2026, 11, payslip_id="nouveau")
        cet.assert_called_once_with(SAL, 2026, 11)
        modulation.assert_called_once_with(SAL, 2026, 11)
        prets.assert_called_once_with("nouveau")

    def test_le_contrat_range_ne_defait_que_ses_propres_retenues(self, crochets):
        cet, modulation, prets = crochets
        effets.defaire_effets_du_bulletin(
            SAL, 2026, 11, payslip_id="ancien", contract_period_id=RANGE
        )
        cet.assert_not_called()
        modulation.assert_not_called()
        prets.assert_called_once_with("ancien")

    def test_supprimer_le_bulletin_de_l_ancien_contrat_garde_le_cet_du_mois(self, base, crochets):
        cet, _, prets = crochets
        with patch(
            "app.modules.employee_loans.application.annulation.refus_de_defaire", return_value=None
        ):
            effets.defaire_avant_suppression("ancien")
        cet.assert_not_called()
        prets.assert_called_once_with("ancien")


class TestGenerable:
    def test_le_contrat_range_se_calcule_sur_sa_fiche(self):
        fiche = {
            "id": SAL,
            "company_id": SOC,
            "employment_status": "actif",
            "hire_date": "2026-11-17",
            "contract_type": "CDD",
        }
        periode = {
            "id": RANGE,
            "employee_id": SAL,
            "fiche": {"hire_date": "2026-07-01", "contract_type": "CDD", "contract_end_date": "2026-11-10"},
        }
        with patch.object(commands._employee_repository, "get_by_id_only", return_value=fiche), patch.object(
            commands, "enrich_employee_with_exit_context", side_effect=lambda e: e
        ), patch.object(commands, "raison_de_blocage_avant_bascule", return_value=None), patch.object(
            commands.effets, "refuser_si_effets_non_defaisables"
        ) as refus, patch(f"{_LECTEUR}.contrat_range", return_value=periode), patch(
            f"{_LECTEUR}.sortie_du_contrat", return_value="2026-11-10"
        ), patch.object(commands, "_raison_de_blocage_du_salarie", return_value=None):
            employe = commands.salarie_generable(SAL, 2026, 11, RANGE)
        assert employe["hire_date"] == "2026-07-01"
        assert employe["exit_last_working_day"] == "2026-11-10"
        refus.assert_called_once_with(SAL, 2026, 11, contract_period_id=RANGE)

    def test_un_contrat_sans_fiche_rangee_est_refuse(self):
        fiche = {"id": SAL, "company_id": SOC, "employment_status": "actif", "hire_date": "2026-11-17"}
        with patch.object(commands._employee_repository, "get_by_id_only", return_value=fiche), patch.object(
            commands, "enrich_employee_with_exit_context", side_effect=lambda e: e
        ), patch(f"{_LECTEUR}.contrat_range", return_value=None):
            with pytest.raises(PayslipBadRequestError, match="contrat précédent"):
                commands.salarie_generable(SAL, 2026, 11, RANGE)


class TestGardeDuContratDeLaFiche:
    """Le marquage du mois partagé a manqué : le bulletin à clé nulle est encore
    celui de l'ancien contrat. Le premier bulletin du nouveau ne le remplace pas."""

    FICHE = {"id": SAL, "company_id": SOC, "hire_date": "2026-11-17"}

    def test_refus_si_le_bulletin_en_place_est_d_un_autre_contrat(self):
        en_place = _bulletin("ancien-non-range", "2026-07-01")
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois", return_value={"id": RANGE, "date_fin": "2026-11-10"}):
            with pytest.raises(PayslipBadRequestError, match="n'est pas rangé avec le contrat précédent"):
                commands._check_contrat_du_bulletin(
                    self.FICHE, GeneratePayslipInput(employee_id=SAL, year=2026, month=11), en_place
                )

    def test_le_bulletin_du_nouveau_contrat_se_regenere(self):
        en_place = _bulletin("nouveau", "2026-11-17")
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois", return_value={"id": RANGE, "date_fin": "2026-11-10"}):
            commands._check_contrat_du_bulletin(
                self.FICHE, GeneratePayslipInput(employee_id=SAL, year=2026, month=11), en_place
            )

    def test_hors_mois_partage_rien_n_est_lu(self):
        en_place = _bulletin("ancien", "2026-07-01")
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois") as lire:
            commands._check_contrat_du_bulletin(
                {**self.FICHE, "hire_date": "2026-07-01"},
                GeneratePayslipInput(employee_id=SAL, year=2026, month=11),
                en_place,
            )
        lire.assert_not_called()

    def test_le_bulletin_du_contrat_range_n_est_pas_garde(self):
        en_place = _bulletin("ancien", "2026-07-01", RANGE)
        with patch(f"{_LECTEUR}.contrat_qui_finit_dans_le_mois") as lire:
            commands._check_contrat_du_bulletin(
                self.FICHE,
                GeneratePayslipInput(employee_id=SAL, year=2026, month=11, contract_period_id=RANGE),
                en_place,
            )
        lire.assert_not_called()


class TestGenerateur:
    def test_les_variables_du_bulletin_sont_celles_de_sa_cle(self, monkeypatch):
        from app.core import database
        from app.modules.payroll.documents.bulletin_par_contrat import (
            variables_du_bulletin,
        )

        BaseEnMemoire(
            {
                "monthly_inputs": [
                    {"id": "prime-ancien", "employee_id": SAL, "year": 2026, "month": 11, "contract_period_id": RANGE},
                    {"id": "prime-nouveau", "employee_id": SAL, "year": 2026, "month": 11},
                ]
            }
        ).brancher(monkeypatch)
        client = database.supabase
        assert [l["id"] for l in variables_du_bulletin(client, SAL, 2026, 11, None).data] == ["prime-nouveau"]
        assert [l["id"] for l in variables_du_bulletin(client, SAL, 2026, 11, RANGE).data] == ["prime-ancien"]

    def test_le_pdf_du_contrat_range_porte_son_nom(self):
        from app.modules.payroll.documents.bulletin_par_contrat import suffixe_du_pdf

        assert suffixe_du_pdf(None) == ""
        assert suffixe_du_pdf(RANGE) == "_contrat-precedent"


def test_le_bulletin_du_contrat_range_ne_se_supprime_pas():
    with patch.object(commands, "_refuser_si_importe"), patch.object(
        commands,
        "_fetch_payslip_status",
        return_value={"id": "ancien", "status": "brouillon", "contract_period_id": RANGE},
    ), patch.object(commands.effets, "defaire_avant_suppression") as defaire:
        with pytest.raises(PayslipBadRequestError, match="contrat précédent"):
            commands.delete_payslip("ancien")
    defaire.assert_not_called()
