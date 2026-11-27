"""Panier saisi au mois : l'excédent par panier au-delà du plafond Urssaf est réintégré."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.frais_professionnels import (
    reintegration_panier_plafonne,
)

pytestmark = pytest.mark.unit

FRAIS = {"repas": {"sur_lieu_travail": 7.5, "hors_locaux_sans_restaurant": 10.4, "hors_locaux_avec_restaurant": 21.4}}


def _ligne(**k):
    base = {"prime_id": "indemnite_panier_repas", "libelle": "Panier repas", "montant": 200.0}
    base.update(k)
    return base


def test_vingt_paniers_de_dix_euros_sur_le_lieu_de_travail():
    ligne = _ligne(quantity=20, quantity_kind="count", situation_repas="sur_lieu_travail")
    assert reintegration_panier_plafonne(ligne, {"frais_pro": FRAIS}.get("frais_pro")) == 50.0


def test_sous_le_plafond_rien_a_reintegrer():
    ligne = _ligne(montant=100.0, quantity=20, quantity_kind="count", situation_repas="sur_lieu_travail")
    assert reintegration_panier_plafonne(ligne, FRAIS) == 0.0


def test_sans_situation_declaree_rien_ne_change():
    assert reintegration_panier_plafonne(_ligne(quantity=20, quantity_kind="count"), FRAIS) == 0.0


def test_une_autre_ligne_que_le_panier_n_est_pas_touchee():
    ligne = {"prime_id": "remb_km", "libelle": "Note de frais : km", "montant": 80.0, "situation_repas": "sur_lieu_travail"}
    assert reintegration_panier_plafonne(ligne, FRAIS) == 0.0


# --- Le nombre de paniers et le montant unitaire sur les lignes (L19, 26/11) ---
#
# Constat LEWIS, octobre 2026 : « Panier » 112,50 € sans nombre ni taux, et
# « Réintégration panier Panier » 1,50 € sans nombre. Le nombre était gardé à
# l'entrée puis perdu. Les lignes portent maintenant base = nombre de paniers,
# taux = montant unitaire ; aucun montant ne change.

from app.modules.payroll.engine.frais_professionnels import (  # noqa: E402
    frais_et_reintegration,
    libelle_de_reintegration_panier,
    panier_non_soumis_plafonne,
)

LEWIS = {
    "prime_id": "indemnite_panier_repas",
    "libelle": "Panier",
    "montant": 114.0,
    "quantity": 15.0,
    "quantity_kind": "count",
    "situation_repas": "sur_lieu_travail",
    "soumise_a_cotisations": False,
    "soumise_a_impot": False,
}


def test_prime_non_soumise_nombre_et_taux_sur_les_deux_lignes():
    montant, reint, colonnes = panier_non_soumis_plafonne(
        LEWIS, LEWIS["prime_id"], LEWIS["libelle"], 114.0, FRAIS
    )
    assert montant == 112.5
    assert colonnes == {"quantite": 15.0, "taux": 7.5}
    assert reint == {
        "libelle": "Réintégration panier",
        # Le code de correction reste celui de l'ancien libellé (relecture du 27/11).
        "libelle_du_code": "Réintégration panier Panier",
        "montant": 1.5,
        "prime_id": "reintegration_panier",
        "quantite": 15.0,
        "taux": 0.1,
    }


def test_frais_professionnels_nombre_et_taux_sur_les_deux_lignes():
    ligne, reint = frais_et_reintegration({**LEWIS, "frais_professionnels": True}, FRAIS)
    assert (ligne["montant"], ligne["quantite"], ligne["taux"]) == (112.5, 15.0, 7.5)
    assert (reint["libelle"], reint["montant"], reint["quantite"], reint["taux"]) == (
        "Réintégration panier",
        1.5,
        15.0,
        0.1,
    )


def test_sous_le_plafond_la_ligne_porte_nombre_et_taux_sans_reintegration():
    saisie = {**LEWIS, "montant": 112.5}
    montant, reint, colonnes = panier_non_soumis_plafonne(
        saisie, saisie["prime_id"], "Panier", 112.5, FRAIS
    )
    assert (montant, reint, colonnes) == (112.5, None, {"quantite": 15.0, "taux": 7.5})
    ligne, reint = frais_et_reintegration({**saisie, "frais_professionnels": True}, FRAIS)
    assert reint is None and (ligne["quantite"], ligne["taux"]) == (15.0, 7.5)


def test_valeur_unitaire_saisie_le_nombre_se_deduit():
    saisie = {
        "prime_id": "paniers_jours_non_soumis",
        "libelle": "Paniers jours non soumis",
        "montant": 73.0,
        "quantity": 7.3,
        "quantity_kind": "unit_value",
        "frais_professionnels": True,
    }
    ligne, reint = frais_et_reintegration(saisie, FRAIS)
    assert reint is None
    assert (ligne["montant"], ligne["quantite"], ligne["taux"]) == (73.0, 10.0, 7.3)


def test_sans_nombre_saisi_ni_base_ni_taux_inventes():
    saisie = {k: v for k, v in LEWIS.items() if k not in ("quantity", "quantity_kind")}
    montant, reint, colonnes = panier_non_soumis_plafonne(
        saisie, saisie["prime_id"], "Panier", 114.0, FRAIS
    )
    assert colonnes == {}
    assert reint is not None and "quantite" not in reint and "taux" not in reint
    ligne, reint = frais_et_reintegration({**saisie, "frais_professionnels": True}, FRAIS)
    assert "quantite" not in ligne and "quantite" not in reint


def test_un_frais_qui_n_est_pas_un_panier_reste_sans_colonnes():
    saisie = {
        "prime_id": "deplacement_forfaitaire",
        "libelle": "Indemnité forfaitaire de déplacement",
        "montant": 60.0,
        "quantity": 4.0,
        "quantity_kind": "count",
        "frais_professionnels": True,
    }
    ligne, _ = frais_et_reintegration(saisie, FRAIS)
    assert "quantite" not in ligne and "taux" not in ligne


@pytest.mark.parametrize(
    "libelle, attendu",
    [
        ("Panier", "Réintégration panier"),
        ("Panier chauffeur", "Réintégration panier chauffeur"),
        ("Panier repas (SPAN)", "Réintégration panier repas (SPAN)"),
        ("Indemnité de panier", "Réintégration indemnité de panier"),
        ("Repas", "Réintégration panier (Repas)"),
        ("", "Réintégration panier"),
    ],
)
def test_le_libelle_de_la_reintegration_ne_double_pas_le_mot(libelle, attendu):
    assert libelle_de_reintegration_panier(libelle) == attendu


# --- Relecture du 27/11 : code de ligne inchangé, total conservé au centime ---

from app.modules.payroll.engine.codes_des_lignes import (  # noqa: E402
    MODE_MONTANT,
    code_de_ligne_de_gain,
    mode_de_correction,
)
from app.modules.payroll.engine.lien_saisie import lier_a_la_saisie  # noqa: E402


def _ligne_de_brut(prime):
    """Comme `calcul_brut` (heures et forfait) range une prime soumise."""
    return lier_a_la_saisie(
        {
            "libelle": prime.get("libelle", "Prime"),
            "quantite": prime.get("quantite"),
            "taux": prime.get("taux"),
            "gain": prime.get("montant", 0.0),
            "perte": None,
        },
        prime,
    )


@pytest.mark.parametrize(
    "libelle, code",
    [
        ("Panier", "brut:reintegration:panier-panier"),
        ("Panier chauffeur", "brut:reintegration:panier-panier-chauffeur"),
    ],
)
def test_la_reintegration_garde_son_code_de_correction(libelle, code):
    _, reint, _ = panier_non_soumis_plafonne(LEWIS, LEWIS["prime_id"], libelle, 114.0, FRAIS)
    ligne = _ligne_de_brut(reint)
    assert code_de_ligne_de_gain(ligne) == code
    # Une correction déjà posée par montant s'applique toujours par montant.
    assert mode_de_correction("brut", ligne, code)[0] == MODE_MONTANT
    assert ligne["libelle"] == libelle_de_reintegration_panier(libelle)


def test_la_reintegration_des_frais_garde_son_code_de_correction():
    _, reint = frais_et_reintegration({**LEWIS, "libelle": "Panier repas (SPAN)", "frais_professionnels": True}, FRAIS)
    ligne = _ligne_de_brut(reint)
    assert code_de_ligne_de_gain(ligne) == "brut:reintegration:panier-panier-repas-span"
    assert mode_de_correction("brut", ligne, code_de_ligne_de_gain(ligne))[0] == MODE_MONTANT


@pytest.mark.parametrize(
    "montant, quantite, genre, exonere, reintegre, base",
    [
        (22.60, 3, "count", 22.50, 0.10, 3.0),
        (108.75, 14.5, "count", 108.75, 0.0, 14.5),
        (100.0, 7.6, "unit_value", 97.50, 2.50, 13.0),
    ],
    ids=["22,60-pour-3", "14,5-paniers", "100-a-7,60"],
)
def test_le_total_de_la_saisie_est_conserve_au_centime(montant, quantite, genre, exonere, reintegre, base):
    saisie = {**LEWIS, "montant": montant, "quantity": quantite, "quantity_kind": genre}
    # Chemin « prime » (paniers dans le montant net social).
    exo, reint, colonnes = panier_non_soumis_plafonne(saisie, saisie["prime_id"], "Panier", montant, FRAIS)
    part_reint = reint["montant"] if reint else 0.0
    assert (exo, part_reint) == (exonere, reintegre)
    assert round(exo + part_reint, 2) == montant
    assert colonnes["quantite"] == base
    # Chemin des frais professionnels : le même partage.
    ligne, reint = frais_et_reintegration({**saisie, "frais_professionnels": True}, FRAIS)
    assert (ligne["montant"], reint["montant"] if reint else 0.0) == (exonere, reintegre)
    assert ligne["quantite"] == base
