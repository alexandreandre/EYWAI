"""compute_trial_period_end doit rendre la même date que le calcul de référence."""

from datetime import date

from app.modules.employees.domain.trial_period_shared import compute_trial_period_end


def test_deux_mois_finissent_la_veille_du_quantieme():
    assert compute_trial_period_end(
        "2026-03-01", {"duree_initiale": 2, "unite": "mois"}
    ) == date(2026, 4, 30)


def test_quantieme_inexistant_va_au_dernier_jour_du_mois():
    assert compute_trial_period_end(
        "2026-01-31", {"duree_initiale": 1, "unite": "mois"}
    ) == date(2026, 2, 28)


def test_jours_comptent_le_jour_d_embauche():
    assert compute_trial_period_end(
        "2026-03-02", {"duree_initiale": 8, "unite": "jours"}
    ) == date(2026, 3, 9)


def test_ancienne_cle_duree_toujours_acceptee():
    assert compute_trial_period_end(
        "2026-03-01", {"duree": 2, "unite": "mois"}
    ) == date(2026, 4, 30)


def test_donnees_absentes():
    assert compute_trial_period_end(None, {"duree_initiale": 2, "unite": "mois"}) is None
    assert compute_trial_period_end("2026-03-01", None) is None
    assert compute_trial_period_end("2026-03-01", {"duree_initiale": 0}) is None
