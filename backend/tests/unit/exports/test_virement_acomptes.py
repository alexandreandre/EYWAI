"""Tests unitaires export « Virement acomptes »."""

import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_sepa
from app.modules.exports.infrastructure import export_virement_acomptes as module

pytestmark = pytest.mark.unit

NS = "{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}"

IBAN_VALIDE = "FR7630006000011234567890189"
IBAN_VALIDE_2 = "FR1420041010050500013M02606"


def _employe(
    employee_id="emp-1",
    prenom="Jean",
    nom="Dupont",
    iban=IBAN_VALIDE,
    bic="BNPAFRPP",
    payment_method=None,
):
    return {
        "id": employee_id,
        "first_name": prenom,
        "last_name": nom,
        "coordonnees_bancaires": {"iban": iban, "bic": bic},
        "salary_payment_method": payment_method,
    }


def _avance(advance_id="adv-1", employee_id="emp-1", payment_method=None, **extra):
    avance = {
        "id": advance_id,
        "employee_id": employee_id,
        "company_id": "co-1",
        "advance_type": "acompte_salaire",
        "status": "approved",
        "payment_method": payment_method,
        "prime_label": None,
    }
    avance.update(extra)
    return avance


def _source(
    employee_id="emp-1",
    advance_id="adv-1",
    montant=300.0,
    montant_indetermine=False,
    payment_id=None,
    advance=None,
    nature="Acompte sur salaire",
    date_evt="2026-07-05",
):
    return {
        "employee_id": employee_id,
        "advance_id": advance_id,
        "payment_id": payment_id,
        "advance": advance if advance is not None else _avance(advance_id, employee_id),
        "nature": nature,
        "montant": montant,
        "montant_indetermine": montant_indetermine,
        "date": date_evt,
    }


def _run(source, employees, exits=None, **kwargs):
    """Exécute get_virement_acomptes_data en isolant les accès base."""
    with patch.object(module, "_build_source_a_verser", return_value=source), \
         patch.object(module, "_build_source_verses", return_value=source), \
         patch.object(module, "_load_employees", return_value=employees), \
         patch.object(module, "_load_exits", return_value=exits or {}):
        return module.get_virement_acomptes_data("co-1", "2026-07", **kwargs)


class TestResteAVerser:
    def test_deduit_les_versements_deja_effectues(self):
        """Approuvé 500, déjà versé 200 : il reste 300 à virer."""
        avances = [_avance(approved_amount=500.0, requested_date="2026-07-01")]
        with patch.object(module, "_fetch_advances_a_verser", return_value=avances), \
             patch.object(module, "_total_paid_by_advance", return_value={"adv-1": 200.0}):
            source = module._build_source_a_verser("co-1", "2026-07", False)
        assert len(source) == 1
        assert source[0]["montant"] == 300.0

    def test_avance_entierement_versee_est_ecartee(self):
        avances = [_avance(approved_amount=500.0, requested_date="2026-07-01")]
        with patch.object(module, "_fetch_advances_a_verser", return_value=avances), \
             patch.object(module, "_total_paid_by_advance", return_value={"adv-1": 500.0}):
            source = module._build_source_a_verser("co-1", "2026-07", False)
        assert source == []

    def test_montant_approuve_absent_est_signale_et_non_vire(self):
        """Le cas observé en production : approuvée sans approved_amount."""
        avances = [_avance(approved_amount=None, requested_date="2026-07-01")]
        with patch.object(module, "_fetch_advances_a_verser", return_value=avances), \
             patch.object(module, "_total_paid_by_advance", return_value={}):
            source = module._build_source_a_verser("co-1", "2026-07", False)
        assert len(source) == 1
        assert source[0]["montant_indetermine"] is True

        rows, totals, anomalies, _ = _run(source, {"emp-1": _employe()})
        assert rows == []
        assert totals["virements_count"] == 0
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "blocking"
        assert "sans montant validé" in anomalies[0]["message"]


