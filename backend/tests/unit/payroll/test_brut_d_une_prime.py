"""Le brut d'une prime pour un net voulu se calcule sur le bulletin du salarié. [lot 30]

La fenêtre des primes (« Net cible (€) — calcul inverse ») envoyait le net
voulu POUR LA PRIME (100 €) à la route du calcul inverse, qui cherche le brut
d'un bulletin ENTIER dont le net à payer vaut 100 €. Mesuré en bac à sable
(octobre 2026, lecture seule) :

- avant le lot 30 (bulletin simplifié, sans le salarié) : 127,60 € pour 100 €
  et 640,50 € pour 500 €, les mêmes pour un salarié de Colorplast et un de
  Comitech ;
- après le passage au moteur complet : 125,03 € et 622,60 € (Colorplast),
  136,20 € et 680,97 € (Comitech), sans convergence pour trois des quatre :
  un « salaire » de 130 € sur un horaire de 39 h porte les heures
  supplémentaires structurelles, et la recherche ne s'encadre plus.

Le bon calcul est marginal : le brut X tel que net(bulletin du mois avec la
prime X) − net(bulletin du mois sans elle) = net voulu, sur le bulletin du
salarié (son salaire, ses saisies du mois, ses cumuls), calculé en bac à sable
(rien n'est écrit). Un mode explicite de la requête, que seule la fenêtre des
primes envoie ; l'onglet « Calcul Inverse » garde le bulletin entier.
"""

from __future__ import annotations

import inspect

import pytest

from app.modules.payroll.application import simulation_queries as sq
from app.modules.payroll.application.prime_nette import chercher_brut_de_prime
from app.modules.payroll.documents.bac_a_sable import BacASable, saisies_du_mois

pytestmark = pytest.mark.unit


def _bulletin(net_a_payer: float, cout: float) -> dict:
    return {"net_a_payer": net_a_payer, "pied_de_page": {"cout_total_employeur": cout}}


def _salarie_39h(montant: float) -> dict:
    """Un bulletin d'octobre : 1 710,06 € nets sans prime ; la prime perd
    21,71 % jusqu'à 300 € bruts, 24 % au-delà (une tranche de plus) ; le net
    est arrondi au centime, comme celui du moteur."""
    if montant <= 300:
        delta = montant * 0.7829
    else:
        delta = 300 * 0.7829 + (montant - 300) * 0.76
    return _bulletin(round(1710.06 + delta, 2), round(2728.57 + montant * 1.18, 2))


class _Compteur:
    def __init__(self, bulletin):
        self.bulletin = bulletin
        self.montants: list[float] = []

    def __call__(self, montant: float) -> dict:
        self.montants.append(montant)
        return self.bulletin(montant)


@pytest.mark.parametrize("net_voulu", [100.0, 500.0])
def test_le_brut_trouve_ajoute_le_net_voulu_au_centime(net_voulu):
    bulletin = _Compteur(_salarie_39h)

    r = chercher_brut_de_prime(net_voulu, bulletin)

    assert r["net_obtenu"] == pytest.approx(net_voulu, abs=0.01)
    assert r["net_obtenu"] == pytest.approx(
        _salarie_39h(r["brut_calcule"])["net_a_payer"] - 1710.06, abs=1e-6
    )
    assert r["brut_calcule"] == round(r["brut_calcule"], 2)
    assert r["convergence"] is True
    # Le bulletin sans la prime d'abord, puis quelques essais seulement : chaque
    # bulletin du mois coûte une génération complète.
    assert bulletin.montants[0] == 0.0
    assert len(bulletin.montants) <= 5
    assert r["iterations"] == len(bulletin.montants)
    assert r["net_a_payer_sans_prime"] == pytest.approx(1710.06)
    assert r["net_a_payer_avec_prime"] == pytest.approx(1710.06 + r["net_obtenu"])
    assert r["cout_employeur"] == pytest.approx(round(r["brut_calcule"] * 1.18, 2), abs=0.01)


def test_une_prime_sans_cotisations_ni_impot_vaut_son_net():
    r = chercher_brut_de_prime(100.0, lambda m: _bulletin(round(1710.06 + m, 2), 2728.57 + m))

    assert r["brut_calcule"] == pytest.approx(100.0)
    assert r["net_obtenu"] == pytest.approx(100.0)


def test_le_bac_a_sable_ajoute_les_saisies_en_memoire_aux_saisies_lues():
    lue = {"name": "Prime d'assiduité", "amount": 50}
    en_plus = {"name": "Prime (calcul du brut)", "amount": 127.73}

    assert saisies_du_mois([lue], BacASable(saisies_en_plus=(en_plus,))) == [lue, en_plus]
    assert saisies_du_mois([lue], BacASable()) == [lue]
    assert saisies_du_mois([lue], None) == [lue]
    assert saisies_du_mois(None, None) == []


@pytest.mark.parametrize(
    "module",
    [
        "app.modules.payroll.documents.payslip_generator",
        "app.modules.payroll.documents.payslip_generator_forfait",
    ],
)
def test_les_deux_generateurs_lisent_les_saisies_du_bac_a_sable(module):
    import importlib

    source = inspect.getsource(importlib.import_module(module))
    assert "saisies_du_mois(saisies_res.data, bac_a_sable)" in source


