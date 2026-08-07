"""Règles de campagne d'entretien annuel — politique propre à chaque société.

Les cas couverts reprennent les sept règles du classeur transmis par Elsa le
27/07/2026 (cf. docs/superpowers/specs/2026-08-07-entretiens-reprise-design.md).
"""

from datetime import date

import pytest

from app.modules.annual_reviews.domain.campaign import (
    DEFAULT_CAMPAIGN_SETTINGS,
    InterviewCampaignSettings,
    campaign_urgency,
    deduce_interview_type,
    next_campaign_date,
)

AOUT_2026 = date(2026, 8, 7)


def mois_fixe(month: int, periodicity: int = 1) -> InterviewCampaignSettings:
    return InterviewCampaignSettings(
        enabled=True,
        campaign_mode="mois_fixe",
        campaign_month=month,
        periodicity_years=periodicity,
    )


ANNIVERSAIRE = InterviewCampaignSettings(
    enabled=True,
    campaign_mode="anniversaire_embauche",
    campaign_month=None,
    periodicity_years=1,
)


class TestDefautInerte:
    def test_reglage_par_defaut_desactive(self):
        assert DEFAULT_CAMPAIGN_SETTINGS.enabled is False

    def test_societe_non_reglee_ne_propose_rien(self):
        assert (
            next_campaign_date(
                DEFAULT_CAMPAIGN_SETTINGS,
                hire_date=date(2020, 1, 1),
                last_review_year=None,
                today=AOUT_2026,
            )
            is None
        )


class TestMoisFixe:
    def test_sans_entretien_connu_prochaine_occurrence_du_mois(self):
        """CARTOL, LEWIS, COMITECH, COLORPLAST, MAJI : personne n'a d'historique."""
        assert next_campaign_date(
            mois_fixe(11), hire_date=date(2023, 4, 14), last_review_year=None,
            today=AOUT_2026,
        ) == date(2026, 11, 1)

    def test_mois_deja_passe_bascule_sur_l_annee_suivante(self):
        assert next_campaign_date(
            mois_fixe(3), hire_date=date(2023, 4, 14), last_review_year=None,
            today=AOUT_2026,
        ) == date(2027, 3, 1)

    def test_mois_en_cours_reste_sur_l_annee_en_cours(self):
        assert next_campaign_date(
            mois_fixe(8), hire_date=None, last_review_year=None, today=AOUT_2026,
        ) == date(2026, 8, 1)

    def test_cycle_de_deux_ans_depuis_le_dernier_entretien(self):
        """MBC : dernier entretien 2024 -> octobre 2026, dernier 2025 -> octobre 2027."""
        assert next_campaign_date(
            mois_fixe(10, periodicity=2), hire_date=None, last_review_year=2024,
            today=AOUT_2026,
        ) == date(2026, 10, 1)
        assert next_campaign_date(
            mois_fixe(10, periodicity=2), hire_date=None, last_review_year=2025,
            today=AOUT_2026,
        ) == date(2027, 10, 1)

    def test_echeance_depassee_reste_dans_le_passe(self):
        """Une échéance ratée n'est pas repoussée : c'est ce qui la rend visible."""
        assert next_campaign_date(
            mois_fixe(10, periodicity=2), hire_date=None, last_review_year=2020,
            today=AOUT_2026,
        ) == date(2022, 10, 1)


class TestAnniversaireEmbauche:
    def test_premier_anniversaire(self):
        """Zone 404 : entrée 05/01/2026 -> 05/01/2027."""
        assert next_campaign_date(
            ANNIVERSAIRE, hire_date=date(2026, 1, 5), last_review_year=None,
            today=AOUT_2026,
        ) == date(2027, 1, 5)

    def test_anciennete_longue_prochain_anniversaire_a_venir(self):
        assert next_campaign_date(
            ANNIVERSAIRE, hire_date=date(2015, 4, 27), last_review_year=None,
            today=AOUT_2026,
        ) == date(2027, 4, 27)

    def test_anniversaire_encore_a_venir_cette_annee(self):
        assert next_campaign_date(
            ANNIVERSAIRE, hire_date=date(2015, 12, 3), last_review_year=None,
            today=AOUT_2026,
        ) == date(2026, 12, 3)

    def test_depuis_le_dernier_entretien(self):
        assert next_campaign_date(
            ANNIVERSAIRE, hire_date=date(2015, 4, 27), last_review_year=2025,
            today=AOUT_2026,
        ) == date(2026, 4, 27)

    def test_29_fevrier_retombe_sur_le_28(self):
        assert next_campaign_date(
            ANNIVERSAIRE, hire_date=date(2024, 2, 29), last_review_year=None,
            today=AOUT_2026,
        ) == date(2027, 2, 28)

    def test_sans_date_d_entree_aucune_proposition(self):
        assert (
            next_campaign_date(
                ANNIVERSAIRE, hire_date=None, last_review_year=None, today=AOUT_2026
            )
            is None
        )


class TestUrgence:
    def test_echeance_future_est_due(self):
        assert campaign_urgency(date(2026, 10, 1), AOUT_2026) == "due"

    def test_echeance_passee_est_en_retard(self):
        assert campaign_urgency(date(2026, 7, 1), AOUT_2026) == "overdue"

    def test_jour_meme_est_du(self):
        assert campaign_urgency(AOUT_2026, AOUT_2026) == "due"


class TestTypeDeduit:
    def test_forfait_jour(self):
        assert deduce_interview_type("Cadre au forfait jour") == "annual_forfait_jour"
        assert (
            deduce_interview_type("Non-Cadre", forfait_jour=True)
            == "annual_forfait_jour"
        )

    def test_cadre(self):
        assert deduce_interview_type("Cadre") == "annual_cadres"

    def test_autre(self):
        assert deduce_interview_type("Non-Cadre") == "annual_performance"
        assert deduce_interview_type(None) == "annual_performance"

    def test_forfait_jour_prime_sur_cadre(self):
        """Un cadre au forfait jour relève de l'entretien de suivi, pas de l'annuel cadre."""
        assert deduce_interview_type("Cadre au forfait jour") == "annual_forfait_jour"


class TestChargementDepuisLaBase:
    def test_ligne_absente_donne_le_defaut_inerte(self):
        assert InterviewCampaignSettings.from_row(None) == DEFAULT_CAMPAIGN_SETTINGS

    def test_ligne_lue(self):
        s = InterviewCampaignSettings.from_row(
            {
                "enabled": True,
                "campaign_mode": "mois_fixe",
                "campaign_month": 10,
                "periodicity_years": 2,
            }
        )
        assert s == mois_fixe(10, periodicity=2)

    @pytest.mark.parametrize("mois", [0, 13, None])
    def test_mois_invalide_en_mois_fixe_desactive_la_campagne(self, mois):
        """La base l'interdit ; une donnée héritée ne doit pas produire une date fausse."""
        s = InterviewCampaignSettings(
            enabled=True, campaign_mode="mois_fixe", campaign_month=mois
        )
        assert (
            next_campaign_date(
                s, hire_date=date(2020, 1, 1), last_review_year=None, today=AOUT_2026
            )
            is None
        )
