"""Activité partielle au calendrier : le bulletin n'est pas « à recalculer » à sa naissance.

Constat du 24/11/2026 (société fictive, un salarié en activité partielle en
juillet) : juste après sa génération, le bulletin était marqué « variables du
mois changées : recalculez », et ne pouvait donc pas être validé. Les deux
lignes d'activité partielle tirées du calendrier (retenue, indemnité) sont
ajoutées aux saisies du mois en mémoire (`lignes_du_calendrier`), et le
générateur hachait cette liste-là. La relecture (liste des bulletins, contrôle
de validation) lit les saisies en base, où ces lignes n'existent pas :
l'empreinte différait toujours.

L'empreinte porte sur les entrées réelles : les saisies telles que lues en
base (le calendrier, qui fait foi, est déjà haché). Le générateur tourne ici
pour de vrai jusqu'au bout du bac à sable, aux heures et au forfait jours,
avec le vrai calcul des lignes d'activité partielle ; seules ses lectures en
base et le calcul du bulletin sont doublés.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from app.modules.activite_partielle.application import service as ap_service
from app.modules.activite_partielle.domain.calendrier import TYPE_JOUR
from app.modules.payroll.application import empreinte_entrees_service as svc
from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents import payslip_generator_forfait as pgf
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.payroll.domain.empreinte_entrees import (
    empreinte_stockee,
    message_a_recalculer,
    parties_changees,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import Complements
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    ANNEE,
    EMP,
    MOIS,
    SOCIETE,
    _Base,
    _prevu,
    moteur,
)

pytestmark = pytest.mark.unit

#: Une prime saisie à la main, telle que la base la rend.
PRIME = {
    "year": ANNEE,
    "month": MOIS,
    "name": "Prime exceptionnelle",
    "amount": 100.0,
    "is_socially_taxed": True,
    "is_taxable": True,
}
#: Une retenue d'activité partielle saisie à la main : le calendrier la remplace.
AP_A_LA_MAIN = {
    "year": ANNEE,
    "month": MOIS,
    "name": "Heures chômées (act. part.)",
    "amount": -50.0,
    "payroll_quantity": 3,
    "is_socially_taxed": True,
    "is_taxable": True,
}
REGLAGE = {
    "company_id": SOCIETE,
    "active": True,
    "date_debut": "2026-06-01",
    "date_fin": None,
    "taux_indemnite": 60.0,
    "plancher_horaire": 9.74,
    "plafond_horaire": 33.24,
    "heures_par_jour": None,
}
#: Jours ouvrés de septembre posés « Activité partielle ».
JOURS_AP = (8, 9)


def _prevu_de_septembre(jours_ap) -> list[dict]:
    """Planning de 35 h (7 h par jour ouvré) ; les jours chômés gardent leurs 7 h."""
    prevu = _prevu(ANNEE, MOIS, en_arret=False)
    for entree in prevu:
        if entree["type"] == "travail":
            entree["heures_prevues"] = 7.0
        if entree["jour"] in jours_ap:
            entree.update(type=TYPE_JOUR, heures_prevues=7.0)
    return prevu


class _BaseAP(_Base):
    """Septembre travaillé, des jours d'activité partielle, des saisies en base."""

    def __init__(self, *, jours_ap=JOURS_AP, saisies=(PRIME,), forfait=False):
        super().__init__([], compensation=False)
        self.lignes[1]["planned_calendar"] = {"calendrier_prevu": _prevu_de_septembre(jours_ap)}
        self.saisies = [dict(s) for s in saisies]
        self.forfait = forfait

    def lire(self, table: str, colonnes: str):
        if table == "employees":
            fiche = super().lire(table, colonnes)
            fiche.update(
                salaire_de_base={"type": "mensuel", "valeur": 2500.0},
                duree_hebdomadaire=35,
            )
            if self.forfait:
                fiche.update(is_forfait_jour=True, statut="Cadre", duree_hebdomadaire=None)
            return fiche
        if table == "monthly_inputs":
            # Une copie : le générateur ne doit pas pouvoir changer « la base ».
            return [dict(s) for s in self.saisies]
        return super().lire(table, colonnes)


@pytest.fixture
def activite_partielle(monkeypatch):
    """Le vrai calcul des lignes, sur un réglage lu en mémoire, sans reprise."""
    import app.shared.reprise_paie as reprise

    monkeypatch.setattr(ap_service, "lire_reglage", lambda _cid: dict(REGLAGE))
    # Forfait annuel de 218 jours, sans lire les réglages de congés de la société.
    monkeypatch.setattr(ap_service, "_jours_du_forfait", lambda _e: 218.0)
    monkeypatch.setattr(reprise, "fin_de_la_reprise_au_premier_mois", lambda *_a, **_k: None)


