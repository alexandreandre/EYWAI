"""Prime d'ancienneté sur un mois sans aucun salaire, quand la convention ne dit rien (L15, 27/11).

Filet de la vague 2, Mont Blanc (plasturgie, IDCC 0292) : un mois entier en absence non rémunérée,
salaire retenu en entier, et la prime d'ancienneté (12 %) versée quand même.

La plasturgie calcule la prime à « 0,80 % du salaire de base par année d'ancienneté » (avenant
« Collaborateurs » du 15/05/1991, art. 14.2, rédaction de l'accord du 28/06/2011, Légifrance
KALITEXT000024769733) et ne dit rien des absences. La jurisprudence dépend de la rédaction :
- la prime « reste due intégralement (Cass. soc., 17 mars 1982, n° 80-40.167) sauf si la convention
  collective en dispose autrement » (Lamy, sort des primes en cas de suspension du contrat) ;
- elle n'est pas due pendant une absence non rémunérée quand la convention la fait s'ajouter « au
  salaire réel » et varier « avec l'horaire de travail » (Cass. soc., 2 avril 2025, n° 23-22.190,
  métallurgie : c'est le prorata de L8).
Le cabinet (Quadra) verse la prime entière sur un sans solde partiel (Mont Blanc, Comitech) ; aucun
mois entier n'est connu. Doute réel : le montant ne change pas, le bulletin le signale (question pour
Elsa). Le plafond de la Sécurité sociale en dépend : prime due, le plafond du mois ne peut être
réduit (BOSS, assiette générale, § 860).

Aux deux générateurs, par le vrai calcul du brut. Salarié fictif : 2 000 € de base, 35 h, entré en
2010 (12 %) : 240,00 € par mois.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

import pytest

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    document_to_engine_rules,
)
from app.modules.collective_agreements.rules.seeds.plasturgie_0292 import (
    PLASTURGIE_0292_SEED,
)
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.contexte import ChargerContexte
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot
from tests.unit.payroll.test_prime_anciennete_temps_paye import (
    _contexte as _contexte_metallurgie,
)

pytestmark = pytest.mark.unit

CODE = "prime_anciennete_mois_sans_salaire"
PLEIN = 240.00
FEVRIER = (date(2026, 2, 1), date(2026, 2, 28))
NOVEMBRE = (date(2026, 11, 1), date(2026, 11, 30))
SANS_SOLDE = {"type": "absence_non_remuneree", "heures": 0.0}
ARRET = {"type": "arret_maladie", "heures": 0.0}


def _plasturgie_baremes():
    baremes = deepcopy(baremes_snapshot())
    doc = CCRulesDocument(idcc="0292", prime_anciennete=PLASTURGIE_0292_SEED.prime)
    baremes.setdefault("conventions_collectives", {})["idcc_0292"] = document_to_engine_rules(doc)
    return baremes


def _contexte(*, forfait: bool = False, duree: float = 35, salaire: float = 2000.0):
    ctx = ChargerContexte(
        {
            "date_entree": "2010-01-04",
            "statut": "Non-cadre",
            "duree_hebdomadaire": duree,
            "salaire_base": salaire,
            "is_forfait_jour": forfait,
            "type_contrat": "CDI",
            "convention_collective": {"idcc": "0292", "libelle": "Plasturgie"},
            "classification_conventionnelle": {"coefficient": 800},
        },
        {"parametres_paie": {"effectif": 50}},
        _plasturgie_baremes(),
    )
    ctx.year = 2026
    return ctx


def _jours(debut: date, fin: date) -> list[date]:
    return [debut + timedelta(days=k) for k in range((fin - debut).days + 1)]


def _cal(debut, fin, absents: dict[date, dict], *, forfait=False, heures_jour=7.0):
    """Lundi à vendredi travaillés, sauf les jours donnés ; week-ends posés au forfait."""
    cal = []
    for jour in _jours(debut, fin):
        if jour in absents:
            cal.append({"date_complete": jour.isoformat(), **absents[jour]})
        elif jour.weekday() < 5:
            cal.append(
                {"date_complete": jour.isoformat(), "type": "travail_base", "heures": 1.0 if forfait else heures_jour}
            )
        elif forfait:
            cal.append({"date_complete": jour.isoformat(), "type": "weekend", "heures": 0.0})
    return cal


def _tout_le_mois(debut, fin, evenement=SANS_SOLDE):
    return {j: evenement for j in _jours(debut, fin) if j.weekday() < 5}


def _prime(resultat):
    for ligne in resultat["lignes_composants_brut"]:
        if "anciennet" in str(ligne.get("libelle") or "").lower():
            return ligne.get("gain")
    return None


def _alertes(ctx):
    return [a for a in ctx.alertes_baremes if a.get("code") == CODE]


def _heures(ctx, cal, periode, **k):
    k.setdefault("jours_maintien", set())
    return calculer_salaire_brut(ctx, cal, *periode, k.pop("primes", []), **k)


def _forfait(ctx, cal, periode, **k):
    k.setdefault("jours_maintien", set())
    return calculer_salaire_brut_forfait(ctx, cal, *periode, k.pop("primes", []), **k)


# 1) Mois entier sans solde : la prime reste (doute réel), le bulletin le dit.
def test_heures_mois_entier_sans_solde_prime_versee_et_signalee():
    ctx = _contexte()
    resultat = _heures(ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER)), FEVRIER, nb_jours_travail_planifies=0)
    # 20 journées de 100 € retiennent tout le salaire : seul reste la prime.
    assert resultat["salaire_brut_total"] == PLEIN
    assert _prime(resultat) == PLEIN
    (alerte,) = _alertes(ctx)
    assert alerte["severity"] == "warning" and not alerte["critique"]
    assert "240,00 €" in alerte["message"]
    assert "à confirmer" in alerte["message"]


def test_forfait_mois_entier_sans_solde_prime_versee_et_signalee():
    ctx = _contexte(forfait=True)
    resultat = _forfait(ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER), forfait=True), FEVRIER)
    assert _prime(resultat) == PLEIN
    assert len(_alertes(ctx)) == 1


# 2) Sans solde partiel : la prime entière, comme le cabinet, sans alerte.
def test_heures_sans_solde_partiel_prime_pleine_sans_alerte():
    ctx = _contexte()
    absents = {date(2026, 11, d): {"type": "absence_non_remuneree", "heures": 7.0} for d in range(9, 21)
               if date(2026, 11, d).weekday() < 5}
    resultat = _heures(ctx, _cal(*NOVEMBRE, absents), NOVEMBRE, nb_jours_travail_planifies=12)
    assert _prime(resultat) == PLEIN
    assert _alertes(ctx) == []


def test_forfait_sans_solde_partiel_prime_pleine_sans_alerte():
    ctx = _contexte(forfait=True)
    absents = {date(2026, 11, d): {"type": "absence_non_remuneree", "heures": 1.0} for d in range(9, 21)
               if date(2026, 11, d).weekday() < 5}
    resultat = _forfait(ctx, _cal(*NOVEMBRE, absents, forfait=True), NOVEMBRE)
    assert _prime(resultat) == PLEIN
    assert _alertes(ctx) == []


# 3) À cheval sur la fenêtre des variables (26/01 au 25/02) et le mois civil.
FENETRE_FEVRIER = (date(2026, 1, 26), date(2026, 2, 25))


def test_heures_sans_solde_de_toute_la_fenetre_mais_jours_travailles_au_mois_civil_sans_alerte():
    """Sans solde du 26/01 au 25/02, travail les 26 et 27/02 : le mois civil a des jours prévus
    travaillés, le salaire n'est pas retenu en entier ; prime entière, pas d'alerte."""
    ctx = _contexte()
    absents = _tout_le_mois(*FENETRE_FEVRIER)
    cal = _cal(date(2026, 1, 26), date(2026, 2, 28), absents)
    resultat = _heures(
        ctx, cal, FEVRIER, nb_jours_travail_planifies=2,
        date_debut_variables=FENETRE_FEVRIER[0], date_fin_variables=FENETRE_FEVRIER[1],
    )
    assert not any("intégrale" in str(l.get("libelle")) for l in resultat["lignes_composants_brut"])
    assert _prime(resultat) == PLEIN
    assert _alertes(ctx) == []


def test_heures_sans_solde_de_tout_le_mois_civil_qui_deborde_de_la_fenetre_signale():
    """Sans solde du 26/01 au 31/03 : février sans aucun jour prévu travaillé, salaire retenu en
    entier même si les 26 et 27/02 relèvent de la fenêtre de mars : l'alerte suit le salaire."""
    ctx = _contexte()
    absents = _tout_le_mois(date(2026, 1, 26), date(2026, 3, 31))
    cal = _cal(date(2026, 1, 26), date(2026, 2, 28), absents)
    resultat = _heures(
        ctx, cal, FEVRIER, nb_jours_travail_planifies=0,
        date_debut_variables=FENETRE_FEVRIER[0], date_fin_variables=FENETRE_FEVRIER[1],
    )
    assert any("intégrale" in str(l.get("libelle")) for l in resultat["lignes_composants_brut"])
    assert _prime(resultat) == PLEIN
    assert len(_alertes(ctx)) == 1