class TestControles:
    def test_ligne_valide_produit_un_virement(self):
        rows, totals, anomalies, _ = _run([_source()], {"emp-1": _employe()})
        assert len(rows) == 1
        assert rows[0]["Montant"] == 300.0
        assert rows[0]["IBAN"] == IBAN_VALIDE
        assert rows[0]["BIC"] == "BNPAFRPP"
        assert rows[0]["Statut_controle"] == "OK"
        assert rows[0]["Libelle"] == "Acompte sur salaire Juillet 2026"
        assert totals["total_amount"] == 300.0
        assert totals["employees_count"] == 1
        assert anomalies == []

    def test_iban_invalide_est_bloquant(self):
        rows, _, anomalies, _ = _run(
            [_source()], {"emp-1": _employe(iban="PASUNIBAN")}
        )
        assert rows == []
        assert anomalies[0]["severity"] == "blocking"
        assert "IBAN" in anomalies[0]["message"]

    def test_montant_negatif_est_bloquant(self):
        rows, _, anomalies, _ = _run([_source(montant=-10.0)], {"emp-1": _employe()})
        assert rows == []
        assert anomalies[0]["severity"] == "blocking"

    def test_reglement_en_especes_est_exclu_avec_avertissement(self):
        source = [_source(advance=_avance(payment_method="especes"))]
        rows, _, anomalies, warnings = _run(source, {"emp-1": _employe()})
        assert rows == []
        assert anomalies == []
        assert any("chèque ou espèces" in w for w in warnings)

    def test_mode_du_salarie_sert_de_repli(self):
        source = [_source(advance=_avance(payment_method=None))]
        rows, _, _, warnings = _run(
            source, {"emp-1": _employe(payment_method="cheque")}
        )
        assert rows == []
        assert any("chèque ou espèces" in w for w in warnings)

    def test_salarie_sorti_declenche_une_alerte_sans_bloquer(self):
        exits = {"emp-1": {"last_working_day": "2026-06-30", "status": "validated"}}
        rows, _, _, warnings = _run(
            [_source()], {"emp-1": _employe()}, exits=exits,
            execution_date="2026-07-05",
        )
        assert len(rows) == 1
        assert rows[0]["Statut_controle"] == "Alerte"
        assert any("salarié sorti" in w for w in warnings)

    def test_libelle_impose_remplace_la_nature(self):
        rows, _, _, _ = _run(
            [_source()], {"emp-1": _employe()}, payment_label="Acompte exceptionnel"
        )
        assert rows[0]["Libelle"] == "Acompte exceptionnel"


class TestExclusions:
    def test_exclusion_a_l_acompte_pres(self):
        """Un salarié peut porter deux acomptes : on doit pouvoir n'en exclure qu'un."""
        source = [
            _source(advance_id="adv-1", montant=100.0),
            _source(advance_id="adv-2", montant=200.0),
        ]
        rows, totals, _, _ = _run(
            source,
            {"emp-1": _employe()},
            filters={"excluded_advance_ids": ["adv-1"]},
        )
        assert len(rows) == 1
        assert rows[0]["Montant"] == 200.0
        assert totals["total_amount"] == 200.0

    def test_exclusion_par_salarie_retire_tous_ses_acomptes(self):
        source = [
            _source(advance_id="adv-1", montant=100.0),
            _source(advance_id="adv-2", montant=200.0),
        ]
        rows, _, _, _ = _run(
            source, {"emp-1": _employe()}, excluded_employee_ids=["emp-1"]
        )
        assert rows == []

    def test_mode_inconnu_est_refuse(self):
        with pytest.raises(ValueError, match="Mode 'bidon' inconnu"):
            _run([_source()], {"emp-1": _employe()}, filters={"mode": "bidon"})


class TestModeVerses:
    def _apercu(self, source, **filtres):
        with patch.object(module, "_build_source_verses", return_value=source), \
             patch.object(module, "_load_employees", return_value={"emp-1": _employe()}), \
             patch.object(module, "_load_exits", return_value={}), \
             patch.object(module, "_detect_paid_without_payment", return_value=[]):
            return module.preview_virement_acomptes(
                "co-1", "2026-07", filters={"mode": "verses", **filtres}
            )

    def test_avertit_du_risque_de_double_paiement(self):
        """Le fichier bancaire de ce mode reste un ordre valide : il faut le dire."""
        apercu = self._apercu([_source(payment_id="pay-1")])
        assert any("second virement" in w for w in apercu["warnings"])

    def test_pas_d_avertissement_de_double_paiement_si_aucune_ligne(self):
        apercu = self._apercu([])
        assert not any("second virement" in w for w in apercu["warnings"])

    def test_salarie_sorti_message_adapte_au_mode(self):
        exits = {"emp-1": {"last_working_day": "2026-06-30"}}
        with patch.object(module, "_build_source_verses", return_value=[_source()]), \
             patch.object(module, "_load_employees", return_value={"emp-1": _employe()}), \
             patch.object(module, "_load_exits", return_value=exits):
            _, _, _, warnings = module.get_virement_acomptes_data(
                "co-1", "2026-07", execution_date="2026-07-05",
                filters={"mode": "verses"},
            )
        assert any("salarié sorti mais acompte versé" in w for w in warnings)

    def test_lit_les_versements_enregistres(self):
        paiements = [
            {"id": "pay-1", "advance_id": "adv-1", "payment_amount": 150.0,
             "payment_date": "2026-07-12"}
        ]
        avances = {"adv-1": _avance(status="paid")}
        with patch.object(module, "_fetch_payments", return_value=(paiements, avances)):
            source = module._build_source_verses("co-1", "2026-07", None, None)
        assert len(source) == 1
        assert source[0]["montant"] == 150.0
        assert source[0]["payment_id"] == "pay-1"
        assert source[0]["date"] == "2026-07-12"


