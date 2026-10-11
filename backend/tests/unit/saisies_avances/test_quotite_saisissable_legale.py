"""Quotité saisissable : le barème légal de l'année, lu en base. [G12]

Le code appliquait un barème « simplifié » à quatre tranches (0/10/20/30 %),
ajoutait 104 € par personne à charge au salaire (ce qui augmentait la retenue)
et laissait au salarié 1/20e de son net. Il retenait trop peu au-dessus de
670 € de net environ, et trop sous le RSA.

Règle (Code du travail L3252-2, L3252-3, R3252-2, R3252-3 ; barème 2026 du
décret du 26/12/2025, service-public A15377) :
- sept tranches annuelles, du vingtième à la totalité : 4 480 / 8 730 /
  13 000 / 17 230 / 21 470 / 25 810 € ;
- chaque seuil est relevé de 1 740 € par an et par personne à charge ;
- le salarié garde toujours le RSA d'une personne seule (646,52 € jusqu'au
  31/03/2026, 651,69 € depuis le 01/04/2026, décret n° 2026-220) ;
- base : rémunération, accessoires et avantages en nature, après cotisations
  et prélèvement à la source, sans les remboursements de frais ; un acompte
  n'est pas déduit (c'est déjà du salaire).

Le barème vit dans `payroll_config` (clé `quotite_saisissable`), comme le SMIC
et le plafond de la Sécurité sociale : une année nouvelle s'y ajoute sans
toucher au code. Les montants de référence sont ceux du simulateur justice.fr
(tranche par tranche, au centime).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.application import service
from app.modules.saisies_avances.domain import rules

pytestmark = pytest.mark.unit

BAREME = {
    "par_annee": {
        "2026": {
            "tranches": [
                {"jusqu_a_annuel": 4480, "fraction": "1/20"},
                {"jusqu_a_annuel": 8730, "fraction": "1/10"},
                {"jusqu_a_annuel": 13000, "fraction": "1/5"},
                {"jusqu_a_annuel": 17230, "fraction": "1/4"},
                {"jusqu_a_annuel": 21470, "fraction": "1/3"},
                {"jusqu_a_annuel": 25810, "fraction": "2/3"},
                {"jusqu_a_annuel": None, "fraction": "1"},
            ],
            "majoration_annuelle_par_personne_a_charge": 1740,
        }
    },
    "solde_insaisissable": [
        {"date_debut": "2025-04-01", "montant_mensuel": 646.52},
        {"date_debut": "2026-04-01", "montant_mensuel": 651.69},
    ],
}


def _quotite(base: str, personnes: int = 0, annee: int = 2026, mois: int = 9) -> Decimal:
    bareme, _ = rules.resoudre_bareme_quotite(BAREME, annee, mois)
    return rules.calculate_seizable_amount(Decimal(base), personnes, bareme)


class TestBaremeLegal:
    @pytest.mark.parametrize(
        "personnes, attendu",
        # justice.fr, barème des saisies sur salaire, ligne « 1 740 € par mois ».
        [(0, "314.78"), (1, "273.70"), (2, "232.61")],
    )
    def test_les_montants_du_simulateur_officiel(self, personnes, attendu):
        assert _quotite("1740", personnes) == Decimal(attendu)

    def test_les_sept_tranches_jusqu_a_la_totalite(self):
        # 18,67 + 35,42 + 71,17 + 88,13 + 117,78 + 241,11 + 849,17
        assert _quotite("3000") == Decimal("1421.45")

    def test_le_salarie_garde_le_rsa(self):
        # Barème : 18,67 + 31,67 = 50,34 ; il doit rester 651,69 € : 38,31.
        assert _quotite("690") == Decimal("38.31")
        assert _quotite("600") == Decimal("0")

    def test_le_rsa_d_avant_avril(self):
        # Mars 2026 : 646,52 € laissés, donc 43,48 € saisissables.
        assert _quotite("690", mois=3) == Decimal("43.48")

    def test_rien_sur_un_net_nul_ou_negatif(self):
        assert _quotite("0") == Decimal("0")
        assert _quotite("-88.30") == Decimal("0")


class TestBaremeDeLAnnee:
    def test_le_bareme_de_l_annee_du_bulletin(self):
        bareme, messages = rules.resoudre_bareme_quotite(BAREME, 2026, 9)
        assert bareme is not None
        assert messages == []

    def test_une_annee_sans_bareme_prend_le_dernier_et_le_dit(self):
        bareme, messages = rules.resoudre_bareme_quotite(BAREME, 2027, 1)
        assert bareme is not None
        assert len(messages) == 1
        assert "2027" in messages[0] and "2026" in messages[0]

    def test_sans_bareme_rien(self):
        bareme, messages = rules.resoudre_bareme_quotite(None, 2026, 9)
        assert bareme is None
        assert messages


class TestBaseSaisissable:
    def test_sans_les_frais_avec_l_avantage_et_sans_deduire_l_acompte(self):
        bulletin = {
            "net_a_payer": 1500.0,
            "synthese_net": {
                "acompte_verse": 200.0,  # acompte déjà versé : salaire, pas déduit
                "avantages_en_nature": 50.0,
                "remboursement_transport": 40.0,
            },
            "primes_non_soumises": [
                {"prime_id": "remb_fournitures_2026-09-12", "montant": 120.0},
                {"prime_id": "prime_partage_valeur", "montant": 100.0},
            ],
        }
        # 1 500 + 200 + 50 − 40 − 120 ; la PPV reste (accessoire du salaire).
        assert rules.base_saisissable(bulletin) == Decimal("1590.00")

    def test_un_frais_ajoute_sur_le_net_n_entre_pas_dans_la_base(self):
        # Panier non soumis versé sur le net : porté en « acompte » négatif.
        bulletin = {"net_a_payer": 1560.0, "synthese_net": {"acompte_verse": -60.0}}
        assert rules.base_saisissable(bulletin) == Decimal("1500.00")


def _enrichir(bulletin: dict, saisies: list, bareme=BAREME):
    ecritures = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=list(saisies)),
        patch.object(service, "get_bareme_quotite_saisissable", return_value=bareme, create=True),
        patch.object(service, "get_advances_to_repay", return_value=[]),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_seizure_deduction", ecritures.saisie),
    ):
        return service.enrich_payslip(bulletin, "e1", 2026, 9, payslip_id="b1"), ecritures


def _saisie_bareme(personnes: int | None = None) -> dict:
    saisie = {
        "id": "s1",
        "type": "saisie_arret",
        "calculation_mode": "barème_legal",
        "amount": None,
        "priority": 4,
        "creditor_name": "Créancier",
    }
    if personnes is not None:
        saisie["dependents_count"] = personnes
    return saisie


class TestAuBulletin:
    def test_la_saisie_au_bareme_prend_la_quotite_legale_de_la_base(self):
        bulletin = {
            "net_a_payer": 1840.0,
            "primes_non_soumises": [{"prime_id": "remb_hotel_2026-09-03", "montant": 100.0}],
        }
        resultat, _ = _enrichir(bulletin, [_saisie_bareme()])

        # Base 1 740 (la note de frais n'est pas saisissable) : 314,78.
        assert resultat["retenues_saisies"]["total_preleve"] == pytest.approx(314.78)
        assert resultat["net_a_payer"] == pytest.approx(1840.0 - 314.78)

    def test_les_personnes_a_charge_de_la_saisie(self):
        resultat, _ = _enrichir({"net_a_payer": 1740.0}, [_saisie_bareme(2)])

        assert resultat["retenues_saisies"]["total_preleve"] == pytest.approx(232.61)

    def test_sans_bareme_rien_n_est_retenu_et_le_bulletin_le_dit(self):
        resultat, ecritures = _enrichir({"net_a_payer": 1740.0}, [_saisie_bareme()], bareme=None)

        assert resultat["retenues_saisies"]["total_preleve"] == 0.0
        assert resultat["net_a_payer"] == pytest.approx(1740.0)
        ecritures.saisie.assert_not_called()
        alertes = resultat.get("alertes_baremes") or []
        assert any("quotité saisissable" in a.get("message", "") for a in alertes)


class TestPersonnesAChargeSurLaSaisie:
    def test_la_creation_enregistre_les_personnes_a_charge(self):
        from app.modules.saisies_avances.schemas import SalarySeizureCreate

        donnees = SalarySeizureCreate(
            employee_id="e1",
            type="saisie_arret",
            creditor_name="Créancier",
            start_date="2026-10-01",
            dependents_count=2,
        )
        with (
            patch.object(service, "employee_company_provider") as societe,
            patch.object(service, "seizure_repository") as depot,
        ):
            societe.get_company_id.return_value = "c1"
            service.create_salary_seizure(donnees, "u1")

        assert depot.create.call_args.args[0]["dependents_count"] == 2

    def test_personnes_a_charge_jamais_negatif(self):
        from pydantic import ValidationError

        from app.modules.saisies_avances.schemas import SalarySeizureCreate

        with pytest.raises(ValidationError):
            SalarySeizureCreate(
                employee_id="e1",
                type="saisie_arret",
                creditor_name="Créancier",
                start_date="2026-10-01",
                dependents_count=-1,
            )