class _Espion:
    """Les pièces que le générateur passe à l'empreinte d'entrée."""

    def __init__(self):
        self.lectures: dict = {}


@pytest.fixture
def espion(monkeypatch) -> _Espion:
    etat = _Espion()
    vraie = svc.poser_empreinte_depuis_lectures

    def poser(payslip_data, **kwargs):
        etat.lectures = kwargs
        return vraie(payslip_data, **kwargs)

    monkeypatch.setattr(svc, "poser_empreinte_depuis_lectures", poser)
    return etat


def _generer_heures(monkeypatch, base: _BaseAP) -> dict:
    monkeypatch.setattr(pg, "supabase", base)
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    return pg.process_payslip_generation(EMP, ANNEE, MOIS, bac_a_sable=BacASable())


def _relue(base: _BaseAP, lectures: dict, *, calendriers=None) -> str:
    """L'empreinte que la relecture calcule : les saisies telles que la base les
    rend, le reste tel que le générateur l'a lu (calendrier, absences, fiche,
    société, fenêtre des variables — que la fixture `moteur` fixe au mois civil)."""
    return svc.empreinte_des_lectures(
        **{
            **lectures,
            "saisies": [dict(s) for s in base.saisies],
            "calendriers": lectures["calendriers"] if calendriers is None else calendriers,
        }
    )


def _parties(lectures: dict, *, saisies=None, reglage=REGLAGE) -> dict[str, str]:
    """L'empreinte complémentaire (un hash par partie) de ces lectures. Posée hors
    bac à sable seulement : on la calcule ici sur les pièces du générateur, ou
    sur les saisies de la base pour la relecture."""
    lu = {**lectures, **({} if saisies is None else {"saisies": [dict(s) for s in saisies]})}
    entrees = svc.entrees_depuis_lectures(**lu)
    du_mois = svc.complements_du_mois(
        Complements(activite_partielle=dict(reglage) if reglage else None),
        year=ANNEE,
        month=MOIS,
        employee=lu["employee"],
        company=lu["company"],
        calendriers=lu["calendriers"],
        fenetre=entrees.get("fenetre_variables"),
        absences=lu["absences"],
    )
    return svc.empreintes_des_parties(entrees, du_mois, mois=(ANNEE, MOIS))


class _Calcul:
    """Ce que le moteur a reçu : les primes du fichier de saisies du mois."""

    def __init__(self):
        self.primes: list[dict] = []


@pytest.fixture
def calcul(monkeypatch, moteur) -> _Calcul:  # noqa: F811
    import json

    from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures

    etat = _Calcul()

    def run_factice(employee_path, year, month, *_a, **_k):
        saisies = json.loads((employee_path / "saisies" / f"{month:02d}.json").read_text("utf-8"))
        etat.primes = list(saisies.get("primes") or [])
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_factice)
    monkeypatch.setattr(payslip_run_forfait, "run_payslip_generation_forfait", run_factice)
    return etat


LIBELLES_AP = ["Heures chômées (act. part.)", "Indemnité activité partielle"]


def _libelles_ap(primes: list[dict]) -> list[str]:
    return sorted(str(p.get("libelle")) for p in primes if p.get("libelle") in LIBELLES_AP)


# --- Aux heures -----------------------------------------------------------------


@pytest.mark.parametrize(
    "saisies", [(PRIME,), (PRIME, AP_A_LA_MAIN), ()], ids=["prime", "ap_a_la_main", "aucune"]
)
def test_heures_l_empreinte_de_la_generation_est_celle_de_la_relecture(
    monkeypatch, calcul, activite_partielle, espion, saisies
):
    base = _BaseAP(saisies=saisies)
    resultat = _generer_heures(monkeypatch, base)

    # Le calendrier a bien produit les deux lignes, calculées (pas la saisie à la main).
    assert _libelles_ap(calcul.primes) == LIBELLES_AP, calcul.primes
    assert all(p.get("montant") != -50.0 for p in calcul.primes)
    stockee = empreinte_stockee(resultat["payslip_data"])
    assert stockee and stockee == _relue(base, espion.lectures)
    # L'empreinte complémentaire, partie par partie, aussi.
    assert parties_changees(_parties(espion.lectures), _parties(espion.lectures, saisies=base.saisies)) == ()


# --- Au forfait jours -----------------------------------------------------------


