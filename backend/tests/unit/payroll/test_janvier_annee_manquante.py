"""Une année absente d'un barème ne passe pas en silence (R-611, chaque janvier).

Rien de tout cela ne change un montant : le calcul continue avec ce qu'il connaît,
et l'alerte dit qu'il faut compléter. Les années déjà couvertes (2026) restent
muettes : aucun bulletin existant ne bouge.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.application.preflight_anomalies import (
    _anomalies_smh_metallurgie,
)
from app.modules.payroll.domain.smh_metallurgie import bareme_smh_manque
from app.modules.payroll.engine.baremes_loader import (
    CODE_BAREME_ANNEE_PASSEE,
    CODE_PLAFOND_SS_NON_DECLARE,
    controler_baremes_sans_annee,
    controler_jour_solidarite,
)
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit

PSS_2026 = {"mensuel": 4005.0, "annuel": 48060.0}
PSS_NOUVEAU = {"mensuel": 4100.0, "annuel": 49200.0}
IJ_2026 = {
    "maladie": 42.97,
    "historique": [
        {"date_debut": "2026-01-01", "maladie": 42.97},
        {"date_debut": "2026-11-01", "maladie": 42.97},
    ],
}


class TestPlafondDeLaSecuriteSociale:
    def test_2026_ne_dit_rien(self):
        assert controler_baremes_sans_annee({"pss": PSS_2026}, 2026) == []

    def test_le_plafond_2026_applique_en_2027_alerte(self):
        alertes = controler_baremes_sans_annee({"pss": PSS_2026}, 2027)
        assert len(alertes) == 1
        assert alertes[0]["code"] == CODE_BAREME_ANNEE_PASSEE
        assert alertes[0]["config_key"] == "pss"
        assert "2026" in alertes[0]["message"] and "2027" in alertes[0]["message"]
        # Visible, sans bloquer ni la génération ni la validation.
        assert alertes[0]["severity"] == "warning"
        assert alertes[0]["critique"] is False

    def test_un_plafond_nouveau_absent_du_code_le_dit(self):
        alertes = controler_baremes_sans_annee({"pss": PSS_NOUVEAU}, 2027)
        assert [a["code"] for a in alertes] == [CODE_PLAFOND_SS_NON_DECLARE]
        assert "2027" in alertes[0]["message"]

    def test_regenerer_2026_avec_le_nouveau_plafond_ne_double_pas_l_alerte(self):
        assert controler_baremes_sans_annee({"pss": PSS_NOUVEAU}, 2026) == []

    def test_sans_bareme_rien(self):
        assert controler_baremes_sans_annee({}, 2027) == []
        assert controler_baremes_sans_annee({"pss": {"annuel": 48060}}, 2027) == []


class TestPlafondsIJ:
    def test_2026_ne_dit_rien(self):
        assert controler_baremes_sans_annee({"ij_plafonds": IJ_2026}, 2026) == []

    def test_des_paliers_de_2026_appliques_en_2027_alertent(self):
        alertes = controler_baremes_sans_annee({"ij_plafonds": IJ_2026}, 2027)
        assert [a["config_key"] for a in alertes] == ["ij_plafonds"]
        assert alertes[0]["code"] == CODE_BAREME_ANNEE_PASSEE

    def test_un_palier_2027_fait_taire_l_alerte(self):
        bareme = {
            "historique": [*IJ_2026["historique"], {"date_debut": "2027-01-01", "maladie": 44.0}]
        }
        assert controler_baremes_sans_annee({"ij_plafonds": bareme}, 2027) == []

    def test_sans_palier_rien(self):
        assert controler_baremes_sans_annee({"ij_plafonds": {"maladie": 42.97}}, 2027) == []


class TestJourDeSolidarite:
    def test_la_date_de_2026_ne_vaut_pas_pour_2027(self):
        alertes = controler_jour_solidarite({"jour_solidarite": "2026-05-25"}, 2027)
        assert len(alertes) == 1
        assert "25/05/2026" in alertes[0]["message"] and "2027" in alertes[0]["message"]
        assert alertes[0]["critique"] is False

    def test_l_annee_du_bulletin_ne_dit_rien(self):
        assert controler_jour_solidarite({"jour_solidarite": "2026-05-25"}, 2026) == []

    @pytest.mark.parametrize("reglage", [None, {}, {"jour_solidarite": None}, {"jour_solidarite": "lundi"}])
    def test_sans_date_lisible_rien(self, reglage):
        assert controler_jour_solidarite(reglage, 2027) == []


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=300.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": PSS_2026,
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


def _maternite(debut: str, fin: str, ctx: SimpleNamespace) -> dict:
    arret = {
        "arret_type": "maternite", "date_debut": debut, "date_fin": fin,
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
        "salaires_bruts_reference": [300.0, 300.0, 300.0],
    }
    reglages = {"apply_legal_maintenance": True, "maintain_parental_leave": False, "subrogation_mode": "never"}
    periode = (date.fromisoformat(debut).replace(day=1), date.fromisoformat(fin))
    return calculer_maintien(arret, ctx, reglages, *periode)["ijss"]


class TestMinimumIJMaternite:
    def test_2026_garde_le_minimum_sans_alerte(self):
        ctx = _ctx()
        ijss = _maternite("2026-09-01", "2026-09-30", ctx)
        assert round(ijss["ijss_journaliere"], 2) == 11.12
        assert not getattr(ctx, "alertes_baremes", [])

    def test_2027_sans_minimum_le_dit_une_seule_fois(self):
        ctx = _ctx()
        _maternite("2027-02-01", "2027-02-28", ctx)
        _maternite("2027-02-01", "2027-02-28", ctx)
        codes = [a["code"] for a in ctx.alertes_baremes]
        assert codes == ["ij_maternite_minimum_absent"]
        assert "2027" in ctx.alertes_baremes[0]["message"]


class TestSmhMetallurgie:
    def test_l_annee_couverte_ne_manque_pas(self):
        assert bareme_smh_manque(2026) is False

    def test_une_annee_passee_ne_manque_pas(self):
        # Le contrôle n'a jamais couvert 2025 : pas d'alerte après coup.
        assert bareme_smh_manque(2025) is False

    def test_l_annee_suivante_manque(self):
        assert bareme_smh_manque(2027) is True

    def test_la_revue_le_dit_a_partir_d_octobre(self):
        salarie = {
            "id": "e1", "first_name": "A", "last_name": "B", "team_id": None,
            "contract_type": "CDI",
            "classification_conventionnelle": {"idcc": "3248", "niveau_dsn": "3 A"},
        }
        anomalies = _anomalies_smh_metallurgie("c1", 2027, 10, [salarie])
        assert len(anomalies) == 1
        assert anomalies[0].type == "minimum_annuel"
        assert "2027" in anomalies[0].message

    def test_avant_octobre_rien(self):
        salarie = {
            "id": "e1", "first_name": "A", "last_name": "B", "team_id": None,
            "contract_type": "CDI",
            "classification_conventionnelle": {"idcc": "3248", "niveau_dsn": "3 A"},
        }
        assert _anomalies_smh_metallurgie("c1", 2027, 9, [salarie]) == []
