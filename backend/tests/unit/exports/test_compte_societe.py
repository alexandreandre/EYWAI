"""Le compte bancaire de la société est le donneur d'ordre des remises SEPA.

Avant, le fichier portait « Entreprise » et aucun IBAN débiteur : la banque
rejetait la remise ou la complétait. Le compte (IBAN, BIC, titulaire) est lu
dans les paramètres de paie de la société ; son absence bloque l'aperçu du
virement avec un message qui dit où le saisir.
"""

import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import (
    export_paiement_salaires,
    export_sepa,
    export_virement_acomptes as acomptes,
)
from app.modules.exports.infrastructure.compte_societe import compte_depuis_societe

pytestmark = pytest.mark.unit

NS = "{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}"
IBAN_SOCIETE = "FR1420041010050500013M02606"
IBAN_SALARIE = "FR7630001007941234567890185"
COMPTE = {"iban": IBAN_SOCIETE, "bic": "BNPAFRPP", "titulaire": "SAS Exemple"}


def _ligne():
    return {
        "Nom": "Dupont",
        "Prénom": "Jean",
        "IBAN": IBAN_SALARIE,
        "BIC": "BNPAFRPP",
        "Montant": 1800.0,
        "Statut_controle": "OK",
    }


class TestLectureDuCompte:
    def test_lu_dans_settings(self):
        societe = {"company_name": "Exemple", "settings": {"compte_bancaire": COMPTE}}
        assert compte_depuis_societe(societe) == COMPTE

    def test_titulaire_par_defaut_le_nom_de_la_societe(self):
        societe = {
            "company_name": "Exemple",
            "settings": {"compte_bancaire": {"iban": IBAN_SOCIETE}},
        }
        compte = compte_depuis_societe(societe)
        assert compte["titulaire"] == "Exemple"
        assert compte["bic"] == ""

    def test_absent(self):
        assert compte_depuis_societe({"company_name": "X", "settings": {}}) is None
        assert compte_depuis_societe({"settings": None}) is None
        assert compte_depuis_societe(None) is None

    def test_iban_invalide_compte_pour_absent(self):
        societe = {"settings": {"compte_bancaire": {"iban": "FR7630001007941234567890186"}}}
        assert compte_depuis_societe(societe) is None


class TestApercuSalaires:
    def _apercu(self, compte):
        totals = {"virements_count": 1, "total_amount": 1800.0}
        with patch.object(
            export_paiement_salaires,
            "get_paiement_salaires_data",
            return_value=([_ligne()], totals, [], []),
        ), patch.object(export_paiement_salaires, "charger_compte_societe", return_value=compte):
            return export_paiement_salaires.preview_paiement_salaires("co-1", "2026-07")

    def test_sans_compte_l_apercu_est_bloque_et_dit_ou_le_saisir(self):
        apercu = self._apercu(None)
        assert apercu["can_generate"] is False
        anomalie = next(a for a in apercu["anomalies"] if "Compte bancaire de la société" in a["message"])
        assert anomalie["severity"] == "blocking"
        assert "Paramètres de paie" in anomalie["message"]

    def test_avec_compte_rien_ne_bloque(self):
        apercu = self._apercu(COMPTE)
        assert apercu["can_generate"] is True
        assert not any("Compte bancaire" in a["message"] for a in apercu["anomalies"])


