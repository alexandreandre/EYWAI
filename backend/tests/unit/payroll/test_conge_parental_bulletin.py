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


def _jours_de_novembre_et_fin_octobre(**meta):
    return [
        {"date_complete": d.isoformat(), "type": "absence_non_remuneree", "heures": 0.0, **meta}
        for d in [date(2026, 10, j) for j in range(26, 32)] + [date(2026, 11, j) for j in range(1, 31)]
        if d.weekday() < 5
    ]


def _brut_fenetre_decalee(monkeypatch, calendrier):
    from app.modules.payroll.engine import calcul_brut as cb
    from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

    from .helpers import build_test_contexte

    monkeypatch.setattr(cb, "coefficient_horaire_reel", lambda *_: 1.0)
    contexte = build_test_contexte(salaire_base=1870.83, duree_hebdo=35.0, date_entree="2025-09-23")
    return calculer_salaire_brut(
        contexte, calendrier, date(2026, 11, 1), date(2026, 11, 30), [],
        date_debut_variables=date(2026, 10, 26), date_fin_variables=date(2026, 11, 22),
    )


def test_fenetre_des_variables_decalee_le_conge_parental_reste_au_mois_civil(monkeypatch):
    """LEWIS : variables du 26/10 au 22/11. Le congé parental suspend le contrat
    et porte ses dates (DSN 632) : comme l'arrêt, il est retenu au mois civil,
    du 1er au 30/11, et jamais les jours de fin octobre (bulletin d'octobre)."""
    resultat = _brut_fenetre_decalee(
        monkeypatch,
        _jours_de_novembre_et_fin_octobre(motif_absence=SOUS_TYPE_CONGE_PARENTAL, periode_absence=PERIODE),
    )
    lignes = [l for l in resultat["lignes_composants_brut"] if "congé parental" in l["libelle"]]
    assert [l["libelle"] for l in lignes] == ["Absence congé parental du 01/11/26 au 30/11/26"]
    assert lignes[0]["quantite"] == pytest.approx(21 * 7.0)


def test_fenetre_des_variables_decalee_le_sans_solde_reste_a_la_fenetre(monkeypatch):
    """Le sans solde ordinaire ne change pas : il suit la fenêtre des variables."""
    resultat = _brut_fenetre_decalee(monkeypatch, _jours_de_novembre_et_fin_octobre())
    dates = sorted(
        l["libelle"][-8:] for l in resultat["lignes_composants_brut"]
        if l["libelle"].startswith("Absence non rémunérée du")
    )
    assert "26/10/26" in dates and "20/11/26" in dates and "23/11/26" not in dates


def test_une_presence_parentale_reprise_n_est_pas_un_conge_parental():
    from app.modules.dsn_export.domain.evenements import _motif_suspension

    assert _motif_suspension("Abs. présence parentale 020326") is None
    assert _motif_suspension("Absence congé parental du 01/11/26 au 30/11/26") == "632"
    assert _motif_suspension("Absence non rémunérée du 03/11/26") == "501"


@pytest.mark.parametrize("profil", ("heures", "forfait_jours", "temps_partiel"))
def test_mois_civil_entier_brut_nul_et_aucune_cotisation(banc, profil):  # noqa: F811
    """Un mois entier de congé parental : rien de versé, rien de cotisé (sans
    mutuelle à la fiche : la mutuelle forfaitaire, elle, reste due tant que la
    fiche y adhère — voir le bac à sable de la salariée A)."""
    parental = banc.generer(
        profil, jours=_parental(ANNEE, MOIS), jours_des_mois_voisins=_voisins(_parental)
    )
    s = parental.get("structure_cotisations") or {}
    assert float(parental.get("salaire_brut") or 0) == pytest.approx(0.0, abs=0.01)
    assert float(s.get("total_salarial") or 0) == pytest.approx(0.0, abs=0.01)
    assert float(s.get("total_patronal") or 0) == pytest.approx(0.0, abs=0.01)
    assert float(parental.get("net_a_payer") or 0) == pytest.approx(0.0, abs=0.01)


