"""Congé parental d'éducation : le bulletin d'un sans solde, au centime, avec son nom.

Retour d'Elsa du 26/11/2026 (salariée A, LEWIS). Le congé parental d'éducation
à temps plein suspend le contrat sans salaire (C. trav. L1225-47 ;
service-public.fr F2280) : il se saisit comme un congé sans solde de sous-type
« congé parental d'éducation ». Aux deux générateurs (heures et forfait jours),
le bulletin doit être celui du même sans solde — brut, net, net imposable,
cotisations — et seule la ligne change : « Absence congé parental du … au … »,
une par mois au lieu d'une par jour. La DSN lit sur cette ligne la suspension
entière (632, premier jour et fin prévue).
"""

from __future__ import annotations

import calendar
from datetime import date

import pytest

from app.modules.dsn_export.domain.evenements import (
    blocs_suspension,
    suspensions_du_bulletin,
)
from app.shared.domain.conge_parental import SOUS_TYPE_CONGE_PARENTAL
from tests.unit.payroll.profils_salaries import ANNEE, MOIS, banc  # noqa: F401

pytestmark = pytest.mark.unit

PERIODE = {"debut": "2026-07-01", "fin": "2027-06-30"}
PROFILS_TESTES = ("heures", "forfait_jours", "apprenti", "temps_partiel")


def _jours(annee: int, mois: int, premiers: int = 1, derniers: int | None = None, **meta) -> dict:
    fin = derniers or calendar.monthrange(annee, mois)[1]
    return {
        j: {"type": "absence_non_remuneree", **meta}
        for j in range(premiers, fin + 1)
        if date(annee, mois, j).weekday() < 5
    }


def _parental(annee: int, mois: int, **k) -> dict:
    return _jours(annee, mois, motif_absence=SOUS_TYPE_CONGE_PARENTAL, periode_absence=PERIODE, **k)


def _voisins(fabrique) -> dict:
    return {(ANNEE, MOIS - 1): fabrique(ANNEE, MOIS - 1), (ANNEE, MOIS + 1): fabrique(ANNEE, MOIS + 1)}


def _lignes(donnees: dict) -> list[dict]:
    """Les lignes du brut et celles des absences (le bulletin les range à part)."""
    return [
        l
        for cle in ("calcul_du_brut", "details_absences")
        for l in (donnees.get(cle) or [])
        if isinstance(l, dict)
    ]


def _empreinte(donnees: dict) -> dict:
    """Ce qui doit être identique au centime entre sans solde et congé parental."""
    cotisations = [
        (c.get("libelle"), c.get("base"), c.get("montant_salarial"), c.get("montant_patronal"))
        for c in donnees.get("structure_cotisations", {}).get("bloc_principales", []) or []
    ]
    synthese = donnees.get("synthese_net") or {}
    return {
        "brut": round(float(donnees.get("salaire_brut") or 0), 2),
        "net": round(float(donnees.get("net_a_payer") or 0), 2),
        "net_imposable": round(float(synthese.get("net_imposable") or 0), 2),
        "retenues": round(sum(float(l.get("perte") or 0) for l in _lignes(donnees)), 2),
        "cotisations": cotisations,
    }


@pytest.mark.parametrize("profil", PROFILS_TESTES)
def test_mois_entier_meme_bulletin_qu_un_sans_solde(banc, profil):  # noqa: F811
    sans_solde = banc.generer(
        profil, jours=_jours(ANNEE, MOIS), jours_des_mois_voisins=_voisins(_jours)
    )
    parental = banc.generer(
        profil, jours=_parental(ANNEE, MOIS), jours_des_mois_voisins=_voisins(_parental)
    )

    assert _empreinte(parental) == _empreinte(sans_solde)
    libelles = [str(l.get("libelle")) for l in _lignes(parental)]
    assert not any(l.startswith("Absence non rémunérée") for l in libelles)
    lignes_parental = [l for l in libelles if l.startswith("Absence congé parental du")]
    assert lignes_parental, libelles
    if profil != "forfait_jours":
        assert lignes_parental == ["Absence congé parental du 01/10/26 au 31/10/26"]


@pytest.mark.parametrize("profil", PROFILS_TESTES)
def test_mois_partiel_meme_brut_et_libelle_borne_au_conge(banc, profil):  # noqa: F811
    periode = {"debut": f"{ANNEE}-{MOIS:02d}-12", "fin": f"{ANNEE}-{MOIS:02d}-23"}
    sans_solde = banc.generer(profil, jours=_jours(ANNEE, MOIS, 12, 23))
    parental = banc.generer(
        profil,
        jours=_jours(
            ANNEE, MOIS, 12, 23, motif_absence=SOUS_TYPE_CONGE_PARENTAL, periode_absence=periode
        ),
    )

    assert _empreinte(parental) == _empreinte(sans_solde)
    libelles = [str(l.get("libelle")) for l in _lignes(parental)]
    assert any(l.startswith("Absence congé parental du 12/10/26 au 23/10/26") for l in libelles), libelles


@pytest.mark.parametrize("profil", ("heures", "forfait_jours"))
def test_la_dsn_declare_632_du_premier_jour_a_la_fin_prevue(banc, profil):  # noqa: F811
    parental = banc.generer(
        profil, jours=_parental(ANNEE, MOIS), jours_des_mois_voisins=_voisins(_parental)
    )

    assert suspensions_du_bulletin(parental) == [("632", date(2026, 7, 1), date(2027, 6, 30))]
    assert blocs_suspension(parental) == [
        {
            "S21.G00.65.001": "632",
            "S21.G00.65.002": "01072026",
            "S21.G00.65.003": "30062027",
        }
    ]


@pytest.mark.parametrize("profil", ("heures", "forfait_jours"))
def test_un_sans_solde_reste_declare_501(banc, profil):  # noqa: F811
    sans_solde = banc.generer(profil, jours=_jours(ANNEE, MOIS, 12, 23))

    motifs = {motif for motif, _, _ in suspensions_du_bulletin(sans_solde)}
    assert motifs == {"501"}
