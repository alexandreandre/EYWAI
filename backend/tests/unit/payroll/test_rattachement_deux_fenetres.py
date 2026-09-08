"""Un événement va sur le bulletin du mois ou sur celui des variables."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.payroll.engine.calcul_brut import (
    TYPES_RATTACHES_AUX_VARIABLES,
    evenements_de_la_periode,
)

pytestmark = pytest.mark.unit

MOIS = (date(2026, 7, 1), date(2026, 7, 31))
VARIABLES = (date(2026, 6, 22), date(2026, 7, 26))


def _ev(jour: str, type_ev: str, heures: float = 7.0) -> dict:
    return {"date_complete": jour, "type": type_ev, "heures": heures}


def test_les_heures_sup_suivent_la_fenetre_des_variables():
    """Une HS du 24/06 est hors du mois de juillet mais dans la fenêtre."""
    evenements = [_ev("2026-06-24", "travail_hs25", 2.0)]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == evenements


def test_un_conge_du_30_juillet_reste_sur_juillet():
    """Hors fenêtre (qui s'arrête au 26) mais dans le mois : il compte."""
    evenements = [_ev("2026-07-30", "conges_payes")]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == evenements


def test_un_conge_du_24_juin_ne_compte_pas_en_juillet():
    """Dans la fenêtre mais dans le mois de juin : il a été payé en juin."""
    evenements = [_ev("2026-06-24", "conges_payes")]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == []


def test_une_heure_sup_du_30_juillet_bascule_sur_aout():
    """Hors fenêtre : elle sera comptée sur la fenêtre du mois suivant."""
    evenements = [_ev("2026-07-30", "travail_hs25", 3.0)]
    assert evenements_de_la_periode(evenements, MOIS, VARIABLES) == []


def test_sans_fenetre_variables_le_comportement_est_inchange():
    """Repli : une seule fenêtre, celle passée en premier argument."""
    evenements = [_ev("2026-07-30", "travail_hs25"), _ev("2026-06-24", "conges_payes")]
    assert evenements_de_la_periode(evenements, MOIS, None) == [evenements[0]]


def test_une_regularisation_anterieure_passe_toujours():
    evenement = _ev("2026-05-12", "absence_non_remuneree")
    evenement["is_regularisation_anterieure"] = True
    assert evenements_de_la_periode([evenement], MOIS, VARIABLES) == [evenement]


def test_le_catalogue_des_types_variables():
    assert TYPES_RATTACHES_AUX_VARIABLES == frozenset({"travail_hs25", "travail_hs50"})


def _ancien_filtre(
    calendrier: list[dict], debut: date, fin: date
) -> list[dict]:
    """Le filtrage d'avant la fenêtre des variables, recopié tel quel.

    Sert de témoin : tant que les deux fenêtres coïncident — le cas des six
    sociétés réglées au mois civil, et de toute société avant qu'une surcharge
    n'existe — le nouveau code doit rendre exactement la même chose.
    """
    retenus = []
    for evenement in calendrier:
        try:
            jour = date.fromisoformat(evenement["date_complete"])
        except (KeyError, TypeError, ValueError):
            continue
        if not evenement.get("is_regularisation_anterieure") and not (
            debut <= jour <= fin
        ):
            continue
        retenus.append(evenement)
    return retenus


def _calendrier_varie() -> list[dict]:
    """Un mois de tous les types d'événements, débordant des deux côtés."""
    types = [
        "travail_base",
        "travail_hs25",
        "travail_hs50",
        "conges_payes",
        "arret_maladie",
        "ferie",
        "absence_non_remuneree",
    ]
    calendrier = []
    for decalage in range(-10, 45):
        jour = date(2026, 7, 1) + timedelta(days=decalage)
        calendrier.append(_ev(jour.isoformat(), types[decalage % len(types)]))
    regul = _ev("2026-04-03", "absence_non_remuneree")
    regul["is_regularisation_anterieure"] = True
    calendrier.append(regul)
    calendrier.append({"type": "travail_base", "heures": 7.0})  # sans date
    return calendrier


def test_fenetres_confondues_le_filtrage_est_lancien():
    """Société au mois civil : rien ne doit bouger par rapport à avant."""
    calendrier = _calendrier_varie()
    debut, fin = date(2026, 7, 1), date(2026, 7, 31)
    assert evenements_de_la_periode(
        calendrier, (debut, fin), (debut, fin)
    ) == _ancien_filtre(calendrier, debut, fin)


def test_fenetre_absente_le_filtrage_est_lancien():
    """Appel direct du moteur, sans fenêtre transmise : idem."""
    calendrier = _calendrier_varie()
    debut, fin = date(2026, 6, 22), date(2026, 7, 26)
    assert evenements_de_la_periode(
        calendrier, (debut, fin), None
    ) == _ancien_filtre(calendrier, debut, fin)


def test_seules_les_heures_sup_bougent_quand_les_fenetres_different():
    """Colorplast : l'écart entre l'ancien et le nouveau ne porte que sur des HS."""
    calendrier = _calendrier_varie()
    mois = (date(2026, 7, 1), date(2026, 7, 31))
    variables = (date(2026, 6, 22), date(2026, 7, 26))

    avant = _ancien_filtre(calendrier, *variables)
    apres = evenements_de_la_periode(calendrier, mois, variables)

    cles = lambda lot: {(e["date_complete"], e["type"]) for e in lot if "date_complete" in e}
    ecart = cles(avant) ^ cles(apres)
    assert ecart, "les deux fenêtres diffèrent, un écart est attendu"

    # Tout événement qui change de camp doit le faire pour la seule raison
    # attendue : les heures sup parce qu'elles suivent désormais la fenêtre,
    # les autres parce qu'ils suivent désormais le mois.
    for jour, type_ev in ecart:
        d = date.fromisoformat(jour)
        dans_le_mois = mois[0] <= d <= mois[1]
        dans_la_fenetre = variables[0] <= d <= variables[1]
        assert dans_le_mois != dans_la_fenetre, (
            f"{jour} ({type_ev}) est dans les deux fenêtres ou dans aucune : "
            "il n'avait aucune raison de changer de camp"
        )
        if type_ev in TYPES_RATTACHES_AUX_VARIABLES:
            # Retenu après le changement si et seulement s'il est dans la fenêtre.
            assert ((jour, type_ev) in cles(apres)) is dans_la_fenetre
        else:
            assert ((jour, type_ev) in cles(apres)) is dans_le_mois
