"""Le moteur applique le barème de la plasturgie (conception du 24/10/2026).

Au centime, les cas de Comitech que le texte explique : IJ au montant validé
relevé sur Quadra (41,19 €/jour pour S.G., 41,95 € pour D.S.), salaires de la
fiche. Puis le plancher légal, comparé sur le versé, les alertes, la
subrogation, et la compatibilité : sans barème, rien ne change. Initiales
seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

AVRIL = (date(2026, 4, 1), date(2026, 4, 30))
MAI = (date(2026, 5, 1), date(2026, 5, 31))
JUIN = (date(2026, 6, 1), date(2026, 6, 30))
JUILLET = (date(2026, 7, 1), date(2026, 7, 31))
SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))

#: Comitech : jamais de subrogation, jours ouvrés, IJSS déduites, barème.
BAREME = {
    "bareme_convention": "plasturgie_0292",
    "subrogation_mode": "never",
    "maintain_working_days": True,
    "deduire_ijss_sans_subrogation": True,
}
#: Réglages manuels que le barème remplace : sous le barème, ils ne comptent pas.
MANUELS = {
    "apply_legal_maintenance": False,
    "employer_waiting_days": 3,
    "min_seniority_months": 10,
    "paid_waiting_days_per_year": 3,
    "custom_duration_days": 57,
    "maintain_100_percent": True,
}
ALERTE_LEGAL = "Règle conventionnelle moins favorable que la règle légale — application de la règle légale"


def _contexte(entree="2003-07-15", salaire=1952.60, statut="Non-Cadre"):
    return build_test_contexte(
        statut=statut, salaire_base=salaire, duree_hebdo=39.0, date_entree=entree,
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _sg(entree="2003-07-15"):
    return _contexte(entree)


def _ds():
    return _contexte("2003-09-01", 3368.60, "Cadre")


def _arret(debut, fin, connus, override=None, type_arret="maladie_simple", **extra):
    arret = {
        "arret_type": type_arret,
        "date_debut": debut,
        "date_fin": fin,
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        "arrets_connus": [{"debut": d, "fin": f, "type": type_arret} for d, f in connus],
        **extra,
    }
    if override is not None:
        arret["ijss_brut_override"] = override
    return arret


CHAINE_SG = [("2026-05-04", "2026-05-31"), ("2026-06-01", "2026-06-30"),
             ("2026-07-01", "2026-07-31"), ("2026-08-01", "2026-08-31"),
             ("2026-09-01", "2026-09-30")]


def _mois_sg(mois, periode, override, contexte=None, reglages=BAREME, **extra):
    debut, fin = CHAINE_SG[mois - 5]
    arret = _arret(debut, fin, CHAINE_SG[: mois - 4], override, **extra)
    return calculer_maintien(arret, contexte or _sg(), dict(reglages), *periode)


# --- Comitech, au centime ----------------------------------------------------


def test_s_g_mai_premier_arret_de_l_annee_sans_carence():
    r = _mois_sg(5, MAI, 1029.75)
    m = r["maintien"]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (2059.84, 1029.75, 1030.09)
    assert m["paliers"] == [{
        "taux": 1.0, "du": "2026-05-04", "au": "2026-05-31", "jours": 20,
        "jours_calendaires": 28, "valeur": 2059.84, "garanti": 2059.84, "ijss_deduites": 1029.75,
    }]
    assert m["bareme"] == "plasturgie_0292" and m["regle_retenue"] == "convention"
    assert m["bareme_detail"] == "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus"
    assert r["carence"]["carence_employeur_jours"] == 0
    assert "premier arrêt de l'année, pas de carence" in r["carence"]["motif_carence"]


def test_s_g_juin_mois_entier_le_salaire_du_mois():
    m = _mois_sg(6, JUIN, 1235.70)["maintien"]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (2231.48, 1235.70, 995.78)


def test_d_s_cadre_avril_et_mai():
    arret = _arret("2026-04-27", "2026-07-17", [("2026-04-27", "2026-07-17")])
    avril = calculer_maintien({**arret, "ijss_brut_override": 41.95}, _ds(), dict(BAREME), *AVRIL)
    assert (avril["maintien"]["maintien_cible"], avril["maintien"]["maintien_verse"]) == (710.72, 668.77)
    assert "cadres : pas de carence" in avril["carence"]["motif_carence"]
    mai = calculer_maintien({**arret, "ijss_brut_override": 1300.45}, _ds(), dict(BAREME), *MAI)
    assert (mai["maintien"]["maintien_cible"], mai["maintien"]["maintien_verse"]) == (3849.73, 2549.28)
    assert mai["maintien"]["bareme_detail"] == "Plasturgie (IDCC 0292), cadres, 10 ans et plus"


def test_d_s_prolongation_du_18_au_26_07():
    arret = _arret("2026-07-18", "2026-07-26",
                   [("2026-04-27", "2026-07-17"), ("2026-07-18", "2026-07-26")], 377.55)
    m = calculer_maintien(arret, _ds(), dict(BAREME), *JUILLET)["maintien"]
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (888.40, 377.55, 510.85)


def test_les_reglages_manuels_ne_comptent_pas_sous_le_bareme():
    reference = _mois_sg(5, MAI, 1029.75)
    for extra in (MANUELS, {**MANUELS, "apply_legal_maintenance": True}):
        assert _mois_sg(5, MAI, 1029.75, reglages={**BAREME, **extra}) == reference


# --- Paliers dans le mois ----------------------------------------------------


def test_passage_a_75_pour_cent_dans_le_mois():
    """Non-cadre de 6 ans, juillet : 2 jours à 100 %, puis 75 % dès le 03/07."""
    r = _mois_sg(7, JUILLET, 1276.89, contexte=_sg("2020-01-15"))
    m = r["maintien"]
    assert m["paliers"] == [
        {"taux": 1.0, "du": "2026-07-01", "au": "2026-07-02", "jours": 2, "jours_calendaires": 2,
         "valeur": 194.04, "garanti": 194.04, "ijss_deduites": 82.38},
        {"taux": 0.75, "du": "2026-07-03", "au": "2026-07-31", "jours": 21, "jours_calendaires": 29,
         "valeur": 2037.44, "garanti": 1528.08, "ijss_deduites": 1194.51},
    ]
    assert (m["maintien_cible"], m["maintien_verse"]) == (1722.12, 445.23)
    assert "Plasturgie : passage à 75 % le 03/07/2026." in r["alertes"]


# --- Plancher légal, comparé sur le versé ------------------------------------


def test_le_legal_l_emporte_en_juillet_pour_un_non_cadre_de_22_ans():
    r = _mois_sg(7, JUILLET, 1276.89)
    m = r["maintien"]
    assert m["regle_retenue"] == "legal" and m["conflit_convention"] is True
    assert [(p["taux"], p["du"], p["au"], p["jours"], p["garanti"]) for p in m["paliers"]] == [
        (0.9, "2026-07-01", "2026-07-19", 13, 1135.14),
        (0.6667, "2026-07-20", "2026-07-31", 10, 646.81),
    ]
    assert (m["maintien_cible"], m["maintien_verse"]) == (1781.95, 505.06)
    assert ALERTE_LEGAL in r["alertes"]


def test_en_septembre_le_bareme_l_emporte_sur_le_verse_meme_si_le_garanti_legal_est_plus_haut():
    """Légal : 1 284,79 garantis, 172,66 versés ; barème : 836,81 et 218,96."""
    r = _mois_sg(9, SEPTEMBRE, 1235.70)
    m = r["maintien"]
    assert m["regle_retenue"] == "convention"
    assert (m["maintien_cible"], m["ijss_deduites"], m["maintien_verse"]) == (836.81, 617.85, 218.96)
    assert (
        "Plasturgie : limite de 135 jours atteinte le 15/09/2026, plus de maintien ensuite. "
        "Vérifier la prévoyance."
    ) in r["alertes"]


# --- Subrogation et réglage des IJSS -----------------------------------------


def test_avec_subrogation_le_garanti_moins_les_ijss_des_jours_maintenus():
    reglages = {**BAREME, "subrogation_mode": "when_maintien"}
    r = _mois_sg(6, JUIN, 1235.70, reglages=reglages, subrogation_active=True)
    assert r["subrogation_active"] is True
    m = r["maintien"]
    assert (m["maintien_cible"], m["maintien_verse"]) == (2231.48, 995.78)
    assert "ijss_deduites" not in m
    assert m["paliers"][0]["ijss_deduites"] == 1235.70


def test_sans_subrogation_garanti_en_entier():
    m = _mois_sg(6, JUIN, 1235.70, reglages={**BAREME, "deduire_ijss_sans_subrogation": False})["maintien"]
    assert m["maintien_verse"] == m["maintien_cible"] == 2231.48
    assert "ijss_deduites" not in m and "ijss_deduites" not in m["paliers"][0]


# --- Droit, carence, statut --------------------------------------------------


def test_onze_mois_rien_en_maladie_mais_les_paliers_en_accident_du_travail():
    contexte = _contexte("2025-05-28", 1918.32)
    maladie = calculer_maintien(
        _arret("2026-05-05", "2026-05-13", [("2026-05-05", "2026-05-13")]), contexte, dict(BAREME), *MAI
    )
    motif = "Plasturgie : un an d'ancienneté requis pour une maladie (11 mois au début de l'arrêt)."
    assert maladie["maintien"]["maintien_applicable"] is False
    assert maladie["maintien"]["motif_non_maintien"] == motif
    assert motif in maladie["alertes"]
    at = calculer_maintien(
        _arret("2026-05-05", "2026-05-07", [("2026-05-05", "2026-05-07")], type_arret="accident_travail"),
        contexte, dict(BAREME), *MAI,
    )
    assert at["maintien"]["maintien_applicable"] is True
    assert [(p["taux"], p["jours"]) for p in at["maintien"]["paliers"]] == [(1.0, 3)]


def test_un_deuxieme_arret_a_trois_jours_de_carence():
    connus = [("2026-02-02", "2026-02-06"), ("2026-03-02", "2026-03-13")]
    r = calculer_maintien(_arret("2026-03-02", "2026-03-13", connus), _sg(), dict(BAREME),
                          date(2026, 3, 1), date(2026, 3, 31))
    assert r["carence"]["carence_employeur_jours"] == 3
    assert r["carence"]["motif_carence"] == (
        "Carence SS : 3 jours. Plasturgie : 3 jours de carence, du 02/03/2026 au 04/03/2026."
    )
    assert r["maintien"]["paliers"][0]["du"] == "2026-03-05"


def test_un_statut_absent_est_lu_non_cadre_et_le_bulletin_le_dit():
    r = _mois_sg(5, MAI, 1029.75, contexte=_contexte(statut=""))
    assert "Statut absent de la fiche : barème des non-cadres appliqué." in r["alertes"]
    assert r["maintien"]["maintien_verse"] == 1030.09


# --- Compatibilité : sans barème, rien ne change ------------------------------


@pytest.mark.parametrize("mois, periode, override", [(5, MAI, 1029.75), (6, JUIN, 1235.70)])
def test_sans_bareme_le_resultat_est_celui_d_avant_cle_pour_cle(mois, periode, override):
    sans = {k: v for k, v in {**BAREME, **MANUELS}.items() if k != "bareme_convention"}
    avant = _mois_sg(mois, periode, override, reglages=sans)
    assert _mois_sg(mois, periode, override, reglages={**sans, "bareme_convention": None}) == avant
    assert "paliers" not in avant["maintien"] and "bareme" not in avant["maintien"]
