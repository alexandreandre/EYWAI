"""Calcul du droit JTC — note de paramétrage Elsa André du 28/07/2026 (MBC)."""

from datetime import date

from app.modules.absences.domain.jtc import (
    JtcSettings,
    calculate_acquired_jtc,
)


ACTIVE = JtcSettings(enabled=True)


def test_annee_complete_sans_absence_donne_le_droit_plein():
    """Une année complète de travail effectif ouvre les 3 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
        )
        == 3
    )


def test_societe_non_activee_ne_donne_aucun_jtc():
    """Le JTC est propre à MBC : sans activation, aucun droit."""
    assert (
        calculate_acquired_jtc(
            settings=JtcSettings(),
            reference_year=2025,
            hire_date=date(2015, 3, 1),
        )
        == 0
    )


def test_nouvel_entrant_sans_presence_en_n1_na_aucun_jtc():
    """Entré en juin 2026 : 0 JTC en 2026, son premier droit sera calculé en janvier 2027."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2026, 6, 1),
        )
        == 0
    )


def test_entree_en_cours_dannee_proratise_sur_les_jours_de_presence():
    """Entré le 01/07/2025 : 184 jours sur 365 → 3 × 0,504 = 1,51 → 1 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2025, 7, 1),
        )
        == 1
    )


def test_sortie_en_cours_dannee_proratise_aussi():
    """Parti le 31/03/2025 : 90 jours sur 365 → 3 × 0,247 = 0,74 → 0 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            exit_date=date(2025, 3, 31),
        )
        == 0
    )


def test_absences_sous_le_seuil_nont_aucun_impact():
    """30 jours d'absence : sous le seuil, le droit reste plein."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=30,
        )
        == 3
    )


def test_absences_au_dessus_du_seuil_proratisent_la_totalite():
    """31 jours d'absence : seuil franchi → 3 × (365 − 31)/365 = 2,74 → 2 JTC.

    Lecture littérale de la note : les 30 jours sont un seuil de déclenchement,
    pas une franchise. En attente de confirmation d'Elsa.
    """
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=31,
        )
        == 2
    )


def test_absence_de_toute_lannee_ne_donne_aucun_jtc():
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=365,
        )
        == 0
    )


def test_entree_et_absences_se_cumulent():
    """Entré le 01/07/2025 (184 j) puis 60 j d'absence → 3 × 124/365 = 1,02 → 1 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2025, 7, 1),
            absence_days=60,
        )
        == 1
    )


def test_annee_bissextile_utilise_366_jours():
    """2024 compte 366 jours : entré le 01/07/2024 → 184 j sur 366 → 1 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2024,
            hire_date=date(2024, 7, 1),
        )
        == 1
    )


def test_le_droit_ne_depasse_jamais_le_maximum_parametre():
    """Même avec des absences négatives ou une présence aberrante, le droit est borné."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=-10,
        )
        == 3
    )


def test_droit_annuel_parametrable():
    """Le maximum n'est pas une constante figée : une autre société pourrait en avoir 5."""
    assert (
        calculate_acquired_jtc(
            settings=JtcSettings(enabled=True, annual_days=5),
            reference_year=2025,
            hire_date=date(2015, 3, 1),
        )
        == 5
    )


def test_salarie_sans_date_dembauche_na_aucun_jtc():
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=None,
        )
        == 0
    )
