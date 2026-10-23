"""Restaurer une version sans heures déclarées dont la ligne d'heures sup était corrigée à la main.

La restauration déclarait la quantité corrigée (8 h) comme heures du mois, et
la correction revenait en plus : le bulletin disait ensuite que Martine avait
calculé 8 h, pour 5 h au planning. Les heures déclarées se lisent désormais
sur la valeur calculée par Martine ; la correction revient comme correction.
Montants, cotisations, net et ce qui alimente les cumuls ne bougent pas d'un
centime. Une version sans ligne corrigée se restaure exactement comme avant.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
)
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, code_de_ligne
from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    JournalDesCorrections,
)
from app.modules.payslips.domain.corrections import (
    apercu_de_restauration,
    corrections_pour_revenir,
)
from app.modules.payslips.domain.heures_sup import quantites_heures_sup_conjoncturelles
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))
CODE_HS25 = "brut:heures_sup:25"


def _calendrier(hs25: float = 5.0) -> list[dict]:
    cal = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "travail_base", "heures": 7.0})
        jour = date.fromordinal(jour.toordinal() + 1)
    if hs25:
        cal.append({"date_complete": "2026-01-15", "type": "travail_hs25", "heures": hs25})
    return cal


def _calculer(declarees=None, corrections=(), hs25_planning: float = 5.0) -> dict:
    """Le bulletin qu'un recalcul donnerait : brut, cotisations, net."""
    contexte = build_test_contexte()
    contexte.year = 2026
    if declarees is not None:
        contexte.contrat["saisie_du_mois"] = {
            "heures_supplementaires_conjoncturelles": declarees[0],
            "heures_supplementaires_conjoncturelles_50": declarees[1],
            "heures_sup_declarees_au_bulletin": True,
        }
    if corrections:
        # Une correction qui revient est écrite comme saisie du mois : elle a alors son identifiant.
        contexte.corrections_du_mois = JournalDesCorrections(
            [c if c.saisie_id else replace(c, saisie_id=f"nouvelle-{i}") for i, c in enumerate(corrections)]
        )
    brut = calculer_salaire_brut(contexte, _calendrier(hs25_planning), *JANVIER, [])
    total_brut = brut["salaire_brut_total"]
    hs, ths = brut["remuneration_brute_heures_supp"], brut["total_heures_supp"]
    lignes, total_sal = calculer_cotisations(contexte, total_brut, hs, ths)
    reduction = calculer_reduction_generale(contexte, total_brut, (contexte.duree_hebdo_contrat * 52) / 12)
    if reduction:
        lignes.append(reduction)
    nets = calculer_net_et_impot(contexte, total_brut, lignes, total_sal, [], hs, 0.0, [])
    return {"brut": brut, "cotisations": lignes, "nets": nets}