class TestApercuSalairesEnCsv:
    """Le CSV se dépose à la main : rien d'un salarié ou de la société ne bloque tout (Elsa, 17/11)."""

    IBAN_FAUX = {
        "type": "error",
        "message": "IBAN manquant ou invalide - Jean Dupont",
        "severity": "blocking",
        "employee_id": "e-2",
        "employee_name": "Jean Dupont",
    }
    DOUBLON = {"type": "error", "message": "Doublon détecté - Paul Martin", "severity": "blocking"}

    def _apercu(self, compte, anomalies, bank_format="csv"):
        totals = {"virements_count": 1, "total_amount": 1800.0}
        with patch.object(
            export_paiement_salaires,
            "get_paiement_salaires_data",
            return_value=([_ligne()], totals, list(anomalies), []),
        ), patch.object(export_paiement_salaires, "charger_compte_societe", return_value=compte):
            return export_paiement_salaires.preview_paiement_salaires(
                "co-1", "2026-07", bank_format=bank_format
            )

    def test_sans_compte_de_la_societe_le_csv_sort(self):
        apercu = self._apercu(None, [])
        assert apercu["can_generate"] is True
        assert apercu["anomalies"] == []

    def test_un_iban_faux_ecarte_le_salarie_nomme_sans_bloquer(self):
        apercu = self._apercu(COMPTE, [self.IBAN_FAUX])
        assert apercu["can_generate"] is True
        assert apercu["anomalies"] == []
        assert any(w.startswith("Jean Dupont : IBAN manquant ou invalide, hors du fichier") for w in apercu["warnings"])

    def test_un_doublon_bloque_toujours(self):
        apercu = self._apercu(COMPTE, [self.IBAN_FAUX, self.DOUBLON])
        assert apercu["can_generate"] is False
        assert apercu["anomalies"] == [self.DOUBLON]

    def test_en_sepa_l_iban_faux_et_le_compte_bloquent_toujours(self):
        apercu = self._apercu(None, [self.IBAN_FAUX], bank_format="sepa")
        assert apercu["can_generate"] is False
        assert len(apercu["anomalies"]) == 2


class TestApercuAcomptes:
    def _apercu(self, compte, mode=None):
        totals = {"virements_count": 1, "employees_count": 1, "total_amount": 0.0}
        filters = {"mode": mode} if mode else None
        with patch.object(
            acomptes, "get_virement_acomptes_data", return_value=([_ligne()], totals, [], [])
        ), patch.object(acomptes, "charger_compte_societe", return_value=compte):
            return acomptes.preview_virement_acomptes("co-1", "2026-07", filters=filters)

    def test_sans_compte_l_apercu_est_bloque(self):
        apercu = self._apercu(None)
        assert apercu["can_generate"] is False
        assert any(
            "Compte bancaire de la société" in a["message"] and a["severity"] == "blocking"
            for a in apercu["anomalies"]
        )

    def test_avec_compte_rien_ne_bloque(self):
        assert self._apercu(COMPTE)["can_generate"] is True


class TestFichierSepa:
    def test_build_pain001_porte_le_compte_du_donneur_d_ordre(self):
        xml = export_sepa.build_pain001(
            [_ligne()],
            period="2026-07",
            label="Salaires",
            debtor_name="SAS Exemple",
            debtor_iban=IBAN_SOCIETE,
            debtor_bic="BNPAFRPP",
        )
        root = ET.fromstring(xml)
        assert root.find(f".//{NS}Dbtr/{NS}Nm").text == "SAS Exemple"
        assert root.find(f".//{NS}DbtrAcct/{NS}Id/{NS}IBAN").text == IBAN_SOCIETE
        assert root.find(f".//{NS}DbtrAgt/{NS}FinInstnId/{NS}BIC").text == "BNPAFRPP"

    def test_la_remise_des_salaires_lit_le_compte_de_la_societe(self):
        with patch.object(
            export_sepa, "get_paiement_salaires_data", return_value=([_ligne()], {}, [], [])
        ), patch.object(export_sepa, "charger_compte_societe", return_value=COMPTE):
            xml = export_sepa.generate_sepa_pain001("co-1", "2026-07")
        root = ET.fromstring(xml)
        assert root.find(f".//{NS}Dbtr/{NS}Nm").text == "SAS Exemple"
        assert root.find(f".//{NS}DbtrAcct/{NS}Id/{NS}IBAN").text == IBAN_SOCIETE

    def test_la_remise_des_acomptes_lit_le_compte_de_la_societe(self):
        with patch.object(
            acomptes, "get_virement_acomptes_data", return_value=([_ligne()], {}, [], [])
        ), patch.object(acomptes, "charger_compte_societe", return_value=COMPTE):
            xml = acomptes.generate_virement_acomptes_sepa("co-1", "2026-07")
        root = ET.fromstring(xml)
        assert root.find(f".//{NS}Dbtr/{NS}Nm").text == "SAS Exemple"
        assert root.find(f".//{NS}DbtrAcct/{NS}Id/{NS}IBAN").text == IBAN_SOCIETE
