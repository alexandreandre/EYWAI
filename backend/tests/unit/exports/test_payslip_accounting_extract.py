"""Tests extraction comptable depuis payslip_data."""

import pytest

from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)

pytestmark = pytest.mark.unit


class TestExtractPasAmount:
    def test_bulletin_format_nested(self):
        assert (
            extract_pas_amount(
                {"impot_prelevement_a_la_source": {"montant": 123.45}}
            )
            == 123.45
        )

    def test_legacy_scalar(self):
        assert extract_pas_amount({"impot_preleve_a_la_source": 50.0}) == 50.0


class TestExtractCotisationsFromPayslip:
    def test_bulletin_blocs_format(self):
        payslip_data = {
            "structure_cotisations": {
                "total_salarial": 600.0,
                "total_patronal": 1200.0,
                "bloc_principales": [
                    {
                        "libelle": "Sécurité sociale",
                        "montant_salarial": 400.0,
                        "montant_patronal": 800.0,
                    },
                    {
                        "libelle": "Retraite",
                        "montant_salarial": 200.0,
                        "montant_patronal": 400.0,
                    },
                ],
            }
        }
        cot_sal, cot_pat, detail, meta = extract_cotisations_from_payslip(payslip_data)
        assert cot_sal == 600.0
        assert cot_pat == 1200.0
        assert len(detail) == 2
        assert meta["format"] == "bulletin_blocs"

    def test_legacy_cotisations_list(self):
        payslip_data = {
            "structure_cotisations": {
                "cotisations": [
                    {"libelle": "URSSAF", "montant_salarial": 100.0, "montant_patronal": 200.0},
                ]
            }
        }
        cot_sal, cot_pat, detail, meta = extract_cotisations_from_payslip(payslip_data)
        assert cot_sal == 100.0
        assert cot_pat == 200.0
        assert len(detail) == 1
        assert meta["format"] == "legacy_cotisations_list"


class TestElementsHorsBrut:
    """Ces montants s'ajoutent au net sans passer par le brut. Sans contrepartie
    au débit, l'OD est déséquilibrée d'exactement leur total."""

    def test_prime_non_soumise_rattachee_a_sa_famille(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "primes_non_soumises": [
                {
                    "libelle": "Indemnite de transport",
                    "montant": 250.0,
                    "prime_id": "indemnite_de_transport",
                }
            ]
        }
        elements = extract_elements_hors_brut(payslip)
        assert elements == [
            {
                "famille": "indemnite_transport",
                "libelle": "Indemnite de transport",
                "montant": 250.0,
            }
        ]

    def test_retenue_negative_conservee(self):
        """Une « prime » non soumise peut être une retenue : avance de
        participation déjà versée, cantine, remboursement de prêt."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "primes_non_soumises": [
                {
                    "libelle": "Avance participation 2025 (déjà versée)",
                    "montant": -900.0,
                    "prime_id": "avance_participation_2025_(déjà_versée)",
                }
            ]
        }
        elements = extract_elements_hors_brut(payslip)
        assert elements[0]["famille"] == "avance_participation"
        assert elements[0]["montant"] == -900.0

    def test_participation_versee_en_numeraire(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "participations": [
                {
                    "brut": 3991.15,
                    "acompte": 0.0,
                    "libelle": "Participation 2025 — numéraire",
                    "part_pee": 0.0,
                    "csg_total": 387.14,
                }
            ]
        }
        elements = extract_elements_hors_brut(payslip)
        assert len(elements) == 1
        assert elements[0]["famille"] == "participation"
        assert elements[0]["montant"] == 3991.15

    def test_participation_placee_sur_un_pee_donne_deux_lignes(self):
        """Cas réel : 10 bulletins de mai 2026. La part placée ne va pas au net,
        elle doit sortir du brut de participation."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "participations": [
                {
                    "brut": 5331.56,
                    "acompte": 0.0,
                    "libelle": "Participation 2025 — numéraire",
                    "part_pee": 5331.56,
                    "csg_total": 517.16,
                }
            ]
        }
        elements = extract_elements_hors_brut(payslip)
        assert len(elements) == 2
        assert elements[0]["famille"] == "participation"
        assert elements[0]["montant"] == 5331.56
        assert elements[1]["famille"] == "participation_pee"
        assert elements[1]["montant"] == -5331.56

    def test_montant_zero_ignore(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "primes_non_soumises": [
                {"libelle": "Prime vide", "montant": 0.0, "prime_id": "prime_vide"}
            ]
        }
        assert extract_elements_hors_brut(payslip) == []

    def test_libelle_inconnu_marque_comme_tel(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "primes_non_soumises": [
                {"libelle": "Prime exceptionnelle", "montant": 100.0}
            ]
        }
        assert extract_elements_hors_brut(payslip)[0]["famille"] == "INCONNUE"

    def test_bulletin_sans_element_hors_brut(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        assert extract_elements_hors_brut({"salaire_brut": 3000.0}) == []
        assert extract_elements_hors_brut({"participations": []}) == []
