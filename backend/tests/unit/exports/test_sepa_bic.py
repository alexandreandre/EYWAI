"""BIC absent — construction pain.001 et avertissement d'aperçu.

Le BIC n'est plus obligatoire depuis le règlement (UE) 260/2012 : l'IBAN suffit,
la banque retrouve le BIC elle-même. Deux conséquences testées ici :

  - dans le XML, un BIC absent se déclare par CdtrAgt/FinInstnId/Othr/Id valant
    « NOTPROVIDED », jamais en écrivant « NOTPROVIDED » dans la balise BIC, qui
    n'accepte qu'un vrai BIC ;
  - dans l'aperçu, l'absence de BIC est signalée sans bloquer la génération.
"""

import xml.etree.ElementTree as ET
from unittest.mock import patch

from app.modules.exports.infrastructure import export_sepa
from app.modules.exports.infrastructure import export_virement_acomptes as acomptes

NS = "{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}"

IBAN_VALIDE = "FR7630001007941234567890185"
IBAN_VALIDE_2 = "FR1420041010050500013M02606"


def _ligne(bic: str = "BNPAFRPP", iban: str = IBAN_VALIDE, **extra):
    row = {
        "Nom": "Dupont",
        "Prénom": "Jean",
        "IBAN": iban,
        "BIC": bic,
        "Montant": 1800.0,
        "Statut_controle": "OK",
    }
    row.update(extra)
    return row


class TestAgentDuCreancier:
    def _agent(self, rows):
        xml = export_sepa.build_pain001(rows, period="2026-07", label="Salaires")
        return ET.fromstring(xml).find(f".//{NS}CdtrAgt/{NS}FinInstnId")

    def test_bic_renseigne_reste_dans_la_balise_bic(self):
        fin = self._agent([_ligne(bic="BNPAFRPP")])
        assert fin.find(f"{NS}BIC").text == "BNPAFRPP"
        assert fin.find(f"{NS}Othr") is None

    def test_bic_absent_passe_par_othr_id(self):
        """« NOTPROVIDED » n'est pas un BIC : il ne doit jamais occuper la balise BIC."""
        fin = self._agent([_ligne(bic="")])
        assert fin.find(f"{NS}BIC") is None
        assert fin.find(f"{NS}Othr/{NS}Id").text == "NOTPROVIDED"

    def test_bic_manquant_dans_la_source_traite_comme_absent(self):
        row = _ligne()
        del row["BIC"]
        fin = self._agent([row])
        assert fin.find(f"{NS}Othr/{NS}Id").text == "NOTPROVIDED"

    def test_bic_blanc_traite_comme_absent(self):
        fin = self._agent([_ligne(bic="   ")])
        assert fin.find(f"{NS}Othr/{NS}Id").text == "NOTPROVIDED"

    def test_bic_normalise_en_majuscules_sans_espaces(self):
        fin = self._agent([_ligne(bic=" bnpa frpp ")])
        assert fin.find(f"{NS}BIC").text == "BNPAFRPP"

    def test_une_remise_mixte_traite_chaque_ligne_pour_elle_meme(self):
        xml = export_sepa.build_pain001(
            [_ligne(bic="BNPAFRPP"), _ligne(bic="", iban=IBAN_VALIDE_2)],
            period="2026-07",
            label="Salaires",
        )
        root = ET.fromstring(xml)
        agents = root.findall(f".//{NS}CdtrAgt/{NS}FinInstnId")
        assert agents[0].find(f"{NS}BIC").text == "BNPAFRPP"
        assert agents[1].find(f"{NS}Othr/{NS}Id").text == "NOTPROVIDED"


class TestAgentDuDebiteur:
    """Le schéma SEPA exige DbtrAgt, que l'entreprise ait déclaré son BIC ou non."""

    def _agent(self, **kwargs):
        xml = export_sepa.build_pain001(
            [_ligne()], period="2026-07", label="Salaires", **kwargs
        )
        return ET.fromstring(xml).find(f".//{NS}DbtrAgt/{NS}FinInstnId")

    def test_present_meme_sans_bic_entreprise(self):
        fin = self._agent()
        assert fin is not None
        assert fin.find(f"{NS}Othr/{NS}Id").text == "NOTPROVIDED"

    def test_porte_le_bic_entreprise_quand_il_est_connu(self):
        assert self._agent(debtor_bic="BNPAFRPP").find(f"{NS}BIC").text == "BNPAFRPP"


class TestAvertissementSalaires:
    def _apercu(self, rows):
        with patch.object(
            export_sepa, "get_paiement_salaires_data", return_value=(rows, {}, [], [])
        ):
            return export_sepa.preview_sepa("co-1", "2026-07")

    def _message(self, apercu):
        return next((w for w in apercu["warnings"] if "sans BIC" in w), None)

    def test_signale_les_salaries_sans_bic(self):
        apercu = self._apercu([_ligne(bic=""), _ligne(bic="BNPAFRPP", iban=IBAN_VALIDE_2)])
        assert "1 salarié sans BIC" in self._message(apercu)

    def test_precise_que_le_virement_reste_valide(self):
        apercu = self._apercu([_ligne(bic="")])
        assert "reste valide" in self._message(apercu)

    def test_ne_bloque_pas_la_generation(self):
        apercu = self._apercu([_ligne(bic="")])
        assert apercu["can_generate"] is True

    def test_accorde_le_pluriel(self):
        apercu = self._apercu([_ligne(bic=""), _ligne(bic="", iban=IBAN_VALIDE_2)])
        assert "2 salariés sans BIC" in self._message(apercu)

    def test_silencieux_quand_tous_les_bic_sont_presents(self):
        assert self._message(self._apercu([_ligne(bic="BNPAFRPP")])) is None

    def test_ignore_les_lignes_ecartees_de_la_remise(self):
        """Un salarié non virable n'a pas de BIC à reprocher : il ne part pas."""
        rows = [_ligne(bic="", **{"Statut_controle": "Bloquant"})]
        assert self._message(self._apercu(rows)) is None


class TestAvertissementAcomptes:
    def _apercu(self, rows):
        totals = {"virements_count": len(rows), "employees_count": 1, "total_amount": 0.0}
        with patch.object(
            acomptes, "get_virement_acomptes_data", return_value=(rows, totals, [], [])
        ):
            return acomptes.preview_virement_acomptes("co-1", "2026-07")

    def _message(self, apercu):
        return next((w for w in apercu["warnings"] if "sans BIC" in w), None)

    def test_signale_les_salaries_sans_bic(self):
        assert "1 salarié sans BIC" in self._message(self._apercu([_ligne(bic="")]))

    def test_compte_les_salaries_et_non_les_acomptes(self):
        """Deux acomptes du même salarié ne font pas deux salariés sans BIC."""
        rows = [
            _ligne(bic="", employee_id="emp-1"),
            _ligne(bic="", employee_id="emp-1"),
        ]
        assert "1 salarié sans BIC" in self._message(self._apercu(rows))

    def test_silencieux_quand_tous_les_bic_sont_presents(self):
        assert self._message(self._apercu([_ligne(bic="BNPAFRPP")])) is None
