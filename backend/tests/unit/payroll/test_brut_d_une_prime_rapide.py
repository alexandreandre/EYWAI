"""Le brut d'une prime : la base lue une fois, les essais en mémoire, peu d'essais. [lot 31]

Mesuré sur le site de test le 12/10 : 16,7 s pour une prime de 100 € nets,
15,8 s pour 500 €. Chaque essai relançait une génération complète du bulletin
du mois et relisait la base (56 requêtes environ). Désormais :

- tous les essais se font dans une même `lecture_seule()` : la base est lue au
  premier bulletin, les suivants se calculent en mémoire, et rien n'est écrit ;
- le brut rendu est le plus petit centime qui ajoute exactement le net voulu.
  Le net d'un bulletin avance par marches d'arrondi : mesuré chez Colorplast
  (octobre 2026), 129,27 € et 129,29 € ajoutent tous deux 100,00 € et 129,28 €
  ajoute 100,01 €. La réponse ne dépend donc plus du chemin de la recherche ;
- la recherche vise ce centime par la sécante qui part du bulletin sans prime,
  puis voit le centime d'en dessous : quatre bulletins en règle générale
  (sans prime, la pente, le centime visé, celui d'en dessous), trois pour une
  prime ni soumise ni imposable.
"""

from __future__ import annotations

import pytest

from app.core.lecture_seule import ecritures_permises, lecture_seule_en_cours
from app.modules.payroll.application import simulation_queries as sq
from app.modules.payroll.application.prime_nette import chercher_brut_de_prime

pytestmark = pytest.mark.unit

NET_SANS_PRIME = 1710.06
PRECHARGER = sq._precharger_le_bulletin_du_mois

# Le net ajouté autour de la réponse, mesuré en bac à sable sur les bulletins
# d'octobre 2026 des deux salariés du lot 30 (CDI de 39 h).
MARCHES_MESUREES = {
    ("Colorplast", 100.0): {129.24: 99.97, 129.25: 99.98, 129.26: 99.99, 129.27: 100.00,
                            129.28: 100.01, 129.29: 100.00},
    ("Colorplast", 500.0): {646.42: 499.99, 646.43: 499.98, 646.44: 499.99, 646.45: 500.00,
                            646.46: 500.01, 646.47: 500.02},
    ("Comitech", 100.0): {129.52: 99.97, 129.53: 99.98, 129.54: 99.99, 129.55: 100.00,
                          129.56: 100.01, 129.57: 100.00},
    ("Comitech", 500.0): {647.78: 499.98, 647.79: 499.99, 647.80: 499.99, 647.81: 500.00,
                          647.82: 500.01, 647.83: 500.02},
}
REPONSES_DU_LOT_30 = {
    ("Colorplast", 100.0): 129.27,
    ("Colorplast", 500.0): 646.45,
    ("Comitech", 100.0): 129.55,
    ("Comitech", 500.0): 647.81,
}


def _bulletin(net_ajoute: float, *, taux_pas: float = 1.6) -> dict:
    return {
        "net_a_payer": round(NET_SANS_PRIME + net_ajoute, 2),
        "pied_de_page": {"cout_total_employeur": 2728.57},
        "synthese_net": {"impot_prelevement_a_la_source": {"taux": taux_pas}},
    }


class _Bulletins:
    """Le bulletin du mois avec une prime de `montant` bruts ; compte les calculs."""

    def __init__(self, net_ajoute):
        self.net_ajoute = net_ajoute
        self.montants: list[float] = []

    def __call__(self, montant: float) -> dict:
        self.montants.append(montant)
        return _bulletin(self.net_ajoute(round(montant, 2)) if montant else 0.0)


def _sur_les_marches(cas, biais: float = 0.0):
    """Hors des marches mesurées, une droite qui passe par la réponse ; inclinée
    de `biais`, la recherche y arrive par un autre chemin."""
    marches, net, reponse = MARCHES_MESUREES[cas], cas[1], REPONSES_DU_LOT_30[cas]
    pente = net / reponse * (1 + biais)

    def net_ajoute(montant: float) -> float:
        if montant in marches:
            return marches[montant]
        return round(net + (montant - reponse) * pente, 2)

    return net_ajoute


