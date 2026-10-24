"""Un mois sans jour travaillé n'est pas « entièrement absent » s'il reste un férié payé.

La retenue « absence intégrale du mois » retient tout le salaire quand aucun
jour n'est travaillé au planning. Un férié chômé qui tombe hors de toute
absence reste pourtant payé : « Le chômage du 1er mai ne peut être une cause
de réduction de salaire » (C. trav., art. L3133-5) ; « Le chômage des jours
fériés ne peut entraîner aucune perte de salaire pour les salariés totalisant
au moins trois mois d'ancienneté » (art. L3133-3).

Cas de Comitech, mai 2026 (S.G., 39 h, 1 952,60 €) : arrêt du 04/05 au 31/05,
le vendredi 1er mai férié puis le week-end. Quadra retient « Absence maladie
040526-310526 » 140 h à 12,8740 et 16 h structurelles à 16,0925, fériés de
l'arrêt compris, et laisse 171,64 € du salaire de 2 231,48 €. Martine retenait
tout le mois.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

MAI = (date(2026, 5, 1), date(2026, 5, 31))
JANVIER = (date(2026, 1, 1), date(2026, 1, 31))
NOVEMBRE = (date(2026, 11, 1), date(2026, 11, 30))
FERIES_MAI = (date(2026, 5, 1), date(2026, 5, 8), date(2026, 5, 14), date(2026, 5, 25))
COMPLEMENT = "Complément retenue absence intégrale du mois"


def _ctx(date_entree: str = "2003-07-15", **extra):
    ctx = build_test_contexte(
        salaire_base=1952.60,
        duree_hebdo=39.0,
        date_entree=date_entree,
        specificites_extra={"salaire_hors_hs_structurelles": True, **extra},
    )
    ctx.baremes.setdefault("heures_supp", {}).setdefault(
        "regles_calcul_communes", {}
    ).setdefault("taux_majoration_par_defaut", {})["heures_supplementaires"] = [
        {"taux": 0.25},
        {"taux": 0.50},
    ]
    return ctx


def _jours(periode):
    jour, fin = periode
    while jour <= fin:
        yield jour
        jour += timedelta(days=1)


def _arret(debut: date, fin: date, periode, feries=()) -> list[dict]:
    """Le calendrier qu'écrit la validation d'un arrêt : les jours ouvrés
    retypés, les fériés de la période gardant leur type mais portant les bornes."""
    bornes = {
        "arret_type": "maladie_simple",
        "date_debut_arret_reel": debut.isoformat(),
        "date_fin_arret_reel": fin.isoformat(),
    }
    cal = []
    for jour in _jours(periode):
        dans_l_arret = debut <= jour <= fin
        if jour in feries:
            ev = {"date_complete": jour.isoformat(), "type": "ferie", "heures": 0.0}
            cal.append({**ev, **bornes} if dans_l_arret else ev)
        elif dans_l_arret and jour.weekday() < 5:
            cal.append(
                {"date_complete": jour.isoformat(), "type": "arret_maladie", "heures": 0, **bornes}
            )
    return cal


def _brut(ctx, cal, periode):
    return calculer_salaire_brut(ctx, cal, *periode, nb_jours_travail_planifies=0)


def _pertes(result, debut_libelle: str) -> float:
    return round(
        sum(
            float(l.get("perte") or 0)
            for l in result["lignes_composants_brut"]
            if l["libelle"].startswith(debut_libelle)
        ),
        2,
    )


def _libelles(result) -> list[str]:
    return [l["libelle"] for l in result["lignes_composants_brut"]]


def test_le_1er_mai_avant_un_arret_qui_couvre_le_reste_du_mois_reste_paye():
    result = _brut(_ctx(), _arret(date(2026, 5, 4), date(2026, 5, 31), MAI, FERIES_MAI), MAI)
    assert not any(l.startswith(COMPLEMENT) for l in _libelles(result))
    # Les fériés compris dans l'arrêt (8, 14 et 25 mai) restent retenus avec lui :
    # 20 jours, 140 h de base et 16 h structurelles, comme Quadra.
    assert _pertes(result, "Absence arrêt maladie") == 1802.36
    assert _pertes(result, "Réduction HS structurelles") == 257.48
    assert result["salaire_brut_total"] == 171.64


def test_un_ferie_dans_un_arret_qui_couvre_tout_le_mois_reste_retenu():
    # Le 1er mai est dans l'arrêt : le mois est entièrement absent, rien ne change.
    result = _brut(_ctx(), _arret(date(2026, 4, 20), date(2026, 6, 10), MAI, FERIES_MAI), MAI)
    assert _pertes(result, "Absence arrêt maladie") == 1532.00
    assert _pertes(result, "Réduction HS structurelles") == 218.86
    assert _pertes(result, COMPLEMENT) == 480.62
    assert result["salaire_brut_total"] == 0.0


def test_un_ferie_du_dimanche_hors_de_l_arret_ne_retire_rien_du_mois():
    # Toussaint 2026 un dimanche, arrêt du lundi 2 au 30 novembre, 11 novembre
    # compris : aucun jour ouvré n'est payé hors de l'arrêt.
    feries = (date(2026, 11, 1), date(2026, 11, 11))
    result = _brut(_ctx(), _arret(date(2026, 11, 2), date(2026, 11, 30), NOVEMBRE, feries), NOVEMBRE)
    assert _pertes(result, COMPLEMENT) > 0
    assert result["salaire_brut_total"] == 0.0


def test_un_ferie_paye_hors_de_l_arret_reste_paye_hors_du_1er_mai():
    # 1er janvier (jeudi), arrêt du 02/01 au 31/01 : 21 jours retenus sur 22.
    result = _brut(_ctx(), _arret(date(2026, 1, 2), date(2026, 1, 31), JANVIER, (date(2026, 1, 1),)), JANVIER)
    assert not any(l.startswith(COMPLEMENT) for l in _libelles(result))
    assert result["salaire_brut_total"] == 68.65


def test_moins_de_trois_mois_d_anciennete_le_ferie_non_paye_et_l_arret_retiennent_le_salaire_exact():
    # Entré le 15/11/2025 : le 1er janvier n'est pas payé (L3133-3). Le mois est
    # alors entièrement absent, et la retenue vaut le salaire, ni plus ni moins :
    # la retenue du férié s'ajoutait au complément, 90,12 € de trop.
    result = _brut(
        _ctx("2025-11-15", jours_feries_anciennete_min_mois=3),
        _arret(date(2026, 1, 2), date(2026, 1, 31), JANVIER, (date(2026, 1, 1),)),
        JANVIER,
    )
    assert _pertes(result, "Abs. jour férié non payé") == 90.12
    assert repr(result["salaire_brut_total"]) == "0.0"  # ni -90,12 ni « -0,00 »


def test_moins_de_trois_mois_d_anciennete_le_1er_mai_reste_paye():
    result = _brut(
        _ctx("2026-03-16", jours_feries_anciennete_min_mois=3),
        _arret(date(2026, 5, 4), date(2026, 5, 31), MAI, FERIES_MAI),
        MAI,
    )
    assert not any(l.startswith(COMPLEMENT) for l in _libelles(result))
    # 8, 14 et 25 mai, dans l'arrêt, sont retenus comme jours d'arrêt.
    assert result["salaire_brut_total"] == 171.64


def test_un_ferie_entre_deux_arrets_distincts_reste_paye():
    # Arrêt du 27/04 au 07/05, puis nouvel arrêt du 11/05 au 05/06 : le 8 mai
    # n'est dans aucun des deux.
    cal = [
        ev
        for ev in _arret(date(2026, 4, 27), date(2026, 5, 7), MAI, FERIES_MAI)
        if date.fromisoformat(ev["date_complete"]) <= date(2026, 5, 7)
    ] + [
        ev
        for ev in _arret(date(2026, 5, 11), date(2026, 6, 5), MAI, FERIES_MAI)
        if date.fromisoformat(ev["date_complete"]) >= date(2026, 5, 8)
    ]
    result = _brut(_ctx(), cal, MAI)
    assert not any(l.startswith(COMPLEMENT) for l in _libelles(result))
    # 20 jours retenus (1er mai compris dans le premier arrêt), le 8 mai payé.
    assert result["salaire_brut_total"] == 171.64


def test_un_conge_sans_solde_apres_le_1er_mai_le_laisse_paye():
    cal = [{"date_complete": "2026-05-01", "type": "ferie", "heures": 0.0}]
    for jour in _jours((date(2026, 5, 4), date(2026, 5, 31))):
        if jour in FERIES_MAI:
            cal.append({"date_complete": jour.isoformat(), "type": "ferie", "heures": 0.0})
        elif jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "absence_non_remuneree", "heures": 0})
    result = _brut(_ctx(), cal, MAI)
    assert not any(l.startswith(COMPLEMENT) for l in _libelles(result))
    # Les fériés compris dans le congé (8, 14 et 25 mai) restent retenus avec
    # lui : 20 journées de 7 h de base (90,12 € chacune, arrondies jour par
    # jour) et 16 h structurelles.
    assert _pertes(result, "Absence non rémunérée") == round(20 * 90.12, 2)
    assert result["salaire_brut_total"] == round(2231.48 - 20 * 90.12 - 257.48, 2)


def test_forfait_jours_le_1er_mai_avant_un_arret_n_est_pas_retenu():
    # Le forfait jours ne passe pas par la retenue « intégrale » des heures : sa
    # règle « absence sur tout le mois » veut tous les jours ouvrés absents.
    ctx = build_test_contexte(
        statut="Cadre", salaire_base=3608.0, specificites_extra={"is_forfait_jour": True}
    )
    cal = _arret(date(2026, 5, 4), date(2026, 5, 31), MAI, FERIES_MAI)
    result = calculer_salaire_brut_forfait(ctx, cal, *MAI, [])
    assert not any(l.startswith("Absence sur tout le mois") for l in _libelles(result))
    assert result["salaire_brut_total"] > 0
