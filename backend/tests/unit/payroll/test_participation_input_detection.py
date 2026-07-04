"""Détection des saisies mensuelles « participation numéraire » (payslip_generator).

Seule la somme *versée* (montant positif) doit être traitée comme part numéraire
soumise au régime participation (CSG 9,7 % + IR). Les lignes connexes (acompte
déjà versé, remboursement de frais, part PEE) doivent être écartées même si leur
libellé mentionne « participation ».
"""

from __future__ import annotations

from app.modules.payroll.documents.payslip_generator import (
    _is_participation_numeraire_input,
)


def test_participation_numeraire_detectee():
    assert _is_participation_numeraire_input(
        {"name": "Participation 2025 — numéraire", "amount": 3936.59}
    )


def test_detectee_par_campaign_id():
    assert _is_participation_numeraire_input(
        {"name": "Somme exercice 2025", "amount": 500.0, "participation_campaign_id": "abc"}
    )


def test_interessement_detecte():
    assert _is_participation_numeraire_input(
        {"name": "Intéressement 2025 — numéraire", "amount": 120.0}
    )


def test_acompte_negatif_exclu():
    assert not _is_participation_numeraire_input(
        {"name": "Acompte participation 2025 (déjà versé)", "amount": -1000.0}
    )


def test_note_de_frais_exclue():
    assert not _is_participation_numeraire_input(
        {"name": "Remboursement note de frais (participation)", "amount": 569.59}
    )


def test_part_pee_exclue():
    assert not _is_participation_numeraire_input(
        {"name": "Participation 2025 — PEE", "amount": 1000.0}
    )


def test_montant_nul_exclu():
    assert not _is_participation_numeraire_input(
        {"name": "Participation 2025 — numéraire", "amount": 0.0}
    )


def test_prime_classique_non_detectee():
    assert not _is_participation_numeraire_input(
        {"name": "Prime exceptionnelle", "amount": 300.0}
    )