@pytest.mark.parametrize("cas", sorted(REPONSES_DU_LOT_30))
@pytest.mark.parametrize("biais", [-0.0005, 0.0, 0.0003, 0.0008])
def test_le_brut_est_le_plus_petit_centime_qui_ajoute_le_net_voulu(cas, biais):
    bulletins = _Bulletins(_sur_les_marches(cas, biais))

    r = chercher_brut_de_prime(cas[1], bulletins)

    assert r["brut_calcule"] == REPONSES_DU_LOT_30[cas]
    assert r["net_obtenu"] == pytest.approx(cas[1])
    assert r["convergence"] is True
    assert r["iterations"] == len(bulletins.montants) <= 6


@pytest.mark.parametrize("cas", sorted(REPONSES_DU_LOT_30))
def test_quatre_bulletins_suffisent_sur_une_droite(cas):
    # Le bulletin sans prime, un essai qui donne la pente, puis le centime visé
    # et celui d'en dessous, qui ne doit pas atteindre le net voulu.
    bulletins = _Bulletins(_sur_les_marches(cas))

    r = chercher_brut_de_prime(cas[1], bulletins)

    assert bulletins.montants[0] == 0.0
    assert len(bulletins.montants) == 4
    assert r["brut_calcule"] == REPONSES_DU_LOT_30[cas]


def _salarie_39h(montant: float) -> float:
    """Le modèle du lot 30 : la prime perd 21,71 % jusqu'à 300 € bruts, 24 %
    au-delà (une tranche de plus)."""
    if montant <= 300:
        return round(montant * 0.7829, 2)
    return round(300 * 0.7829 + (montant - 300) * 0.76, 2)


@pytest.mark.parametrize("net_voulu", [100.0, 500.0])
def test_sur_le_modele_du_lot_30_le_premier_centime_au_plus_en_cinq_bulletins(net_voulu):
    bulletins = _Bulletins(_salarie_39h)

    r = chercher_brut_de_prime(net_voulu, bulletins)

    assert r["net_obtenu"] == pytest.approx(net_voulu)
    assert _salarie_39h(round(r["brut_calcule"] - 0.01, 2)) < net_voulu
    assert len(bulletins.montants) <= 5


def test_une_prime_ni_soumise_ni_imposable_se_trouve_en_trois_bulletins():
    bulletins = _Bulletins(lambda montant: montant)

    r = chercher_brut_de_prime(
        100.0, bulletins, soumise_a_cotisations=False, soumise_a_impot=False
    )

    assert r["brut_calcule"] == 100.0
    assert len(bulletins.montants) == 3


def test_une_prime_imposable_seulement_part_du_taux_du_prelevement():
    # 1,6 % prélevé à la source sur un net imposable de 1 666,02 €.
    def net_ajoute(montant: float) -> float:
        impot = round((1666.02 + montant) * 0.016, 2) - round(1666.02 * 0.016, 2)
        return round(montant - impot, 2)

    bulletins = _Bulletins(net_ajoute)

    r = chercher_brut_de_prime(
        100.0, bulletins, soumise_a_cotisations=False, soumise_a_impot=True
    )

    assert r["net_obtenu"] == pytest.approx(100.0)
    assert net_ajoute(round(r["brut_calcule"] - 0.01, 2)) < 100.0
    # Le premier essai tombe au centime près : il reste à voir celui d'en dessous.
    assert len(bulletins.montants) <= 4


