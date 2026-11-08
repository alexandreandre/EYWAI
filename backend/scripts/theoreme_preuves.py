"""Ce qui rend le test du théorème capable de rougir : le bilan, les salariés à jouer.

Sans effet à l'import (pas de piège, pas de base) : les tests unitaires le lisent
tel quel. Le script `theoreme_correction_a_la_main.py` s'en sert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    COTI_IDS_AU_MONTANT,
    code_de_ligne_de_cotisation,
    numeroter,
)
from app.modules.payslips.domain.anomalies_bulletin import _taux_proportionnel
from app.shared.domain.employment_rules import payslip_employment_period_block_reason


@dataclass(frozen=True)
class Bilan:
    joues: int
    sautes: int
    echecs: int

    @property
    def code(self) -> int:
        """1 si un cas échoue, ou si rien n'a été joué : un test à vide n'est pas vert."""
        return 1 if self.echecs or not self.joues else 0

    @property
    def phrase(self) -> str:
        return f"{self.joues} cas joué(s), {self.sautes} sauté(s), {self.echecs} échec(s)" + (
            "" if self.joues else " — 0 cas : RIEN N'A ÉTÉ PROUVÉ"
        )


def bilan(rapport: Iterable[Mapping[str, Any]]) -> Bilan:
    cas = list(rapport)
    sautes = sum(1 for c in cas if c.get("saute"))
    return Bilan(joues=len(cas) - sautes, sautes=sautes, echecs=sum(1 for c in cas if not c.get("ok")))


def salaries_a_jouer(employes: Iterable[dict[str, Any]], year: int, month: int) -> list[dict[str, Any]]:
    """Les salariés présents dans le mois, lus sur la fiche : un mois sans bulletin se joue aussi."""
    return [e for e in employes if payslip_employment_period_block_reason(e, year, month) is None]


#: Les gains dont une part sort du net imposable (heures exonérées) ou du net
#: à payer (avantage en nature) : l'identité net / imposable ne s'applique pas.
_FAMILLES_HORS_IDENTITE = frozenset(
    {
        "brut:heures_sup",
        "brut:hs_structurelles",
        "brut:heures_complementaires",
        "brut:reduction_hs_absence",
        "brut:reduction_hs_evenement_familial",
        "brut:avantages_en_nature",
    }
)
_TOLERANCE = 0.021
_FAMILLE_REDUCTION = "cotisation:reduction_generale"


def _f(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _synthese(data: Mapping[str, Any]) -> Mapping[str, Any]:
    return data.get("synthese_net") or {}


def _impot(data: Mapping[str, Any]) -> Mapping[str, Any]:
    return _synthese(data).get("impot_prelevement_a_la_source") or {}


def _cotisations(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        ligne
        for rubrique in data.get("cotisations_officielles") or []
        if isinstance(rubrique, Mapping)
        for ligne in rubrique.get("lignes") or []
        if isinstance(ligne, Mapping)
    ]


def _par_code(data: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    lignes = _cotisations(data)
    codes = numeroter(code_de_ligne_de_cotisation(ligne) for ligne in lignes)
    return {code: ligne for code, ligne in zip(codes, lignes) if code}


def _proportionnelle(ligne: Mapping[str, Any]) -> bool:
    return (
        not ligne.get("correction")
        and not ligne.get("regularisation")
        and str(ligne.get("coti_id") or "") not in COTI_IDS_AU_MONTANT
        and _taux_proportionnel(dict(ligne))
    )


def _cotisations_base_fois_taux(data: Mapping[str, Any]) -> bool:
    for ligne in _cotisations(data):
        if not _proportionnelle(ligne):
            continue
        for taux, montant in (("taux_salarial", "montant_salarial"), ("taux_patronal", "montant_patronal")):
            if ligne.get(taux) is None:
                continue
            if abs(round(_f(ligne.get("base")) * _f(ligne.get(taux)), 2) - _f(ligne.get(montant))) > _TOLERANCE:
                return False
    return True


def _impot_base_fois_taux(data: Mapping[str, Any]) -> bool | None:
    impot = _impot(data)
    if impot.get("base") is None or impot.get("montant") is None:
        return None
    return abs(round(_f(impot["base"]) * _f(impot.get("taux")) / 100.0, 2) - _f(impot["montant"])) <= _TOLERANCE


def _cotisations_suivent(data0: Mapping[str, Any], data1: Mapping[str, Any]) -> bool | None:
    """Une cotisation assise sur tout le brut bouge quand le brut bouge."""
    brut0 = _f(data0.get("salaire_brut"))
    apres = _par_code(data1)
    concernees = [
        (ligne, apres[code])
        for code, ligne in _par_code(data0).items()
        if code in apres and _proportionnelle(ligne) and abs(_f(ligne.get("base")) - brut0) < 0.01
    ]
    if not concernees:
        return None
    return all(abs(_f(l1.get("base")) - _f(l0.get("base"))) > 0.005 for l0, l1 in concernees)


def _non_deductible(data: Mapping[str, Any]) -> float:
    return sum(_f(l.get("montant_salarial")) for l in _cotisations(data) if l.get("coti_id") in ("csg_non_deductible", "crds"))


def _net_imposable_suit(data0: Mapping[str, Any], data1: Mapping[str, Any]) -> bool | None:
    """Le net imposable bouge comme net + impôt + CSG non déductible et CRDS."""
    s0, s1 = _synthese(data0), _synthese(data1)
    if s0.get("net_imposable") is None or s1.get("net_imposable") is None:
        return None
    attendu = (
        _f(data1.get("net_a_payer")) - _f(data0.get("net_a_payer"))
        + _f(_impot(data1).get("montant")) - _f(_impot(data0).get("montant"))
        + _non_deductible(data1) - _non_deductible(data0)
    )
    return abs(_f(s1["net_imposable"]) - _f(s0["net_imposable"]) - attendu) <= _TOLERANCE + 0.01


def _base_impot_suit(data0: Mapping[str, Any], data1: Mapping[str, Any]) -> bool | None:
    if _impot(data0).get("base") is None or _impot(data1).get("base") is None:
        return None
    return (
        abs(
            (_f(_impot(data1)["base"]) - _f(_impot(data0)["base"]))
            - (_f(_synthese(data1).get("net_imposable")) - _f(_synthese(data0).get("net_imposable")))
        )
        <= _TOLERANCE
    )


def _net_social_suit(data0: Mapping[str, Any], data1: Mapping[str, Any]) -> bool | None:
    s0, s1 = _synthese(data0), _synthese(data1)
    if s0.get("montant_net_social") is None or s1.get("montant_net_social") is None:
        return None
    return abs(_f(s1["montant_net_social"]) - _f(s0["montant_net_social"])) > 0.005


def _reduction_suit(data0: Mapping[str, Any], data1: Mapping[str, Any]) -> bool | None:
    avant = _par_code(data0).get(_FAMILLE_REDUCTION)
    apres = _par_code(data1).get(_FAMILLE_REDUCTION)
    if avant is None or apres is None or abs(_f(avant.get("montant_patronal"))) < 0.005 or apres.get("correction"):
        return None
    return abs(_f(apres.get("montant_patronal")) - _f(avant.get("montant_patronal"))) > 0.005


def constats_independants(
    data0: Mapping[str, Any], data1: Mapping[str, Any], *, bloc: str, famille: str
) -> dict[str, bool | None]:
    """Ce que le bulletin corrigé doit valoir, recalculé hors du moteur.

    None : la vérification ne s'applique pas à ce bulletin (rien à comparer) ;
    seul False est un échec.
    """
    constats: dict[str, bool | None] = {
        "cotisations_base_fois_taux": _cotisations_base_fois_taux(data1),
        "impot_base_fois_taux": _impot_base_fois_taux(data1),
    }
    if bloc != BLOC_BRUT or abs(_f(data1.get("salaire_brut")) - _f(data0.get("salaire_brut"))) < 0.01:
        return constats
    constats["cotisations_suivent_le_brut"] = _cotisations_suivent(data0, data1)
    constats["net_social_suit"] = _net_social_suit(data0, data1)
    constats["reduction_suit"] = _reduction_suit(data0, data1)
    exonere = any(_synthese(data1).get(cle) for cle in ("exoneration_ir_apprenti", "exoneration_ir_stagiaire"))
    if famille not in _FAMILLES_HORS_IDENTITE and not exonere:
        constats["net_imposable_suit"] = _net_imposable_suit(data0, data1)
        constats["base_impot_suit"] = _base_impot_suit(data0, data1)
    return constats


def compta_garde_les_patronales(ligne_od: Mapping[str, Any]) -> bool:
    """Le détail que lit l'OD porte toutes les charges patronales du bulletin."""
    detail = sum(_f(c.get("montant_patronal")) for c in ligne_od.get("cotisations_detail") or [])
    return abs(detail - _f(ligne_od.get("cotisations_patronales"))) <= _TOLERANCE


#: Ce que chaque cumul doit devenir d'un mois sur l'autre (cumul de M+1 − valeur de M+1 = cumul de M).
def cumuls_du_mois_suivant_a_verifier(data: Mapping[str, Any]) -> dict[str, float]:
    return {
        "brut_total": _f(data.get("salaire_brut")),
        "net_imposable": _f(_synthese(data).get("net_imposable")),
        "impot_preleve_a_la_source": _f(_impot(data).get("montant")),
    }