def test_le_fournisseur_passe_les_saisies_en_plus_au_bac_a_sable(monkeypatch):
    from app.modules.payslips.infrastructure import providers

    recu: dict = {}
    monkeypatch.setattr(
        providers.employee_statut_reader, "get_employee_statut", lambda _eid: "Non-Cadre"
    )
    monkeypatch.setattr(
        providers,
        "process_payslip_generation",
        lambda **kwargs: recu.update(kwargs) or {"payslip_data": {}},
    )
    ligne = {"name": "Prime (calcul du brut)", "amount": 127.73}
    providers.payslip_generator_provider.generate_en_bac_a_sable(
        "emp", 2026, 10, {"cumuls": {}}, saisies_en_plus=(ligne,)
    )

    assert recu["bac_a_sable"].saisies_en_plus == (ligne,)
    assert recu["bac_a_sable"].cumuls_precedents == {"cumuls": {}}


@pytest.fixture
def bac(monkeypatch):
    from app.modules.payslips.infrastructure import providers

    appels: list[dict] = []

    def generer(employee_id, year, month, cumuls_precedents=None, saisies_en_plus=()):
        appels.append(
            {
                "employee_id": employee_id,
                "year": year,
                "month": month,
                "cumuls": cumuls_precedents,
                "saisies": list(saisies_en_plus),
            }
        )
        montant = sum(float(s["amount"]) for s in saisies_en_plus)
        return {"payslip_data": _salarie_39h(montant)}

    monkeypatch.setattr(providers.payslip_generator_provider, "generate_en_bac_a_sable", generer)
    # Les lectures préchargées en parallèle (lot 31) : sans objet ici.
    monkeypatch.setattr(sq, "_precharger_le_bulletin_du_mois", lambda *_a: [], raising=False)
    monkeypatch.setattr(sq, "load_company", lambda _cid: {"id": "soc"})
    monkeypatch.setattr(
        sq, "load_employee", lambda eid, cid: {"id": eid, "company_id": cid}
    )
    monkeypatch.setattr(
        sq.simulation_repository,
        "fetch_cumuls_du_mois",
        lambda eid, year, month: {"cumuls": {"brut_total": 20000.0}, "mois": (year, month)},
        raising=False,
    )

    def bulletin_entier(**_k):
        raise AssertionError("le mode prime ne passe pas par le bulletin entier")

    monkeypatch.setattr(sq.simulation_commands, "run_reverse_calculation", bulletin_entier)
    return appels


def test_le_mode_prime_calcule_sur_le_bulletin_du_salarie_en_bac_a_sable(bac):
    r = sq.run_reverse_calculation_for_company(
        company_id="soc",
        employee_id="emp",
        net_target=100.0,
        net_type="net_a_payer",
        options={},
        month=10,
        year=2026,
        mode="prime",
        prime_soumise_a_cotisations=True,
        prime_soumise_a_impot=False,
    )

    assert r["mode"] == "prime"
    assert r["net_obtenu"] == pytest.approx(100.0, abs=0.01)
    assert (r["month"], r["year"]) == (10, 2026)
    assert all((a["employee_id"], a["year"], a["month"]) == ("emp", 2026, 10) for a in bac)
    # Les cumuls de septembre, lus (jamais écrits) : la réduction générale et le
    # prélèvement du mois partent du vrai passé du salarié.
    assert all(a["cumuls"]["mois"] == (2026, 9) for a in bac)
    assert bac[0]["saisies"] == []
    # La prime proposée a été essayée (le dernier essai peut être le centime
    # d'en dessous, qui confirme qu'elle est la première : lot 31).
    (prime,) = next(a["saisies"] for a in bac if a["saisies"] and a["saisies"][0]["amount"] == r["brut_calcule"])
    assert prime["amount"] == pytest.approx(r["brut_calcule"])
    assert prime["is_socially_taxed"] is True
    assert prime["is_taxable"] is False
    assert prime["sur_le_net"] is False


def test_le_mode_prime_demande_un_salarie(bac):
    with pytest.raises(ValueError, match="salarié"):
        sq.run_reverse_calculation_for_company(
            company_id="soc",
            employee_id=None,
            net_target=100.0,
            net_type="net_a_payer",
            options={},
            month=10,
            year=2026,
            mode="prime",
        )


def test_le_routeur_passe_le_mode_et_les_cases_de_la_prime(monkeypatch):
    from app.modules.payroll.api import router as routeur

    recu: dict = {}
    monkeypatch.setattr(routeur, "_require_rh_or_admin", lambda _u: "soc")
    monkeypatch.setattr(
        routeur.simulation_queries,
        "run_reverse_calculation_for_company",
        lambda **kwargs: recu.update(kwargs) or {},
    )
    corps = routeur.ReverseCalculationRequest(
        employee_id="emp",
        net_target=100,
        net_type="net_a_payer",
        month=10,
        year=2026,
        mode="prime",
        prime_soumise_a_cotisations=True,
        prime_soumise_a_impot=False,
    )
    routeur.reverse_calculation(corps, current_user=object())

    assert recu["mode"] == "prime"
    assert recu["prime_soumise_a_cotisations"] is True
    assert recu["prime_soumise_a_impot"] is False


def test_sans_mode_la_route_garde_le_bulletin_entier():
    from app.modules.payroll.api import router as routeur

    corps = routeur.ReverseCalculationRequest(
        employee_id=None, net_target=1800, net_type="net_a_payer", month=10, year=2026
    )
    assert corps.mode == "bulletin_entier"