def test_sans_centime_exact_le_plus_petit_brut_qui_depasse_le_net_voulu_et_le_dit():
    # Une marche de deux centimes enjambe le net voulu : aucun brut au centime
    # n'ajoute 100,00 €. Le brut rendu est le premier qui l'atteint ou le
    # dépasse, et la recherche dit qu'elle n'a pas convergé (la fenêtre écrit
    # alors « 100,01 € (100,00 € voulus) »).
    def net_ajoute(montant: float) -> float:
        net = round(montant * 0.7736, 2)
        return 100.01 if net == 100.0 else net

    r = chercher_brut_de_prime(100.0, _Bulletins(net_ajoute))

    assert r["net_obtenu"] == pytest.approx(100.01)
    assert r["ecart"] == pytest.approx(0.01)
    assert r["convergence"] is False
    assert net_ajoute(round(r["brut_calcule"] - 0.01, 2)) < 100.0


# --- La grille du prélèvement à la source ---------------------------------
#
# Régression mesurée sur le site de test après le lot 31 (MAJI, CDI de 35 h à
# 2 100 €, sans taux personnalisé, octobre 2026) : 500 € nets donnaient
# 760,32 € pour 499,98 € ajoutés, sans convergence ; le lot 30 donnait
# 760,34 € pour 500,00 €. Sans taux personnalisé, le prélèvement suit la grille
# du taux neutre : quand la prime fait passer le net imposable dans la tranche
# suivante, tout le salaire est prélevé au nouveau taux et le net à payer recule
# de plusieurs euros. La droite qui part du bulletin sans prime n'a plus la
# pente du bulletin près de la réponse : la recherche s'en approchait trop
# lentement et s'arrêtait à court d'essais.

GRILLE_DU_TAUX_NEUTRE = [
    (1620, 0.0), (1683, 0.005), (1791, 0.013), (1911, 0.021), (2042, 0.029),
    (2151, 0.035), (2294, 0.041), (2714, 0.053), (3107, 0.075), (10**9, 0.099),
]


def _net_a_la_grille(prime: float) -> float:
    brut = 2100.0 + prime
    imposable = round(brut * 0.8155, 2)
    taux = next(t for borne, t in GRILLE_DU_TAUX_NEUTRE if imposable < borne)
    return round(round(brut * 0.7807 - 30.0, 2) - round(imposable * taux, 2), 2)


def _ajoute_a_la_grille(prime: float) -> float:
    return round(_net_a_la_grille(round(prime, 2)) - _net_a_la_grille(0.0), 2)


@pytest.mark.parametrize(
    "net_voulu", [37.5, 100.0, 300.0, 480.0, 500.0, 505.0, 510.0, 520.0, 700.0, 1234.56]
)
def test_a_la_grille_du_prelevement_le_brut_ajoute_exactement_le_net_voulu(net_voulu):
    bulletins = _Bulletins(_ajoute_a_la_grille)

    r = chercher_brut_de_prime(net_voulu, bulletins)

    assert r["net_obtenu"] == pytest.approx(net_voulu)
    assert r["convergence"] is True
    # Le premier centime qui l'atteint, là où la recherche croise le net voulu.
    assert _ajoute_a_la_grille(round(r["brut_calcule"] - 0.01, 2)) < net_voulu
    assert len(bulletins.montants) <= 10


def test_a_la_grille_les_reponses_du_lot_30_restent_celles_du_lot_31():
    # Mêmes réponses que le lot 30 là où il s'arrêtait sur le premier centime.
    for net_voulu, brut in ((500.0, 770.87), (510.0, 784.44), (520.0, 798.0), (300.0, 448.94)):
        assert chercher_brut_de_prime(net_voulu, _Bulletins(_ajoute_a_la_grille))["brut_calcule"] == brut


# --- Le mode « prime » de la route ----------------------------------------


@pytest.fixture
def essais(monkeypatch) -> list[dict]:
    from app.modules.payslips.infrastructure import providers

    vus: list[dict] = []

    def generer(employee_id, year, month, cumuls_precedents=None, saisies_en_plus=()):
        montant = sum(float(s["amount"]) for s in saisies_en_plus)
        vus.append(
            {
                "portee": lecture_seule_en_cours(),
                "ecritures_permises": ecritures_permises(),
                "saisies": list(saisies_en_plus),
            }
        )
        return {"payslip_data": _bulletin(_salarie_39h(montant) if montant else 0.0)}

    monkeypatch.setattr(providers.payslip_generator_provider, "generate_en_bac_a_sable", generer)
    monkeypatch.setattr(sq, "_precharger_le_bulletin_du_mois", lambda *_a: [])
    monkeypatch.setattr(sq, "load_employee", lambda eid, cid: {"id": eid, "company_id": cid})
    monkeypatch.setattr(
        sq.simulation_repository, "fetch_cumuls_du_mois", lambda *_a: {"cumuls": {}}, raising=False
    )
    return vus


