"""Métallurgie, forfait jours : l'activité partielle ne fait pas baisser le net (art. 103.5.1)."""

from app.modules.activite_partielle.domain.calcul import LIBELLE_INDEMNITE, LIBELLE_RETENUE
from app.modules.payroll.engine import maintien_net_activite_partielle as m

PRIMES = [
    {"libelle": "Prime", "montant": 100.0, "soumise_a_cotisations": True, "soumise_a_impot": True},
    {"libelle": LIBELLE_RETENUE, "montant": -348.31, "soumise_a_cotisations": True, "soumise_a_impot": True},
    {"libelle": LIBELLE_INDEMNITE, "montant": 208.99, "soumise_a_cotisations": False, "soumise_a_impot": True},
]


def _net(primes, salaire=4000.0, part_salariale=0.22, csg_indemnite=0.0658):
    """Un calcul simplifié : salaire et primes cotisés à 22 %, indemnité à 6,58 %."""
    soumis = salaire + sum(p["montant"] for p in primes if p.get("soumise_a_cotisations"))
    exonere = sum(p["montant"] for p in primes if not p.get("soumise_a_cotisations"))
    return round(soumis * (1 - part_salariale) + exonere * (1 - csg_indemnite), 2)


def test_s_applique_seulement_en_metallurgie_avec_une_indemnite():
    assert m.s_applique("3248", PRIMES)
    assert m.s_applique("03248", PRIMES)
    assert not m.s_applique("0292", PRIMES)
    assert not m.s_applique("3248", PRIMES[:1])
    assert not m.s_applique(None, PRIMES)


def test_le_complement_rend_le_net_sans_activite_partielle():
    cible = _net(m.sans_activite_partielle(PRIMES))
    c = m.complement_qui_garde_le_net(PRIMES, _net)
    assert c > 0
    net = _net(m.avec_complement(PRIMES, c))
    # Ni moins (la convention), ni plus qu'un centime d'arrondi.
    assert cible <= net <= cible + 0.01


def test_le_complement_est_cotise_comme_un_salaire():
    ligne = m.avec_complement(PRIMES, 50.0)[-1]
    assert ligne["libelle"] == m.LIBELLE_COMPLEMENT
    assert ligne["soumise_a_cotisations"] is True and ligne["soumise_a_impot"] is True


def test_rien_quand_le_net_ne_baisse_pas():
    genereux = [*PRIMES[:2], {**PRIMES[2], "montant": 400.0}]
    assert m.complement_qui_garde_le_net(genereux, _net) == 0.0


def test_un_ancien_complement_est_remplace_pas_ajoute():
    primes = m.avec_complement(PRIMES, 80.0)
    assert [p["montant"] for p in m.avec_complement(primes, 90.0) if p["libelle"] == m.LIBELLE_COMPLEMENT] == [90.0]
    assert all(p["libelle"] != m.LIBELLE_COMPLEMENT for p in m.sans_activite_partielle(primes))


def test_net_avant_impot_lu_dans_la_synthese_sinon_reconstruit():
    assert m.net_avant_impot({"synthese_net": {"net_social_avant_impot": 3138.66}}) == 3138.66
    assert (
        m.net_avant_impot(
            {"net_a_payer": 2900.0, "synthese_net": {"impot_prelevement_a_la_source": {"montant": 238.66}}}
        )
        == 3138.66
    )
