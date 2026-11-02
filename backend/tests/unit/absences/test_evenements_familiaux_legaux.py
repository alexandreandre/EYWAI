"""Congés pour événements familiaux : jamais moins que la loi.

Code du travail L3142-4 (version mise à jour le 14/06/2026, lue le 03/11/2026
sur code.travail.gouv.fr) : la convention fixe la durée de chaque congé, « qui
ne peut être inférieure à » 4 jours (mariage ou PACS), 1 jour (mariage d'un
enfant), 3 jours (naissance, adoption), 12 jours ou 14 jours (décès d'un
enfant), 3 jours (décès du conjoint, du partenaire, d'un parent, d'un
beau-parent, d'un frère ou d'une sœur), 10 jours (annonce d'un handicap, d'une
pathologie chronique ou d'un cancer chez un enfant). Jours ouvrables.

Défaut trouvé le 03/11 : la table de référence portait PACS 1 j, décès d'un
enfant 5 j, annonce d'un handicap 2 j ; et une société sans convention
configurée (MAJI) n'avait aucun événement proposé.
"""

from app.modules.absences.domain.evenements_familiaux import (
    MINIMA_LEGAUX_JOURS,
    duree_evenement,
)


def test_les_minima_sont_ceux_de_l_article_l3142_4():
    assert MINIMA_LEGAUX_JOURS == {
        "mariage_salarie": 4,
        "pacs_salarie": 4,
        "mariage_enfant": 1,
        "naissance_adoption": 3,
        "deces_enfant": 14,
        "deces_conjoint": 3,
        "deces_pere_mere": 3,
        "deces_frere_soeur": 3,
        "deces_beaux_parents": 3,
        "annonce_handicap_enfant": 10,
    }


def test_sans_convention_la_loi_s_applique():
    assert duree_evenement("pacs_salarie", duree_convention=None, duree_reference=1, avec_convention=False) == 4
    assert duree_evenement("deces_conjoint", duree_convention=None, duree_reference=5, avec_convention=False) == 3


def test_sans_convention_un_evenement_hors_loi_n_est_pas_propose():
    assert duree_evenement("demenagement", duree_convention=None, duree_reference=1, avec_convention=False) is None
    assert duree_evenement("deces_grands_parents", duree_convention=None, duree_reference=1, avec_convention=False) is None


def test_une_convention_ne_descend_pas_sous_la_loi():
    assert duree_evenement("annonce_handicap_enfant", duree_convention=2, duree_reference=2, avec_convention=True) == 10


def test_une_convention_plus_favorable_l_emporte():
    assert duree_evenement("mariage_salarie", duree_convention=5, duree_reference=4, avec_convention=True) == 5


def test_avec_convention_sans_duree_saisie_la_loi_pour_un_evenement_legal():
    assert duree_evenement("deces_enfant", duree_convention=None, duree_reference=5, avec_convention=True) == 14


def test_avec_convention_un_evenement_hors_loi_garde_la_reference():
    # Inchangé pour les usines : la liste montrait déjà ces deux événements.
    assert duree_evenement("deces_grands_parents", duree_convention=None, duree_reference=1, avec_convention=True) == 1
    assert duree_evenement("demenagement", duree_convention=2, duree_reference=1, avec_convention=True) == 2