def _prime(**cases) -> dict:
    return sq.run_reverse_calculation_for_company(
        company_id="soc",
        employee_id="emp",
        net_target=100.0,
        net_type="net_a_payer",
        options={},
        month=10,
        year=2026,
        mode="prime",
        **cases,
    )


def test_tous_les_essais_se_font_dans_une_meme_lecture_seule(essais):
    r = _prime()

    assert r["net_obtenu"] == pytest.approx(100.0)
    portees = {id(e["portee"]) for e in essais}
    assert len(portees) == 1 and essais[0]["portee"] is not None
    assert not any(e["ecritures_permises"] for e in essais)
    # Le bloc est refermé : le reste de la requête écrit comme avant.
    assert lecture_seule_en_cours() is None
    assert ecritures_permises() is True


def test_les_cases_de_la_prime_orientent_le_premier_essai(essais):
    _prime(prime_soumise_a_cotisations=False, prime_soumise_a_impot=False)

    # Ni soumise ni imposable : le premier essai est le net voulu lui-même.
    assert essais[1]["saisies"][0]["amount"] == pytest.approx(100.0)
    assert essais[1]["saisies"][0]["is_socially_taxed"] is False
    assert essais[1]["saisies"][0]["is_taxable"] is False


def test_les_soldes_de_conges_et_les_baremes_se_lisent_en_parallele_du_premier_bulletin(
    essais, monkeypatch
):
    # Ces lectures ne dépendent pas du calcul : lues dans un autre fil, dans la
    # même lecture seule, le premier bulletin les retrouve en mémoire au lieu
    # de les attendre l'une après l'autre (16 des 46 lectures, lot 31).
    import threading

    from app.core import database
    from app.modules.absences.application import queries as absences
    from app.modules.payroll.engine import baremes_loader

    lues: list[tuple[str, int, object]] = []

    def noter(quoi):
        def lire(*_a, **_k):
            lues.append((quoi, threading.get_ident(), lecture_seule_en_cours()))
            return {}

        return lire

    monkeypatch.setattr(sq, "_precharger_le_bulletin_du_mois", PRECHARGER)
    monkeypatch.setattr(absences, "get_absence_balances_for_payslip", noter("soldes de congés"))
    monkeypatch.setattr(baremes_loader, "charger_db_baremes", noter("barèmes"))
    monkeypatch.setattr(baremes_loader, "charger_conventions_collectives", noter("conventions"))
    monkeypatch.setattr(database, "get_supabase_admin_client", lambda: object())

    _prime()

    assert sorted(q for q, *_ in lues) == ["barèmes", "conventions", "soldes de congés"]
    assert all(fil != threading.get_ident() for _, fil, _ in lues)
    assert {id(portee) for *_, portee in lues} == {id(essais[0]["portee"])}


def test_un_prechargement_en_echec_ne_change_pas_le_calcul(essais, monkeypatch):
    from app.core import database
    from app.modules.absences.application import queries as absences
    from app.modules.payroll.engine import baremes_loader

    def en_panne(*_a, **_k):
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(sq, "_precharger_le_bulletin_du_mois", PRECHARGER)
    monkeypatch.setattr(absences, "get_absence_balances_for_payslip", en_panne)
    monkeypatch.setattr(baremes_loader, "charger_db_baremes", en_panne)
    monkeypatch.setattr(database, "get_supabase_admin_client", lambda: object())

    r = _prime()

    assert r["net_obtenu"] == pytest.approx(100.0)