def test_plafond_partiel_de_date_a_date_week_end_compris():
    """Congé du mercredi 26/08 : le plafond d'août ne court que du 1er au 25
    (25/31), samedis et dimanches du congé compris, comme un arrêt."""
    from app.modules.payroll.engine.calcul_cotisations import ratio_plafond_periode

    from .helpers import build_test_contexte

    periode = {"debut": "2026-08-26", "fin": "2027-08-25"}
    cal = [
        {
            "date_complete": f"2026-08-{j:02d}",
            "type": "absence_non_remuneree",
            "heures": 0.0,
            "motif_absence": SOUS_TYPE_CONGE_PARENTAL,
            "periode_absence": periode,
        }
        for j in (26, 27, 28, 31)
    ]
    ratio = ratio_plafond_periode(cal, date(2026, 8, 1), date(2026, 8, 31), build_test_contexte())
    assert ratio == pytest.approx(25 / 31, abs=1e-6)


def test_mois_sans_salaire_apres_un_cumul_negatif_ne_cotise_pas():
    """Salariée A : rappel d'IJSS repris en brut négatif (cumul -375,58). Un
    mois entier de congé (brut 0, plafond 0) rattrapait ce négatif en tranche
    1 ; il n'y a rien à cotiser sur un mois sans rémunération (CSS L242-1).
    Le mois payé suivant absorbe le négatif comme avant."""
    from app.modules.payroll.engine.calcul_cotisations import _calculer_assiettes

    from .helpers import build_test_contexte

    cumuls = {
        "cumuls": {
            "cumul_brut_agirc_arrco": -375.58,
            "cumul_pss_agirc_arrco": 0.0,
            "cumul_tranche_1_appliquee": -375.58,
            "cumul_tranche_2_appliquee": 0.0,
        }
    }
    ctx = build_test_contexte(cumuls=cumuls["cumuls"])
    ctx.month = 11
    ctx.ratio_plafond_ss = 0.0
    assert _calculer_assiettes(ctx, 0.0, 0.0)["brut_plafonne"] == pytest.approx(0.0, abs=0.01)

    paye = build_test_contexte(cumuls=cumuls["cumuls"])
    paye.month = 11
    assert _calculer_assiettes(paye, 1870.83, 0.0)["brut_plafonne"] == pytest.approx(1870.83, abs=0.01)


def test_une_prolongation_a_la_suite_prolonge_le_meme_bloc_632():
    from app.shared.domain.conge_parental import periode_du_jour, periodes_chainees

    def demande(debut, fin, **k):
        from datetime import timedelta

        d0, d1 = date.fromisoformat(debut), date.fromisoformat(fin)
        jours = [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
        return {"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
                "status": "validated", "selected_days": jours, **k}

    chaines = periodes_chainees([
        demande("2026-08-26", "2027-08-25"),
        demande("2027-08-26", "2028-08-25"),
        demande("2028-10-01", "2028-12-31"),
        demande("2026-01-01", "2026-01-31", status="cancelled"),
        {"type": "sans_solde", "status": "validated", "selected_days": ["2028-08-26"]},
    ])
    assert chaines == [
        {"debut": "2026-08-26", "fin": "2028-08-25"},
        {"debut": "2028-10-01", "fin": "2028-12-31"},
    ]
    assert periode_du_jour(chaines, "2027-09-01") == {"debut": "2026-08-26", "fin": "2028-08-25"}


def test_le_generateur_pose_les_bornes_de_la_prolongation():
    from app.modules.payroll.documents import payslip_generator as pg

    demandes = [
        {"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "status": "validated",
         "selected_days": ["2026-11-01", "2026-11-30"]},
        {"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "status": "validated",
         "selected_days": ["2026-12-01", "2027-03-31"]},
    ]
    jours = [{"annee": 2026, "mois": 11, "jour": 3, "type": "absence_non_remuneree",
              "motif_absence": SOUS_TYPE_CONGE_PARENTAL,
              "periode_absence": {"debut": "2026-11-01", "fin": "2026-11-30"}}]
    pg._stamp_periodes_du_conge_parental(jours, demandes)
    assert jours[0]["periode_absence"] == {"debut": "2026-11-01", "fin": "2027-03-31"}
