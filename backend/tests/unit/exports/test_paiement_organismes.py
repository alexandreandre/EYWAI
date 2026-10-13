"""Échéance du « Paiement organismes » : le 15 du mois suivant sous 50 salariés,
le 5 du mois suivant à partir de 50.

Une cotisation de salaires du mois M se paie le 15 de M+1 (Urssaf, DSN) pour les
sociétés de moins de 50 salariés. La date était le 15 du mois de paie lui-même,
un mois trop tôt. À 50 salariés et plus, le 5 de M+1 (décision du 12/10/2026,
salaires payés dans le mois ; service-public F34059), selon l'effectif des seuils
de l'année.
"""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_paiement_organismes as organismes

pytestmark = pytest.mark.unit

DETAIL = [
    {
        "Organisme": "URSSAF",
        "Libellé cotisation": "Maladie",
        "Part salariale": 0,
        "Part patronale": 100.0,
        "Total cotisations": 100.0,
    }
]


def _societe(effectif, annee=2026):
    return {"effectif": 3, "settings": {"effectif_seuils": {str(annee): effectif}}}


class TestEcheance:
    def test_sous_50_salaries_le_15_du_mois_suivant(self):
        lignes = organismes._build_payment_rows(DETAIL, "2026-09", effectif=12)
        assert lignes[0]["Échéance"] == "2026-10-15"

    def test_decembre_passe_a_janvier_de_l_annee_suivante(self):
        lignes = organismes._build_payment_rows(DETAIL, "2026-12", effectif=49)
        assert lignes[0]["Échéance"] == "2027-01-15"

    def test_a_partir_de_50_salaries_le_5_du_mois_suivant(self):
        lignes = organismes._build_payment_rows(DETAIL, "2026-09", effectif=50)
        assert lignes[0]["Échéance"] == "2026-10-05"
        lignes = organismes._build_payment_rows(DETAIL, "2026-12", effectif=120)
        assert lignes[0]["Échéance"] == "2027-01-05"


class TestApercuEtFichier:
    def _apercu(self, societe):
        with patch.object(
            organismes, "get_charges_sociales_data", return_value=(DETAIL, [], {"employees_count": 4})
        ), patch.object(organismes, "_charger_societe", return_value=societe):
            return organismes.preview_paiement_organismes("co-1", "2026-09")

    def test_l_effectif_des_seuils_de_l_annee_decide(self):
        apercu = self._apercu(_societe(12))
        assert apercu["details"]["lines"][0]["Échéance"] == "2026-10-15"

    def test_l_effectif_saisi_prime_sur_le_nombre_de_comptes(self):
        # 3 comptes mais 60 salariés saisis pour l'année : palier 50 et plus
        apercu = self._apercu({"effectif": 3, "settings": {"effectif_seuils": {"2026": 60}}})
        assert apercu["details"]["lines"][0]["Échéance"] == "2026-10-05"

    def test_a_50_et_plus_l_echeance_n_est_plus_a_confirmer(self):
        apercu = self._apercu(_societe(60))
        assert not any("à confirmer" in w for w in apercu["warnings"])

    def test_sous_50_aucun_avertissement_d_echeance(self):
        apercu = self._apercu(_societe(12))
        assert not any("50 salariés" in w for w in apercu["warnings"])

    def test_le_fichier_porte_la_meme_echeance(self):
        with patch.object(
            organismes, "get_charges_sociales_data", return_value=(DETAIL, [], {})
        ), patch.object(organismes, "_charger_societe", return_value=_societe(12)):
            contenu = organismes.generate_paiement_organismes_export(
                "co-1", "2026-09", file_format="csv"
            ).decode("utf-8-sig")
        assert "2026-10-15" in contenu
        assert "2026-09-15" not in contenu