def _generer_forfait(monkeypatch, base: _BaseAP) -> dict:
    from app.modules.payroll.application import salary_evolution_payroll

    monkeypatch.setattr(pgf, "build_convention_collective_payload", lambda *_a, **_k: {})
    monkeypatch.setattr(
        salary_evolution_payroll, "prepare_salary_evolution_for_payslip", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        pgf,
        "get_jei_settings_raw",
        lambda *_a: SimpleNamespace(jei_enabled=False, date_creation_etablissement=None, taux_exoneration=None),
    )
    monkeypatch.setattr(pgf, "supabase", base)
    monkeypatch.setattr(pg, "supabase", base)
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    return pgf.process_payslip_generation_forfait(EMP, ANNEE, MOIS, bac_a_sable=BacASable())


def _generer(monkeypatch, generateur: str, base: _BaseAP) -> dict:
    return (_generer_heures if generateur == "heures" else _generer_forfait)(monkeypatch, base)


@pytest.mark.parametrize(
    "saisies", [(PRIME,), (PRIME, AP_A_LA_MAIN), ()], ids=["prime", "ap_a_la_main", "aucune"]
)
def test_forfait_l_empreinte_de_la_generation_est_celle_de_la_relecture(
    monkeypatch, calcul, activite_partielle, espion, saisies
):
    base = _BaseAP(saisies=saisies, forfait=True)
    resultat = _generer_forfait(monkeypatch, base)

    assert _libelles_ap(calcul.primes) == LIBELLES_AP, calcul.primes
    assert all(p.get("montant") != -50.0 for p in calcul.primes)
    stockee = empreinte_stockee(resultat["payslip_data"])
    assert stockee and stockee == _relue(base, espion.lectures)
    # L'empreinte complémentaire, partie par partie, aussi.
    assert parties_changees(_parties(espion.lectures), _parties(espion.lectures, saisies=base.saisies)) == ()


# --- Les deux générateurs : une vraie modification se voit toujours ------------


def _calendrier_sans_jour_ap(lectures: dict, jour: int) -> dict:
    """Le calendrier lu, où la gestionnaire a remis un jour chômé en travail."""
    calendriers = copy.deepcopy(dict(lectures["calendriers"]))
    for entree in calendriers[(ANNEE, MOIS)]["planned_calendar"]["calendrier_prevu"]:
        if entree["jour"] == jour:
            entree.update(type="travail", heures_prevues=7.0)
    return calendriers


@pytest.mark.parametrize("generateur", ["heures", "forfait_jours"])
def test_un_jour_d_activite_partielle_retire_du_calendrier_rend_le_bulletin_a_recalculer(
    monkeypatch, calcul, activite_partielle, espion, generateur
):
    base = _BaseAP(forfait=generateur == "forfait_jours")
    stockee = empreinte_stockee(_generer(monkeypatch, generateur, base)["payslip_data"])

    assert stockee == _relue(base, espion.lectures)
    assert stockee != _relue(
        base, espion.lectures, calendriers=_calendrier_sans_jour_ap(espion.lectures, JOURS_AP[0])
    )


@pytest.mark.parametrize("generateur", ["heures", "forfait_jours"])
@pytest.mark.parametrize(
    "changement",
    ["prime_ajoutee", "prime_modifiee", "ap_a_la_main_ajoutee"],
)
def test_une_saisie_changee_rend_le_bulletin_a_recalculer(
    monkeypatch, calcul, activite_partielle, espion, generateur, changement
):
    """Même la retenue saisie à la main que le calendrier remplace : c'est une
    donnée d'entrée, la poser ou l'effacer change l'empreinte."""
    base = _BaseAP(forfait=generateur == "forfait_jours")
    stockee = empreinte_stockee(_generer(monkeypatch, generateur, base)["payslip_data"])
    assert stockee == _relue(base, espion.lectures)

    if changement == "prime_ajoutee":
        base.saisies.append({**PRIME, "name": "Prime de froid", "amount": 30.0})
    elif changement == "prime_modifiee":
        base.saisies[0]["amount"] = 120.0
    else:
        base.saisies.append(dict(AP_A_LA_MAIN))
    assert stockee != _relue(base, espion.lectures)


# --- Sans activité partielle : l'empreinte des bulletins existants ne bouge pas --
#
# Valeurs relevées sur le code d'avant le correctif (541b4bdd) : un bulletin sans
# jour d'activité partielle au calendrier garde son empreinte au bit près, il ne
# passe pas « à recalculer » au déploiement. La retenue saisie à la main y
# figure : sans jour au calendrier, c'est elle qui compte.

