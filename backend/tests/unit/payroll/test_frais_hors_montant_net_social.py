"""Un remboursement de frais professionnels n'entre pas dans le montant net social. [D2]

Relevé à l'écran (vidéo G, 11/10/2026) : deux notes de frais validées (restaurant
42 €, indemnités kilométriques 60 €) faisaient passer le « MONTANT NET SOCIAL »
de 2 265,76 € à 2 367,76 €. Le montant part tel quel à la DSN (S21.G00.58,
type 03) et sert au calcul du RSA et de la prime d'activité.

La page Urssaf « Montant net social »
(https://www.urssaf.fr/accueil/employeur/beneficier-exonerations/montant-net-social.html)
répond « Page introuvable » le 11/10/2026. L'Urssaf renvoie, pour le calcul, à la
FAQ du Bulletin officiel de la Sécurité sociale (actualité « Un montant net
social correctement déclaré, c'est essentiel ! », mise à jour le 12/02/2025,
https://www.urssaf.fr/accueil/actualites/declaration-montant-net-social.html).

BOSS, Montant net social, II, A, 1 (version en vigueur au 01/10/2026,
https://boss.gouv.fr/portail/accueil/bulletin-de-paie/montant-net-social.html),
éléments non pris en compte dans le MNS : « Les remboursements de frais
professionnels (au réel ou forfaitaires) dans la limite de chacun de leurs
plafonds d'exonération (ex : nourriture, grand déplacement, trajet
domicile-travail, indemnité forfaitaire de télétravail, […]) ». Et § 27 :
« les remboursements de frais professionnels ne sont pas à inclure dans le
montant net social ». Les primes exonérées, elles, y restent : « Les primes de
toute nature (y compris […] celles exonérées comme la prime de partage de la
valeur) ».

Le remboursement reste versé : il s'ajoute au net à payer.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.frais_professionnels import (
    entree_de_note_de_frais,
    ligne_de_frais_professionnels,
    notes_de_frais_dans_le_mns,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

NOTE_RESTAURANT = {"type": "Restaurant", "amount": 42.0, "date": "2026-10-07"}
NOTE_KILOMETRES = {"type": "Indemnités kilométriques", "amount": 60.0, "date": "2026-10-08"}


def _nets(primes_non_soumises):
    ctx = build_test_contexte(salaire_base=2100.0)
    ctx.year = 2026
    return calculer_net_et_impot(ctx, 2100.0, [], 400.0, primes_non_soumises, 0.0, 0.0, [])


def _frais(note):
    """La note telle que le générateur la passe, puis telle que le moteur la range."""
    return ligne_de_frais_professionnels(entree_de_note_de_frais(note, dans_le_mns=False))


class TestNotesDeFraisDuModule:
    def test_hors_du_montant_net_social(self):
        sans = _nets([])
        avec = _nets([_frais(NOTE_RESTAURANT), _frais(NOTE_KILOMETRES)])

        assert avec["montant_net_social"] == pytest.approx(sans["montant_net_social"])

    def test_toujours_versees_au_net_a_payer(self):
        sans = _nets([])
        avec = _nets([_frais(NOTE_RESTAURANT), _frais(NOTE_KILOMETRES)])

        assert avec["net_a_payer"] == pytest.approx(sans["net_a_payer"] + 102.0)

    def test_une_prime_exoneree_reste_dans_le_montant_net_social(self):
        sans = _nets([])
        ppv = {"libelle": "Prime de partage de la valeur (PPV)", "montant": 500.0, "prime_id": "prime_partage_valeur"}
        avec = _nets([ppv, _frais(NOTE_RESTAURANT)])

        assert avec["montant_net_social"] == pytest.approx(sans["montant_net_social"] + 500.0)


class TestReglageDeLaSociete:
    """Colorplast (spécificité S27, constatée au rapprochement) : Quadra garde ses
    notes de frais dans le montant net social — juillet 2026, 499,15 € ;
    septembre, 627,30 €. Une pratique de la gestionnaire ne se corrige pas sans
    son accord : le réglage `notes_de_frais_dans_mns` la garde."""

    def test_le_reglage_garde_la_note_dans_le_montant_net_social(self):
        entree = entree_de_note_de_frais(NOTE_RESTAURANT, dans_le_mns=True)

        assert ligne_de_frais_professionnels(entree) is None
        sans = _nets([])
        avec = _nets([{"libelle": "x", "montant": entree["montant"], "prime_id": entree["prime_id"]}])
        assert avec["montant_net_social"] == pytest.approx(sans["montant_net_social"] + 42.0)

    def test_le_reglage_se_lit_dans_les_reglages_de_la_societe(self):
        assert notes_de_frais_dans_le_mns({"settings": {"notes_de_frais_dans_mns": True}}) is True
        assert notes_de_frais_dans_le_mns({"settings": {}}) is False
        assert notes_de_frais_dans_le_mns({"settings": None}) is False
        assert notes_de_frais_dans_le_mns(None) is False

    def test_par_defaut_la_note_est_un_frais_professionnel(self):
        entree = entree_de_note_de_frais(NOTE_RESTAURANT, dans_le_mns=False)

        ligne = ligne_de_frais_professionnels(entree)
        assert ligne is not None
        assert ligne["montant"] == 42.0
        assert ligne["prime_id"] == "remb_restaurant_2026-10-07"


def test_une_saisie_ordinaire_n_est_pas_un_frais():
    assert ligne_de_frais_professionnels({"prime_id": "prime_exceptionnelle", "montant": 150.0}) is None