class TestFichierSepa:
    def _sepa(self, rows, **kwargs):
        with patch.object(module, "get_virement_acomptes_data",
                          return_value=(rows, {}, [], [])):
            return module.generate_virement_acomptes_sepa("co-1", "2026-07", **kwargs)

    def _rows(self):
        return [
            {"Nom": "Dupont", "Prénom": "Jean", "IBAN": IBAN_VALIDE, "BIC": "BNPAFRPP",
             "Montant": 300.0, "Libelle": "Acompte sur salaire Juillet 2026",
             "Statut_controle": "OK"},
            {"Nom": "Martin", "Prénom": "Claire", "IBAN": IBAN_VALIDE_2, "BIC": "SOGEFRPP",
             "Montant": 150.5, "Libelle": "Acompte sur prime Juillet 2026",
             "Statut_controle": "OK"},
        ]

    def test_totaux_et_nombre_de_transactions(self):
        root = ET.fromstring(self._sepa(self._rows()))
        grp = root.find(f".//{NS}GrpHdr")
        assert grp.find(f"{NS}NbOfTxs").text == "2"
        assert grp.find(f"{NS}CtrlSum").text == "450.50"

    def test_identifiants_distincts_de_la_campagne_salaires(self):
        root = ET.fromstring(self._sepa(self._rows()))
        assert root.find(f".//{NS}GrpHdr/{NS}MsgId").text.startswith("EYWAI-ACO-")
        assert root.find(f".//{NS}PmtInf/{NS}PmtInfId").text == "PMT-ACO-2026-07"
        ids = [e.text for e in root.iter(f"{NS}EndToEndId")]
        assert ids == ["ACO-2026-07-0001", "ACO-2026-07-0002"]

    def test_libelle_par_ligne_sur_le_releve(self):
        root = ET.fromstring(self._sepa(self._rows()))
        libelles = [e.text for e in root.iter(f"{NS}Ustrd")]
        assert libelles == [
            "Acompte sur salaire Juillet 2026",
            "Acompte sur prime Juillet 2026",
        ]

    def test_ligne_bloquante_ecartee_de_la_remise(self):
        rows = self._rows()
        rows[1]["Statut_controle"] = "Bloquant"
        root = ET.fromstring(self._sepa(rows))
        assert root.find(f".//{NS}GrpHdr/{NS}NbOfTxs").text == "1"
        assert root.find(f".//{NS}GrpHdr/{NS}CtrlSum").text == "300.00"


class TestNonRegressionSepaSalaires:
    """Le refactor de build_pain001 ne doit rien changer à la remise des salaires."""

    def test_prefixes_salaires_inchanges(self):
        rows = [
            {"Nom": "Dupont", "Prénom": "Jean", "IBAN": IBAN_VALIDE, "BIC": "BNPAFRPP",
             "Montant": 1800.0, "Statut_controle": "OK"}
        ]
        with patch.object(export_sepa, "get_paiement_salaires_data",
                          return_value=(rows, {}, [], [])):
            xml = export_sepa.generate_sepa_pain001("co-1", "2026-07")
        root = ET.fromstring(xml)
        assert root.find(f".//{NS}GrpHdr/{NS}MsgId").text.startswith("EYWAI-2026-07-")
        assert root.find(f".//{NS}PmtInf/{NS}PmtInfId").text == "PMT-2026-07"
        assert root.find(f".//{NS}EndToEndId").text == "SAL-2026-07-0001"
        assert root.find(f".//{NS}Ustrd").text == "Salaires Juillet 2026"


class TestFichiersPlats:
    def test_recap_ne_fuit_pas_les_identifiants_internes(self):
        rows = [
            {"Matricule": "emp-1", "Nom": "Dupont", "Prénom": "Jean",
             "Nature": "Acompte sur salaire", "IBAN": IBAN_VALIDE, "BIC": "BNPAFRPP",
             "Montant": 300.0, "Devise": "EUR", "Date": "2026-07-05",
             "Libelle": "Acompte sur salaire Juillet 2026", "Statut_controle": "OK",
             "advance_id": "adv-1", "payment_id": "", "employee_id": "emp-1"}
        ]
        with patch.object(module, "get_virement_acomptes_data",
                          return_value=(rows, {}, [], [])):
            contenu = module.generate_virement_acomptes_export("co-1", "2026-07")
        texte = contenu.decode("utf-8-sig")
        assert "adv-1" not in texte
        assert "Acompte sur salaire" in texte

    def test_fichier_bancaire_csv_filtre_les_lignes_bloquantes(self):
        rows = [
            {"Nom": "Dupont", "Prénom": "Jean", "IBAN": IBAN_VALIDE, "BIC": "BNPAFRPP",
             "Montant": 300.0, "Devise": "EUR", "Libelle": "Acompte",
             "Statut_controle": "OK"},
            {"Nom": "Martin", "Prénom": "Claire", "IBAN": "INVALIDE", "BIC": "",
             "Montant": 150.0, "Devise": "EUR", "Libelle": "Acompte",
             "Statut_controle": "OK"},
        ]
        with patch.object(module, "get_virement_acomptes_data",
                          return_value=(rows, {}, [], [])):
            contenu = module.generate_virement_acomptes_bank_file("co-1", "2026-07")
        texte = contenu.decode("utf-8-sig")
        assert "Dupont" in texte
        assert "Martin" not in texte
