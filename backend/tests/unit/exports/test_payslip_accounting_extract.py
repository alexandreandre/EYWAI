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


def _par_famille(elements):
    totaux = {}
    for e in elements:
        totaux[e["famille"]] = round(totaux.get(e["famille"], 0.0) + e["montant"], 2)
    return totaux


class TestRetenuesDuBulletin:
    """Ce que le bulletin retient du net doit en sortir au bon compte, une fois.

    Les avances, prêts et saisies des modules n'étaient lus que dans leurs
    tables, jamais sur le bulletin (audit du 04/10/2026).
    """

    def test_saisie_du_module_lue_sur_le_bulletin(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "retenues_saisies": {
                "total_preleve": 46.49,
                "saisies": [
                    {"type": "saisie_arret", "montant": 46.49, "creditor_name": "Trésor"}
                ],
            }
        }
        elements = extract_elements_hors_brut(payslip)
        assert elements == [
            {
                "famille": "saisie_opposition",
                "libelle": "Saisie sur salaire — Trésor",
                "montant": -46.49,
                "type_saisie": "saisie_arret",
            }
        ]

    def test_avance_du_module_garde_son_compte(self):
        """Le versement de l'avance a été passé sur le compte de l'avance : le
        remboursement doit solder ce même compte."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "remboursements_avances": {
                "total_rembourse": 800.0,
                "avances": [
                    {
                        "montant": 800.0,
                        "type": "acompte_salaire",
                        "type_label": "Acompte sur salaire",
                        "compte": "4251",
                    }
                ],
            }
        }
        elements = extract_elements_hors_brut(payslip)
        assert elements == [
            {
                "famille": "avance_salaire",
                "libelle": "Acompte sur salaire",
                "montant": -800.0,
                "compte": "4251",
            }
        ]

    def test_pret_capital_et_interets_separes(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "remboursements_prets": {
                "total_rembourse": 212.5,
                "total_capital": 200.0,
                "total_interets": 12.5,
                "avantage_nature_interets": 3.1,
            }
        }
        assert _par_famille(extract_elements_hors_brut(payslip)) == {
            "pret_employeur": -200.0,
            "interets_pret_employeur": -12.5,
        }

    def test_retenues_reprises_lues_et_acompte_pas_double(self):
        """Bulletin repris : `retenues_sur_net` détaille ce que l'ancien logiciel
        a retenu ; `acompte_verse` y répète l'acompte."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "synthese_net": {"acompte_verse": 800.0},
            "retenues_sur_net": [
                {"zone": "apres_net", "libelle": "Acompte 08/2026", "montant": 800.0},
                {"zone": "apres_net", "libelle": "Report NAP négatif", "montant": 419.75},
                {"zone": "apres_net", "libelle": "Saisie Trésor", "montant": 70.18},
                {
                    "zone": "apres_net",
                    "libelle": "Saisie Trésor",
                    "montant": 180.0,
                    "sans_effet_sur_le_net": True,
                },
            ],
        }
        assert _par_famille(extract_elements_hors_brut(payslip)) == {
            "acompte_verse": -800.0,
            "regularisation_net": -419.75,
            "saisie_opposition": -70.18,
        }

    def test_indemnite_de_rupture_exoneree(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "indemnites_sortie": {
                "lignes_exonerees": [
                    {"libelle": "Indemnité légale de licenciement", "montant": 1520.33}
                ],
                "total_exonerees": 1520.33,
            }
        }
        assert _par_famille(extract_elements_hors_brut(payslip)) == {
            "indemnite_rupture": 1520.33
        }

    def test_remboursement_transport_du_contrat(self):
        """Prise en charge de l'abonnement (50 %), ajoutée au net par le moteur."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {"synthese_net": {"remboursement_transport": 43.1}}
        assert _par_famille(extract_elements_hors_brut(payslip)) == {
            "indemnite_transport": 43.1
        }

    def test_acompte_deja_verse_sur_la_participation(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
        )

        payslip = {
            "participations": [
                {
                    "libelle": "Participation 2025",
                    "brut": 1000.0,
                    "part_pee": 0.0,
                    "csg_total": 97.0,
                    "acompte": 300.0,
                }
            ]
        }
        assert _par_famille(extract_elements_hors_brut(payslip)) == {
            "participation": 1000.0,
            "avance_participation": -300.0,
        }


class TestAcompteVerseDecompose:
    """`acompte_verse` additionne tout ce que les variables du mois retiennent
    sur le net : acompte, saisie, report d'un net négatif… Chacun a son compte."""

    def test_saisie_saisie_en_variable_va_au_compte_des_saisies(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
            merge_monthly_inputs_hors_brut,
        )

        payslip = {"synthese_net": {"acompte_verse": 33.38}}
        saisies = [{"name": "Saisie Trésor", "amount": -33.38}]
        elements = merge_monthly_inputs_hors_brut(
            extract_elements_hors_brut(payslip), saisies
        )
        assert _par_famille(elements) == {"saisie_opposition": -33.38}

    def test_plusieurs_retenues_decomposees(self):
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
            merge_monthly_inputs_hors_brut,
        )

        payslip = {"synthese_net": {"acompte_verse": 915.11}}
        saisies = [
            {"name": "Acompte", "amount": -800.0},
            {"name": "Report NAP négatif 04/2026", "amount": -115.11},
            {"name": "Indemnité de transport", "amount": 60.0},
        ]
        payslip["primes_non_soumises"] = [
            {"libelle": "Indemnité de transport", "montant": 60.0}
        ]
        elements = merge_monthly_inputs_hors_brut(
            extract_elements_hors_brut(payslip), saisies
        )
        assert _par_famille(elements) == {
            "acompte_verse": -800.0,
            "regularisation_net": -115.11,
            "indemnite_transport": 60.0,
        }

    def test_sans_correspondance_l_acompte_reste_entier(self):
        """Les variables ont changé depuis le calcul : on ne devine pas."""
        from app.modules.exports.infrastructure.payslip_accounting_extract import (
            extract_elements_hors_brut,
            merge_monthly_inputs_hors_brut,
        )

        payslip = {"synthese_net": {"acompte_verse": 500.0}}
        saisies = [{"name": "Saisie Trésor", "amount": -33.38}]
        elements = merge_monthly_inputs_hors_brut(
            extract_elements_hors_brut(payslip), saisies
        )
        assert _par_famille(elements) == {"acompte_verse": -500.0}
