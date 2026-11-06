"""Le congé pris indemnise la période d'acquisition, dans la bonne unité."""
from types import SimpleNamespace

from app.modules.payroll.engine.calcul_conges import calculer_indemnite_conges


def contexte(reference=None, **valeurs):
    cumuls = {"cumuls": {"brut_reference_n_1": 6000.0, "brut_reference_period_start": "2026-06-01"}}
    if reference is not None:
        cumuls["reference_dixieme_conges"] = reference
    return SimpleNamespace(cumuls=cumuls, baremes={}, duree_hebdo_contrat=35.0, alertes_baremes=[], **valeurs)


def test_periode_acquise_et_denominateur_ouvre_service_public():
    ctx = contexte({"coefficient_jours_evenements": 1.0, "periode_precedente": {
        "base": 24000.0, "droits": 25.0, "restants": 25.0,
    }})
    r = calculer_indemnite_conges(ctx, 10.0, 2000.0 / 147.0)
    assert r["montant_indemnite"] == 960.0
    assert r["methode_retenue"] == "1/10ème"
    assert ctx.cumuls["cumuls"]["brut_reference_n_1"] == 6000.0


def test_unite_ouvrable_convertie_pour_le_dixieme_seulement():
    ctx = contexte({"coefficient_jours_evenements": 1.2, "periode_precedente": {
        "base": 24000.0, "droits": 30.0, "restants": 30.0,
    }})
    assert calculer_indemnite_conges(ctx, 10.0, 2000.0 / 147.0)["montant_indemnite"] == 960.0


def test_un_ancien_cumul_sans_reference_reste_calculable_et_signale():
    ctx = contexte()
    assert calculer_indemnite_conges(ctx, 2.0, 10.0)["montant_indemnite"] == 140.0
    assert any("inconnue" in a["message"] for a in ctx.alertes_baremes)


def test_forfait_jours_garde_sa_valeur_de_jour_au_maintien():
    ctx = contexte({"coefficient_jours_evenements": 1.0, "periode_precedente": {
        "base": 36000.0, "droits": 25.0, "restants": 25.0,
    }})
    assert calculer_indemnite_conges(ctx, 10.0, 3000.0 / 21.67 / 7)["montant_indemnite"] == 1440.0


def test_plusieurs_periodes_comparees_separement():
    ctx = contexte({"coefficient_jours_evenements": 1.0,
        "periode_precedente": {"base": 30000.0, "droits": 25.0, "restants": 4.0},
        "periode_en_cours": {"base": None, "droits": 10.0, "restants": 10.0}})
    r = calculer_indemnite_conges(ctx, 6.0, 100.0 / 7)
    assert r["montant_indemnite"] == 680.0  # 4 × 120 puis 2 × 100
    assert ctx.alertes_baremes