# 4) Temps partiel : même règle, la prime du temps partiel est signalée.
def test_heures_temps_partiel_mois_entier_sans_solde_signale():
    ctx = _contexte(duree=24, salaire=1371.43)
    resultat = _heures(
        ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER), heures_jour=4.8), FEVRIER, nb_jours_travail_planifies=0
    )
    prime = _prime(resultat)
    assert prime == round(1371.43 * 0.12, 2)
    (alerte,) = _alertes(ctx)
    assert f"{prime:.2f}".replace(".", ",") + " €" in alerte["message"]


def test_heures_temps_partiel_sans_solde_partiel_sans_alerte():
    ctx = _contexte(duree=24, salaire=1371.43)
    absents = {date(2026, 2, d): {"type": "absence_non_remuneree", "heures": 4.8} for d in (9, 10, 11)}
    resultat = _heures(ctx, _cal(*FEVRIER, absents, heures_jour=4.8), FEVRIER, nb_jours_travail_planifies=17)
    assert _prime(resultat) == round(1371.43 * 0.12, 2)
    assert _alertes(ctx) == []


# 5) Arrêt de tout le mois : sans maintien, même question ; maintenu, rien à signaler.
def test_heures_arret_de_tout_le_mois_sans_maintien_signale():
    ctx = _contexte()
    resultat = _heures(ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER, ARRET)), FEVRIER, nb_jours_travail_planifies=0)
    assert _prime(resultat) == PLEIN
    assert len(_alertes(ctx)) == 1