EMPREINTES_D_AVANT = {
    "heures": "669884bdbd8869a358814b30d3f38861decd321821cd1a3c4160163fbdd9546a",
    "forfait_jours": "0cdc6d0d8da8f891d73764d1e166e11dd7d8eb2aee9e02f2a974137f5ef12729",
}


@pytest.mark.parametrize("generateur", ["heures", "forfait_jours"])
def test_sans_activite_partielle_l_empreinte_est_celle_d_avant_le_correctif(
    monkeypatch, calcul, activite_partielle, espion, generateur
):
    base = _BaseAP(
        jours_ap=(), saisies=(PRIME, AP_A_LA_MAIN), forfait=generateur == "forfait_jours"
    )
    stockee = empreinte_stockee(_generer(monkeypatch, generateur, base)["payslip_data"])

    # La retenue à la main passe au calcul telle quelle.
    assert any(p.get("montant") == -50.0 for p in calcul.primes)
    assert stockee == _relue(base, espion.lectures)
    assert stockee == EMPREINTES_D_AVANT[generateur]


# --- Le réglage d'activité partielle de la société ------------------------------
#
# Les deux lignes ne sont plus hachées : le réglage d'où elles sont tirées
# (taux, plancher, plafond, dates) l'est, dans une partie à part de l'empreinte
# complémentaire, les mois qui ont un jour d'activité partielle seulement.


@pytest.mark.parametrize("generateur", ["heures", "forfait_jours"])
def test_un_reglage_d_activite_partielle_modifie_rend_le_bulletin_a_recalculer(
    monkeypatch, calcul, activite_partielle, espion, generateur
):
    base = _BaseAP(forfait=generateur == "forfait_jours")
    _generer(monkeypatch, generateur, base)
    stockees = _parties(espion.lectures)
    assert svc.PARTIE_ACTIVITE_PARTIELLE in stockees

    for cle, valeur in (("taux_indemnite", 70.0), ("plafond_horaire", 30.0), ("date_fin", "2026-09-05")):
        actuelles = _parties(
            espion.lectures, saisies=base.saisies, reglage={**REGLAGE, cle: valeur}
        )
        assert parties_changees(stockees, actuelles) == (svc.PARTIE_ACTIVITE_PARTIELLE,), cle
    assert message_a_recalculer((svc.PARTIE_ACTIVITE_PARTIELLE,)) == (
        "Le réglage d'activité partielle de la société a changé depuis le calcul : "
        "recalculez avant de valider."
    )
    # Une note ou la référence de la décision ne changent aucun montant.
    actuelles = _parties(
        espion.lectures,
        saisies=base.saisies,
        reglage={**REGLAGE, "note": "x", "reference_decision": "D-1", "updated_by": "u"},
    )
    assert parties_changees(stockees, actuelles) == ()


def test_sans_jour_d_activite_partielle_la_partie_n_existe_pas(
    monkeypatch, calcul, activite_partielle, espion
):
    """Un mois sans jour chômé : ni la partie, ni de changement quand le réglage
    bouge — les empreintes complémentaires existantes restent comparables."""
    base = _BaseAP(jours_ap=())
    _generer(monkeypatch, "heures", base)
    stockees = _parties(espion.lectures)
    assert svc.PARTIE_ACTIVITE_PARTIELLE not in stockees
    assert stockees == _parties(espion.lectures, reglage=None)
    actuelles = _parties(espion.lectures, reglage={**REGLAGE, "taux_indemnite": 70.0})
    assert parties_changees(stockees, actuelles) == ()


def test_un_bulletin_calcule_avant_la_partie_ne_la_compare_pas(
    monkeypatch, calcul, activite_partielle, espion
):
    base = _BaseAP()
    _generer(monkeypatch, "heures", base)
    stockees = _parties(espion.lectures)
    stockees.pop(svc.PARTIE_ACTIVITE_PARTIELLE)
    actuelles = _parties(espion.lectures, reglage={**REGLAGE, "taux_indemnite": 70.0})
    assert parties_changees(stockees, actuelles) == ()


def test_un_bulletin_valide_ne_suit_pas_le_reglage_d_aujourd_hui():
    """Comme les autres réglages de la société : ceux d'aujourd'hui ne remettent
    pas en cause un bulletin validé."""
    assert svc.PARTIE_ACTIVITE_PARTIELLE in svc._PARTIES_IGNOREES_SI_VALIDE


def test_les_complements_lisent_le_reglage_avec_la_societe():
    """Une seule lecture jointe : la table a sa clé étrangère vers `companies`
    (migration 20261116200000_activite_partielle.sql)."""
    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    assert "company_activite_partielle(*)" in q._SOCIETE_JOINTE
