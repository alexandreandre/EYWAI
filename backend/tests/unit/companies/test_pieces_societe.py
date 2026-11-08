"""La zone « Pièces de la société » : ce qui est attendu, et où c'est rangé."""

from __future__ import annotations

import pytest

from app.modules.companies.domain.pieces_societe import (
    TYPES_DE_PIECES,
    chemin_de_la_piece,
    chemin_de_la_societe,
    etat_des_pieces,
    nom_affiche,
    verifier_depot,
)

SOCIETE = "11111111-2222-3333-4444-555555555555"


def _ligne(etat, type_piece):
    return next(p for p in etat["pieces"] if p["type"] == type_piece)


class TestEtat:
    def test_sans_convention_l_accord_de_temps_de_travail_est_attendu(self):
        etat = etat_des_pieces({}, a_une_convention=False, statut_jei=False)
        assert _ligne(etat, "accord_temps_travail")["attendue"] is True
        assert _ligne(etat, "adhesion_branche")["attendue"] is False

    def test_avec_convention_l_adhesion_est_attendue(self):
        etat = etat_des_pieces({}, a_une_convention=True, statut_jei=False)
        assert _ligne(etat, "adhesion_branche")["attendue"] is True
        assert _ligne(etat, "accord_temps_travail")["attendue"] is False

    def test_le_justificatif_jei_n_est_attendu_que_si_le_statut_est_applique(self):
        assert (
            _ligne(etat_des_pieces({}, a_une_convention=True, statut_jei=True), "justificatif_jei")[
                "attendue"
            ]
            is True
        )
        assert (
            _ligne(
                etat_des_pieces({}, a_une_convention=True, statut_jei=False), "justificatif_jei"
            )["attendue"]
            is False
        )

    def test_compte_seulement_les_attendues_sans_fichier(self):
        fichiers = {"kbis": [{"chemin": "x", "nom": "kbis.pdf", "depose_le": None}]}
        etat = etat_des_pieces(fichiers, a_une_convention=True, statut_jei=False)
        # attendues : kbis (déposé), mutuelle, prévoyance, adhésion
        assert etat["manquantes"] == 3

    def test_autre_n_est_jamais_attendue(self):
        etat = etat_des_pieces({}, a_une_convention=False, statut_jei=True)
        assert _ligne(etat, "autre")["attendue"] is False

    def test_les_attendues_viennent_d_abord(self):
        etat = etat_des_pieces({}, a_une_convention=True, statut_jei=False)
        attendues = [p["attendue"] for p in etat["pieces"]]
        assert attendues == sorted(attendues, reverse=True)


class TestRangement:
    def test_le_chemin_reste_dans_la_societe(self):
        chemin = chemin_de_la_piece(SOCIETE, "kbis", "Kbis été 2026.PDF", "abc")
        assert chemin.startswith(f"pieces-societe/{SOCIETE}/kbis/abc_")
        assert chemin.endswith(".pdf")
        assert " " not in chemin

    def test_le_nom_de_fichier_ne_peut_pas_remonter(self):
        chemin = chemin_de_la_piece(SOCIETE, "kbis", "../../autre/x.pdf", "abc")
        assert ".." not in chemin
        assert chemin.startswith(f"pieces-societe/{SOCIETE}/kbis/")

    def test_nom_affiche_sans_le_jeton(self):
        assert nom_affiche("abc123_kbis.pdf") == "kbis.pdf"

    def test_chemin_d_une_autre_societe_refuse(self):
        with pytest.raises(ValueError):
            chemin_de_la_societe(SOCIETE, "pieces-societe/autre-societe/kbis/x.pdf")

    def test_remontee_refusee(self):
        with pytest.raises(ValueError):
            chemin_de_la_societe(SOCIETE, f"pieces-societe/{SOCIETE}/../autre/x.pdf")

    def test_chemin_de_la_societe_accepte(self):
        chemin = f"pieces-societe/{SOCIETE}/kbis/abc_x.pdf"
        assert chemin_de_la_societe(SOCIETE, chemin) == chemin


class TestDepot:
    def test_type_inconnu_refuse(self):
        with pytest.raises(ValueError, match="Type de pièce"):
            verifier_depot("inconnu", b"x", "application/pdf")

    def test_fichier_vide_refuse(self):
        with pytest.raises(ValueError, match="vide"):
            verifier_depot("kbis", b"", "application/pdf")

    def test_format_refuse(self):
        with pytest.raises(ValueError, match="PDF"):
            verifier_depot("kbis", b"x", "application/zip")

    def test_trop_gros_refuse(self):
        with pytest.raises(ValueError, match="Mo"):
            verifier_depot("kbis", b"x" * (15 * 1024 * 1024 + 1), "application/pdf")

    def test_pdf_accepte(self):
        verifier_depot("kbis", b"x", "application/pdf")

    def test_chaque_type_a_un_libelle_et_une_raison(self):
        for piece in TYPES_DE_PIECES.values():
            assert piece["libelle"] and piece["pourquoi"]