def _montants(bulletin: dict) -> dict:
    """Tout ce qui se paie ou se cumule, au centime ; sans la trace de la correction."""
    brut = bulletin["brut"]
    lignes = [
        {k: (round(v, 2) if isinstance(v, float) else v) for k, v in l.items() if k not in ("valeur_calculee", "correction")}
        for l in brut["lignes_composants_brut"]
    ]
    cotisations = [
        (l.get("libelle"), round(l.get("montant_salarial") or 0.0, 2), round(l.get("montant_patronal") or 0.0, 2))
        for l in bulletin["cotisations"]
    ]
    nombres = {k: round(v, 2) for k, v in brut.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    nets = {k: round(v, 2) for k, v in bulletin["nets"].items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {"lignes": lignes, "cotisations": cotisations, "brut": nombres, "nets": nets}


def _ligne_hs25(bulletin: dict) -> dict:
    return next(l for l in bulletin["brut"]["lignes_composants_brut"] if code_de_ligne(BLOC_BRUT, l) == CODE_HS25)


def _version_corrigee() -> dict:
    """Une version sans heures déclarées : 5 h au planning, ligne corrigée à 8 h."""
    libelle = _ligne_hs25(_calculer())["libelle"]
    correction = CorrectionDeLigne(ligne=CODE_HS25, libelle=libelle, motif="Heures confirmées", base=8.0, saisie_id="c1")
    calcule = _calculer(corrections=(correction,))
    assert _ligne_hs25(calcule)["quantite"] == 8.0 and _ligne_hs25(calcule)["valeur_calculee"]["quantite"] == 5.0
    return {"calcul_du_brut": calcule["brut"]["lignes_composants_brut"]}


def _heures_comme_avant(courant, cible):
    """La règle d'avant le correctif, pour une version sans heures déclarées."""
    heures_cible = quantites_heures_sup_conjoncturelles(cible)
    heures_courant = quantites_heures_sup_conjoncturelles(courant)
    if all(abs(a - b) <= 0.005 for a, b in zip(heures_cible, heures_courant)):
        return None
    return (round(heures_cible[0], 2), round(heures_cible[1], 2))


class TestVersionALigneDHeuresCorrigee:
    def test_les_heures_se_lisent_sur_la_valeur_de_martine_et_la_correction_revient(self):
        version = _version_corrigee()
        restauration = corrections_pour_revenir({}, version)
        assert restauration.heures_sup == (5.0, 0.0)
        assert [(c.ligne, c.base) for c in restauration.corrections_ajoutees] == [(CODE_HS25, 8.0)]

    def test_montants_cotisations_net_et_cumuls_restent_ceux_d_aujourd_hui_au_centime(self):
        version = _version_corrigee()
        restauration = corrections_pour_revenir({}, version)
        apres = _calculer(restauration.heures_sup, restauration.corrections_ajoutees)
        avant = _calculer(_heures_comme_avant({}, version), restauration.corrections_ajoutees)
        assert _heures_comme_avant({}, version) == (8.0, 0.0)
        assert _montants(apres) == _montants(avant)
        # Ce qui change : Martine avait calculé 5 h, plus 8 h.
        assert _ligne_hs25(apres)["valeur_calculee"]["quantite"] == 5.0
        assert _ligne_hs25(avant)["valeur_calculee"]["quantite"] == 8.0

    def test_une_version_identique_au_bulletin_n_a_rien_a_restaurer(self):
        version = _version_corrigee()
        assert corrections_pour_revenir(version, version).heures_sup is None

    def test_l_apercu_dit_les_memes_heures_que_la_restauration(self):
        version = _version_corrigee()
        courant = {"calcul_du_brut": _calculer(hs25_planning=0.0)["brut"]["lignes_composants_brut"]}
        restauration = corrections_pour_revenir(courant, version)
        apercu = apercu_de_restauration(courant, version)
        assert restauration.heures_sup == (5.0, 0.0)
        assert apercu["reviennent"][0] == "Heures sup 5 h à 25 % et 0 h à 50 % (au lieu de 0 h et 0 h)"
        assert any("Heures confirmées" in r for r in apercu["reviennent"])


class TestVersionSansLigneCorrigee:
    @pytest.mark.parametrize("hs_version,hs_courant", [(5.0, 0.0), (0.0, 5.0), (5.0, 5.0), (3.0, 6.0)])
    def test_se_restaure_exactement_comme_avant(self, hs_version, hs_courant):
        version = {"calcul_du_brut": _calculer(hs25_planning=hs_version)["brut"]["lignes_composants_brut"]}
        courant = {"calcul_du_brut": _calculer(hs25_planning=hs_courant)["brut"]["lignes_composants_brut"]}
        restauration = corrections_pour_revenir(courant, version)
        assert restauration.heures_sup == _heures_comme_avant(courant, version)
        assert restauration.corrections_ajoutees == () and restauration.corrections_retirees == ()
        if restauration.heures_sup is not None:
            assert _montants(_calculer(restauration.heures_sup)) == _montants(
                _calculer(_heures_comme_avant(courant, version))
            )