def test_heures_arret_de_tout_le_mois_maintenu_sans_alerte():
    ctx = _contexte()
    maintien = {j.day for j in _jours(*FEVRIER) if j.weekday() < 5}
    resultat = _heures(
        ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER, ARRET)), FEVRIER,
        nb_jours_travail_planifies=0, jours_maintien=maintien,
    )
    assert _prime(resultat) == PLEIN
    assert _alertes(ctx) == []


def test_forfait_arret_de_tout_le_mois_maintenu_sans_alerte():
    ctx = _contexte(forfait=True)
    maintien = {j.day for j in _jours(*FEVRIER) if j.weekday() < 5}
    resultat = _forfait(
        ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER, ARRET), forfait=True), FEVRIER, jours_maintien=maintien,
    )
    assert _prime(resultat) == PLEIN
    assert _alertes(ctx) == []


# 6) La prime saisie du mois remplace le calcul : plus rien à signaler sur la prime calculée.
@pytest.mark.parametrize("forfait", (False, True))
def test_prime_saisie_qui_remplace_le_calcul_retire_l_alerte(forfait):
    ctx = _contexte(forfait=forfait)
    saisie = [{"libelle": "Prime d'ancienneté", "montant": 100.0}]
    if forfait:
        resultat = _forfait(ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER), forfait=True), FEVRIER, primes=saisie)
    else:
        resultat = _heures(
            ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER)), FEVRIER, primes=saisie, nb_jours_travail_planifies=0
        )
    assert _prime(resultat) == 100.0
    assert _alertes(ctx) == []
    assert any(a.get("code") == "prime_anciennete_remplacee" for a in ctx.alertes_baremes)


# 7) Métallurgie (L8) : la prime suit le temps payé, nulle sur ce mois ; rien à signaler en plus.
@pytest.mark.parametrize("forfait", (False, True))
def test_metallurgie_mois_entier_sans_solde_aucune_prime_aucune_alerte(forfait):
    ctx = _contexte_metallurgie(forfait=forfait)
    if forfait:
        resultat = _forfait(ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER), forfait=True), FEVRIER)
    else:
        resultat = _heures(ctx, _cal(*FEVRIER, _tout_le_mois(*FEVRIER)), FEVRIER, nb_jours_travail_planifies=0)
    assert _prime(resultat) is None
    assert _alertes(ctx) == []
