"""Jour férié chômé : condition légale d'ancienneté (art. L3133-3 C. trav.).

Le maintien de salaire d'un jour férié chômé (hors 1er mai) suppose au moins
3 mois d'ancienneté dans l'entreprise. En dessous, le jour férié n'est pas payé
(déduit). Une CCN plus favorable peut abaisser le seuil (0 = payé dès l'embauche)
via `specificites_paie.jours_feries_anciennete_min_mois`.
"""

from __future__ import annotations

from app.modules.payroll.engine.calcul_brut import _jour_ferie_est_paye
from tests.unit.payroll.helpers import build_test_contexte


def _ferie(date_iso: str) -> dict:
    return {"type": "ferie", "date_complete": date_iso, "heures": 7.0}


def test_ferie_non_paye_par_defaut_avant_3_mois_anciennete():
    # Embauché le 04/05/2026, férié du 08/05/2026 → 0 mois d'ancienneté < 3.
    ctx = build_test_contexte(date_entree="2026-05-04")
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-08")) is False


def test_ferie_paye_par_defaut_apres_3_mois_anciennete():
    ctx = build_test_contexte(date_entree="2020-01-01")
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-08")) is True


def test_premier_mai_toujours_paye_meme_sans_anciennete():
    ctx = build_test_contexte(date_entree="2026-04-28")
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-01")) is True


def test_seuil_zero_explicite_paye_des_embauche():
    # CCN plus favorable : payé dès l'embauche (seuil 0 explicite).
    ctx = build_test_contexte(
        date_entree="2026-05-04",
        specificites_extra={"jours_feries_anciennete_min_mois": 0},
    )
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-08")) is True


def test_reprise_anciennete_ouvre_le_maintien_du_ferie():
    # Embauché récemment mais reprise d'ancienneté ancienne → payé.
    ctx = build_test_contexte(
        date_entree="2026-05-04",
        specificites_extra={
            "dsn_anciennete": {"date_anciennete": "2023-01-01"}
        },
    )
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-08")) is True


def test_ferie_paye_si_prior_service_months_couvre_le_seuil():
    # Nouveau contrat récent (12/01) mais 6 mois de service antérieurs (reprise
    # d'ancienneté) : ancienneté effective >= 3 mois au lundi de Pâques -> payé.
    ctx = build_test_contexte(date_entree="2026-01-12", prior_service_months=6)
    assert _jour_ferie_est_paye(ctx, _ferie("2026-04-06")) is True


def test_ferie_non_paye_si_prior_service_months_insuffisant():
    # 2 mois de service antérieurs : reste sous 3 mois -> déduit.
    ctx = build_test_contexte(date_entree="2026-05-04", prior_service_months=2)
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-08")) is False


def test_lundi_de_pentecote_neutre_par_defaut_meme_sans_anciennete():
    # À défaut d'accord (art. L3133-11), la journée de solidarité est le lundi de
    # Pentecôte (05/2026 : 25/05) : jour travaillé/neutre, jamais déduit.
    ctx = build_test_contexte(date_entree="2026-05-04")
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-25")) is True


def test_pentecote_chome_si_solidarite_fixee_ailleurs():
    # Si la journée de solidarité est fixée un autre jour, le lundi de Pentecôte
    # redevient un férié chômé ordinaire → déduit sous 3 mois d'ancienneté.
    ctx = build_test_contexte(date_entree="2026-05-04")
    ctx.entreprise.setdefault("parametres_paie", {})["jour_solidarite"] = "2026-11-11"
    assert _jour_ferie_est_paye(ctx, _ferie("2026-05-25")) is False
