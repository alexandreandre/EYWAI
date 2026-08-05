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
        # La part placée est brute de CSG : la contribution est prélevée avant le
        # placement, sinon l'OD est déséquilibrée du montant de cette CSG.
        assert elements[1]["famille"] == "participation_pee"
        assert elements[1]["montant"] == pytest.approx(-4814.40)

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


class TestParticipationEnLigneInformative:
    """Certains bulletins ne portent la participation que dans calcul_du_brut,
    en ligne informative (44 bulletins de Mont Blanc en mai 2026)."""

    def test_ligne_informative_reprise_quand_participations_est_vide(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "participations": [],
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "gain": 0.0, "quantite": 151.67},
                {"libelle": "Prime d'ancienneté", "gain": 139.65},
                {
                    "libelle": "Participation 2025 (brut, exonéré de cotisations)",
                    "gain": 1500.75,
                    "is_informative": True,
                },
            ],
        }
        elements = extract_elements_hors_brut(payslip)
        assert len(elements) == 1
        assert elements[0]["famille"] == "participation"
        assert elements[0]["montant"] == 1500.75

    def test_pas_de_double_comptage_quand_les_deux_sources_existent(self):
        """`participations` fait foi : elle porte la part PEE et la CSG."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "participations": [
                {
                    "brut": 1500.75,
                    "part_pee": 0.0,
                    "csg_total": 145.57,
                    "libelle": "Participation 2025",
                }
            ],
            "calcul_du_brut": [
                {
                    "libelle": "Participation 2025 (brut, exonéré de cotisations)",
                    "gain": 1500.75,
                    "is_informative": True,
                },
            ],
        }
        elements = extract_elements_hors_brut(payslip)
        assert len(elements) == 1
        assert elements[0]["montant"] == 1500.75

    def test_lignes_non_informatives_ignorees(self):
        """Le salaire de base et les primes soumises sont déjà dans le brut."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "gain": 2000.0},
                {"libelle": "Prime d'ancienneté", "gain": 139.65},
            ]
        }
        assert extract_elements_hors_brut(payslip) == []
