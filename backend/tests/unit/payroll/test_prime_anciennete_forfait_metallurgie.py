"""Prime d'ancienneté de la métallurgie au forfait en jours : majoration de 30 %.

CCN de la métallurgie du 7 février 2022, art. 142 (Légifrance KALIARTI000046999200, ouvert le
08/11/2026) : « Le montant de la prime d'ancienneté varie avec l'horaire de travail. Il supporte donc,
le cas échéant, les majorations pour heures supplémentaires ou au titre des conventions de forfait en
jours sur l'année, soit la majoration de 30 % dans les conditions de l'article 139 ». Art. 139 : pour
le forfait en jours sur l'année, les minima « sont majorés de 30 % ».
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete
from tests.unit.payroll.test_prime_anciennete_metallurgie import _metallurgie_baremes

pytestmark = pytest.mark.unit


def _contexte(*, forfait: bool, classe: int = 8, date_entree: str = "2021-06-14"):
    employee = {
        "date_entree": date_entree,
        "statut": "Non-cadre",
        "duree_hebdomadaire": 35,
        "salaire_base": 3251.13,
        "is_forfait_jour": forfait,
        "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
        "classification_conventionnelle": {"classe_emploi": classe, "coefficient": classe},
    }
    company = {
        "adresse_code_postal": "79140",
        "identification": {"adresse": {"code_postal": "79140"}},
        "parametres_paie": {"effectif": 70},
    }
    return ChargerContexte(employee, company, _metallurgie_baremes())


def _jours_forfait(n: int = 17) -> list[dict]:
    return [{"date_complete": f"2026-10-{d:02d}", "type": "travail_base", "heures": 1.0} for d in range(1, n + 1)]


def test_au_forfait_en_jours_la_prime_est_majoree_de_30_pour_cent():
    """Classe 8 (2,9 %), point des Deux-Sèvres 2026 (5,80 €), 5 ans : 5,80 × 2,9 × 5 = 84,10 €,
    majoré de 30 % = 109,33 €."""
    ligne = calculer_ligne_prime_anciennete(
        _contexte(forfait=True), calendrier_saisie=_jours_forfait(),
        date_debut_periode=date(2026, 10, 1), date_fin_periode=date(2026, 10, 31))
    assert ligne is not None
    assert ligne["gain"] == pytest.approx(109.33, abs=0.01)


def test_hors_forfait_la_prime_n_est_pas_majoree():
    cal = [{"date_complete": f"2026-10-{d:02d}", "type": "travail", "heures": 151.67 / 22} for d in range(1, 23)]
    ligne = calculer_ligne_prime_anciennete(
        _contexte(forfait=False), calendrier_saisie=cal,
        date_debut_periode=date(2026, 10, 1), date_fin_periode=date(2026, 10, 31))
    assert ligne is not None
    assert ligne["gain"] == pytest.approx(84.10, abs=0.02)


def test_la_majoration_vaut_aussi_pour_les_regles_en_valeur_du_point_de_la_metallurgie():
    """Les règles en base de Cartol et LEWIS décrivent la prime en « valeur_du_point » avec un taux
    par classe (octobre à blanc : 84,10 € sans majoration) : c'est la convention (IDCC 3248) qui
    impose la majoration, pas le nom de la méthode."""
    ctx = _contexte(forfait=True)
    regles = ctx.baremes["conventions_collectives"]["idcc_3248"]["prime_anciennete"]
    regles["base_de_calcul"] = {**(regles.get("base_de_calcul") or {}), "methode": "valeur_du_point"}
    ligne = calculer_ligne_prime_anciennete(
        ctx, calendrier_saisie=_jours_forfait(),
        date_debut_periode=date(2026, 10, 1), date_fin_periode=date(2026, 10, 31))
    assert ligne is not None
    assert ligne["gain"] == pytest.approx(109.33, abs=0.01)
