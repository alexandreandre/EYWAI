"""Indemnité trajet domicile-travail — calcul mensuel (domaine pur)."""

from datetime import date

from app.modules.payroll_variables.domain.transport_allowance import (
    est_absent_tout_le_mois,
    jours_ouvres,
    montant_transport_mensuel,
)

JUIN_DEBUT = date(2026, 6, 1)
JUIN_FIN = date(2026, 6, 30)


def test_juin_2026_compte_22_jours_ouvres():
    assert jours_ouvres(JUIN_DEBUT, JUIN_FIN) == 22


def test_fin_avant_debut_donne_zero():
    assert jours_ouvres(JUIN_FIN, JUIN_DEBUT) == 0


def test_mois_complet_verse_le_montant_contractuel():
    montant = montant_transport_mensuel(
        250.0, debut_mois=JUIN_DEBUT, fin_mois=JUIN_FIN
    )
    assert montant == 250.0


def test_absence_totale_ne_verse_rien():
    """Règle d'Elsa : « si absent tous les mois on enlève »."""
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        absent_tout_le_mois=True,
    )
    assert montant == 0.0


def test_entree_en_cours_de_mois_proratise():
    """Entrée le 15/06/2026 : 12 jours ouvrés sur 22."""
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_entree=date(2026, 6, 15),
    )
    assert montant == 136.36


def test_sortie_en_cours_de_mois_proratise():
    """Sortie le 15/06/2026 : 11 jours ouvrés sur 22."""
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_sortie=date(2026, 6, 15),
    )
    assert montant == 125.0


def test_date_effet_posterieure_au_mois_ne_verse_rien():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_effet=date(2026, 7, 1),
    )
    assert montant == 0.0


def test_date_effet_anterieure_verse_le_montant_plein():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_effet=date(2026, 1, 1),
    )
    assert montant == 250.0


def test_date_effet_en_cours_de_mois_proratise():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_effet=date(2026, 6, 15),
    )
    assert montant == 136.36


def test_montant_contractuel_nul_ne_verse_rien():
    assert montant_transport_mensuel(0.0, debut_mois=JUIN_DEBUT, fin_mois=JUIN_FIN) == 0.0


def test_sortie_avant_le_mois_ne_verse_rien():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_sortie=date(2026, 5, 20),
    )
    assert montant == 0.0


def test_absence_couvrant_tous_les_jours_ouvres():
    jours = {date(2026, 6, d) for d in range(1, 31)}
    assert est_absent_tout_le_mois(jours, JUIN_DEBUT, JUIN_FIN)


def test_absence_partielle_nest_pas_totale():
    jours = {date(2026, 6, d) for d in range(1, 16)}
    assert not est_absent_tout_le_mois(jours, JUIN_DEBUT, JUIN_FIN)


def test_absence_ignorant_les_week_ends_reste_totale():
    """Un salarié absent tous les jours ouvrés l'est totalement, même si les
    samedis et dimanches ne sont pas déclarés."""
    jours = {
        date(2026, 6, d)
        for d in range(1, 31)
        if date(2026, 6, d).weekday() < 5
    }
    assert est_absent_tout_le_mois(jours, JUIN_DEBUT, JUIN_FIN)


def test_aucune_absence_declaree_nest_pas_une_absence_totale():
    assert not est_absent_tout_le_mois(set(), JUIN_DEBUT, JUIN_FIN)
