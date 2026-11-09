"""Ce qui rend le test du théorème capable de rougir : le bilan, les salariés à jouer.

Sans effet à l'import (pas de piège, pas de base) : les tests unitaires le lisent
tel quel. Le script `theoreme_correction_a_la_main.py` s'en sert.
"""

from __future__ import annotations

import re
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
from verification_rgdu.oracle import Parametres, reduction_cumulee
from verification_rgdu.oracle_smic import SMIC_H_2026


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
    cas = [c for c in rapport if not c.get("information")]
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
    """Une ligne base × taux. Sans aucun taux (exonération JEI), rien à rejouer : la base y est un affichage."""
    return (
        not ligne.get("correction")
        and not ligne.get("regularisation")
        and str(ligne.get("coti_id") or "") not in COTI_IDS_AU_MONTANT
        and (ligne.get("taux_salarial") is not None or ligne.get("taux_patronal") is not None)
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


def _reduction_suit(data0: Mapping[str, Any], data1: Mapping[str, Any], res0: Mapping[str, Any] | None = None, res1: Mapping[str, Any] | None = None) -> bool | None:
    """La réduction générale bouge comme l'oracle (formule écrite depuis les textes, hors du moteur).

    Attendu : f(cumul brut, cumul SMIC) après moins f avant, sur les cumuls des
    deux calculs. Le mouvement attendu peut être nul (coefficient qui saute un
    palier ou qui plafonne à Tmax) : seul un écart à l'oracle est un échec.
    """
    avant = _par_code(data0).get(_FAMILLE_REDUCTION)
    apres = _par_code(data1).get(_FAMILLE_REDUCTION)
    if avant is None or apres is None or abs(_f(avant.get("montant_patronal"))) < 0.005 or apres.get("correction"):
        return None
    mouvement = _f(apres.get("montant_patronal")) - _f(avant.get("montant_patronal"))
    if res0 is None or res1 is None:
        return abs(mouvement) > 0.005
    attendus = _mouvements_attendus_de_la_reduction(res0, res1)
    if attendus is None:
        return None
    return any(abs(mouvement - attendu) <= _TOLERANCE for attendu in attendus)


def _mouvements_attendus_de_la_reduction(res0: Mapping[str, Any], res1: Mapping[str, Any]) -> list[float] | None:
    """Mouvement de la réduction selon l'oracle, avec les deux taux de Tdelta (moins de 50 / 50 et plus)."""

    def cumuls(res: Mapping[str, Any]) -> Mapping[str, Any]:
        return ((res.get("cumuls") or {}).get("cumuls") or {}) if isinstance(res, Mapping) else {}

    def brut(c: Mapping[str, Any]) -> float:
        valeur = c.get("brut_annee_civile")
        return _f(valeur if valeur is not None else c.get("brut_total")) - _f(c.get("brut_hors_reduction_generale"))

    c0, c1 = cumuls(res0), cumuls(res1)
    heures0 = _f(c0.get("heures_remunerees")) - _f(c0.get("heures_hors_reduction_generale"))
    heures1 = _f(c1.get("heures_remunerees")) - _f(c1.get("heures_hors_reduction_generale"))
    if brut(c0) <= 0 or heures0 <= 0:
        return None
    resultats = []
    for tdelta in (0.3781, 0.3821):
        prm = Parametres(tdelta=tdelta)
        # La réduction est négative sur le bulletin : le mouvement l'est quand le brut baisse.
        resultats.append(
            -round(
                reduction_cumulee(brut(c1), round(SMIC_H_2026 * heures1, 2), prm)
                - reduction_cumulee(brut(c0), round(SMIC_H_2026 * heures0, 2), prm),
                2,
            )
        )
    return resultats


#: Abattement d'assiette de la CSG et de la CRDS (CSS L136-1-1) tant que le brut reste sous 4 PASS.
_ABATTEMENT_CSG = 0.9825
_CSG_CRDS = frozenset({"csg_deductible", "csg_non_deductible", "crds"})
#: Plafond mensuel de la Sécurité sociale 2026 (48 060 € / 12).
_PLAFOND_MENSUEL = 4005.0


#: Parts patronales ajoutées à l'assiette de la CSG (prévoyance, retraite supplémentaire) : leur mouvement la suit.
_PATRONAL_DANS_LA_CSG = frozenset({"prevoyance_cadre", "prevoyance_non_cadre", "retraite_sup"})


#: La CSG des heures supplémentaires exonérées (« sur HS ») a sa propre assiette.
_CSG_DES_HEURES = re.compile(r"\bhs\b|heures")


def _mouvement_du_patronal_dans_la_csg(data0: Mapping[str, Any], data1: Mapping[str, Any]) -> float:
    def total(data: Mapping[str, Any]) -> float:
        return sum(_f(l.get("montant_patronal")) for l in _cotisations(data) if l.get("coti_id") in _PATRONAL_DANS_LA_CSG)

    return total(data1) - total(data0)


def _base_attendue(
    ligne: Mapping[str, Any], brut0: float, brut1: float, famille: str, delta_patronal_csg: float = 0.0
) -> float | None:
    """La base d'une cotisation après le mouvement du brut, sans le moteur. None : non modélisée."""
    b0 = _f(ligne.get("base"))
    if abs(b0 - brut0) <= 0.01:
        # Au plafond (ou proratisée à une entrée en cours de mois) : la ligne n'est plus sur le brut.
        return brut1 if brut1 <= _PLAFOND_MENSUEL else None
    # Sous 90 % du brut, l'assiette n'est pas le brut abattu (apprenti, régime particulier) : non modélisée.
    if ligne.get("coti_id") in _CSG_CRDS and b0 > 0.9 * brut0 and not _CSG_DES_HEURES.search(str(ligne.get("libelle") or "").lower()):
        if famille in _FAMILLES_HORS_IDENTITE or brut1 > 4 * _PLAFOND_MENSUEL:
            return None
        return round(b0 + _ABATTEMENT_CSG * (brut1 - brut0) + delta_patronal_csg, 2)
    return None


def cotisations_attendues(
    data0: Mapping[str, Any], data1: Mapping[str, Any], delta_brut: float, famille: str
) -> dict[str, Any]:
    """Chaque cotisation modélisée contre sa valeur attendue : le taux du bulletin de départ, le brut attendu.

    Sortie : `cotisations_attendues` (None si aucune ligne modélisée), les
    écarts, et les mouvements attendus des parts salariale, déductible et totale.
    """
    brut0 = _f(data0.get("salaire_brut"))
    brut1 = brut0 + delta_brut
    apres = _par_code(data1)
    ecarts: list[str] = []
    verifiees = 0
    delta_salarial = 0.0
    delta_deductible = 0.0
    delta_patronal_csg = _mouvement_du_patronal_dans_la_csg(data0, data1)
    for code, ligne in _par_code(data0).items():
        suivante = apres.get(code)
        if suivante is None:
            # Ligne retirée au calcul (base tombée à zéro) : tout son salarial s'en va.
            delta_salarial -= _f(ligne.get("montant_salarial"))
            if ligne.get("coti_id") not in ("csg_non_deductible", "crds"):
                delta_deductible -= _f(ligne.get("montant_salarial"))
            continue
        mouvement_moteur = _f(suivante.get("montant_salarial")) - _f(ligne.get("montant_salarial"))
        b1 = _base_attendue(ligne, brut0, brut1, famille, delta_patronal_csg) if _proportionnelle(ligne) else None
        memes_taux = all(
            ligne.get(t) is None or (suivante.get(t) is not None and abs(_f(ligne.get(t)) - _f(suivante.get(t))) < 1e-9)
            for t in ("taux_salarial", "taux_patronal")
        )
        if b1 is None or not memes_taux:
            # Taux qui bascule à un seuil, ligne non modélisée : le mouvement du moteur compte, sans être vérifié.
            delta_salarial += mouvement_moteur
            if ligne.get("coti_id") not in ("csg_non_deductible", "crds"):
                delta_deductible += mouvement_moteur
            continue
        verifiees += 1
        if abs(_f(suivante.get("base")) - b1) > _TOLERANCE:
            ecarts.append(f"{code}: base {suivante.get('base')} au lieu de {b1}")
            continue
        for taux, montant in (("taux_salarial", "montant_salarial"), ("taux_patronal", "montant_patronal")):
            if ligne.get(taux) is None:
                continue
            voulu = round(b1 * _f(ligne.get(taux)), 2)
            if abs(_f(suivante.get(montant)) - voulu) > _TOLERANCE:
                ecarts.append(f"{code}: {montant} {suivante.get(montant)} au lieu de {voulu}")
        if ligne.get("taux_salarial") is not None:
            attendu = round(b1 * _f(ligne.get("taux_salarial")), 2) - _f(ligne.get("montant_salarial"))
            delta_salarial += attendu
            if ligne.get("coti_id") not in ("csg_non_deductible", "crds"):
                delta_deductible += attendu
    return {
        "cotisations_attendues": (not ecarts) if verifiees else None,
        "cotisations_ecarts": ecarts,
        "delta_salarial_attendu": round(delta_salarial, 2),
        "delta_deductible_attendu": round(delta_deductible, 2),
    }


def attendus_apres_un_gain(
    data0: Mapping[str, Any],
    data1: Mapping[str, Any],
    delta_ligne: float,
    *,
    famille: str,
    delta_indemnites: float = 0.0,
) -> dict[str, Any]:
    """Le bulletin attendu, calculé à part du mouvement voulu sur la ligne : brut, cotisations, net imposable, impôt, net.

    `delta_indemnites` : ce que le moteur ajoute par construction (précarité,
    congés payés de fin de contrat, sur le gain corrigé). Ces lignes-là ne sont
    pas recalculées ici.
    """
    delta_brut = round(delta_ligne + delta_indemnites, 2)
    constats: dict[str, Any] = {
        "brut_attendu": abs(_f(data1.get("salaire_brut")) - round(_f(data0.get("salaire_brut")) + delta_brut, 2)) <= _TOLERANCE,
    }
    attendus = cotisations_attendues(data0, data1, delta_brut, famille)
    constats["cotisations_attendues"] = attendus["cotisations_attendues"]
    if attendus["cotisations_ecarts"]:
        constats["cotisations_ecarts"] = attendus["cotisations_ecarts"][:5]
    if famille == "brut:avantages_en_nature":
        # L'avantage en nature porte cotisations et impôt, jamais d'argent en plus :
        # le net ne bouge que de ces retenues (constat L1 de la relecture 6).
        delta_impot = _f(_impot(data1).get("montant")) - _f(_impot(data0).get("montant"))
        constats["avantage_non_paye_en_argent"] = (
            abs(_f(data1.get("net_a_payer")) - _f(data0.get("net_a_payer")) + attendus["delta_salarial_attendu"] + delta_impot) <= _TOLERANCE + 0.02
        )
    hs_ou_exo = famille in _FAMILLES_HORS_IDENTITE or any(
        _synthese(data1).get(cle) for cle in ("exoneration_ir_apprenti", "exoneration_ir_stagiaire")
    )
    s0, s1 = _synthese(data0), _synthese(data1)
    if hs_ou_exo or s0.get("net_imposable") is None or s1.get("net_imposable") is None:
        constats["net_imposable_attendu"] = None
        constats["impot_attendu"] = None
        constats["net_attendu"] = None
        return constats
    net_imposable = round(_f(s0["net_imposable"]) + delta_brut - attendus["delta_deductible_attendu"], 2)
    constats["net_imposable_attendu"] = abs(_f(s1["net_imposable"]) - net_imposable) <= _TOLERANCE + 0.01
    impot0, impot1 = _impot(data0), _impot(data1)
    delta_impot = 0.0
    if impot0.get("taux") is not None and impot1.get("taux") is not None and abs(_f(impot0["taux"]) - _f(impot1["taux"])) < 1e-9:
        attendu_impot = round(net_imposable * _f(impot0["taux"]) / 100.0, 2)
        constats["impot_attendu"] = abs(_f(impot1.get("montant")) - attendu_impot) <= _TOLERANCE + 0.01
        delta_impot = attendu_impot - _f(impot0.get("montant"))
    else:
        constats["impot_attendu"] = None  # Taux qui change avec la base (grille) : non recalculé ici.
        delta_impot = _f(impot1.get("montant")) - _f(impot0.get("montant"))
    constats["net_attendu"] = (
        abs(
            _f(data1.get("net_a_payer"))
            - round(_f(data0.get("net_a_payer")) + delta_brut - attendus["delta_salarial_attendu"] - delta_impot, 2)
        )
        <= _TOLERANCE + 0.02
    )
    return constats


def constats_independants(
    data0: Mapping[str, Any],
    data1: Mapping[str, Any],
    *,
    bloc: str,
    famille: str,
    res0: Mapping[str, Any] | None = None,
    res1: Mapping[str, Any] | None = None,
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
    constats["reduction_suit"] = _reduction_suit(data0, data1, res0, res1)
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
