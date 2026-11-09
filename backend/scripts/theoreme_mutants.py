"""Les erreurs injectées dans un bulletin juste : le test du théorème doit les voir (R-180, R-177).

Chaque mutant abîme le résultat d'un calcul exact, comme le ferait un défaut du
moteur, de la DSN ou de l'OD, et nomme les constats du test dont l'un au moins
doit rougir. Aucun mutant ne touche à la base : ils opèrent sur la copie en
mémoire que `theoreme_correction_a_la_main._generer` rend au test.

Une injection sans effet (le salarié n'a pas la ligne visée : pas de réduction
générale chez un JEI, par exemple) n'est pas un échec : elle est comptée à part,
avec sa cause. Une injection qui change le bulletin sans qu'aucun constat rougisse
est un échec du test.

Sans effet à l'import : les tests unitaires le lisent tel quel.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

#: Ce qui change avec le mois pour un mutant : les saisies du calcul, le mois corrigé.
Contexte = Mapping[str, Any]


def _f(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _lignes(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [l for r in data.get("cotisations_officielles") or [] for l in r.get("lignes") or []]


def _reduction(data: Mapping[str, Any]) -> dict[str, Any] | None:
    return next((l for l in _lignes(data) if l.get("coti_id") == "reduction_generale" and not l.get("correction")), None)


def _impot(data: dict[str, Any]) -> dict[str, Any]:
    return (data.get("synthese_net") or {}).get("impot_prelevement_a_la_source") or {}


def _reference(ctx: Contexte) -> dict[str, Any]:
    """Le bulletin sans correction du même salarié et du même mois."""
    return ctx["bulletin_sans_correction"]["payslip_data"]


def _brut_change(res: Mapping[str, Any], ctx: Contexte) -> bool:
    return abs(_f(res["payslip_data"].get("salaire_brut")) - _f(_reference(ctx).get("salaire_brut"))) >= 0.01


def _e2(res: dict[str, Any], ctx: Contexte) -> None:
    if ctx["saisies"]:
        res["payslip_data"]["net_a_payer"] = round(_f(res["payslip_data"].get("net_a_payer")) + 7.77, 2)


def _e3(res: dict[str, Any], ctx: Contexte) -> None:
    res["payslip_data"]["net_a_payer"] = round(_f(res["payslip_data"].get("net_a_payer")) + 100.0, 2)


def _e4(res: dict[str, Any], ctx: Contexte) -> None:
    """Les cotisations ne suivent pas le gain corrigé : celles d'avant, totaux et net avec."""
    if not _brut_change(res, ctx):
        return
    data, ref = res["payslip_data"], _reference(ctx)
    par_code = {(l.get("coti_id"), l.get("libelle")): l for l in _lignes(ref)}
    delta_salarial = 0.0
    for ligne in _lignes(data):
        ancienne = par_code.get((ligne.get("coti_id"), ligne.get("libelle")))
        if ancienne is None or ligne.get("correction") or ligne.get("regularisation"):
            continue
        delta_salarial += _f(ligne.get("montant_salarial")) - _f(ancienne.get("montant_salarial"))
        for cle in ("base", "montant_salarial", "montant_patronal"):
            ligne[cle] = ancienne.get(cle)
    structure = data.get("structure_cotisations") or {}
    structure["total_salarial"] = round(_f(structure.get("total_salarial")) - delta_salarial, 2)
    data["net_a_payer"] = round(_f(data.get("net_a_payer")) + delta_salarial, 2)


def _e5(res: dict[str, Any], ctx: Contexte) -> None:
    """La réduction générale ne suit pas le gain corrigé."""
    if not _brut_change(res, ctx):
        return
    data = res["payslip_data"]
    ligne, ancienne = _reduction(data), _reduction(_reference(ctx))
    if ligne is None or ancienne is None:
        return
    ligne["montant_patronal"] = ancienne.get("montant_patronal")


def _e6(res: dict[str, Any], ctx: Contexte) -> None:
    """L'impôt ne suit pas : montant d'avant, net recomposé."""
    if not _brut_change(res, ctx):
        return
    data = res["payslip_data"]
    avant = _f(_impot(_reference(ctx)).get("montant"))
    ecart = _f(_impot(data).get("montant")) - avant
    _impot(data)["montant"] = avant
    data["net_a_payer"] = round(_f(data.get("net_a_payer")) + ecart, 2)


def _e7(res: dict[str, Any], ctx: Contexte) -> None:
    """Le net imposable ne suit pas."""
    if not _brut_change(res, ctx):
        return
    res["payslip_data"]["synthese_net"]["net_imposable"] = (_reference(ctx).get("synthese_net") or {}).get("net_imposable")


def _e8(res: dict[str, Any], ctx: Contexte) -> None:
    """Le mois suivant oublie tous les cumuls, sauf le brut."""
    if not ctx.get("mois_suivant"):
        return
    data, cumuls = res["payslip_data"], res["cumuls"]["cumuls"]
    cumuls["net_imposable"] = _f((data.get("synthese_net") or {}).get("net_imposable"))
    cumuls["impot_preleve_a_la_source"] = _f(_impot(data).get("montant"))


def _e11(res: dict[str, Any], ctx: Contexte) -> None:
    """Le montant net social ne suit pas."""
    if not _brut_change(res, ctx):
        return
    synthese = res["payslip_data"].get("synthese_net") or {}
    if "montant_net_social" in synthese:
        synthese["montant_net_social"] = (_reference(ctx).get("synthese_net") or {}).get("montant_net_social")


def _e12(res: dict[str, Any], ctx: Contexte) -> None:
    """La ligne corrigée est perdue au rejeu : la saisie n'a plus d'effet."""
    if ctx["saisies"]:
        for cle in ("payslip_data", "cumuls"):
            res[cle] = ctx["bulletin_sans_correction"][cle]


def _cumul_oublie(cle: str) -> Callable[[dict[str, Any], Contexte], None]:
    def muter(res: dict[str, Any], ctx: Contexte) -> None:
        if ctx["saisies"] and not ctx.get("mois_suivant"):
            cumuls = res["cumuls"]["cumuls"]
            reference = ctx["bulletin_sans_correction"]["cumuls"]["cumuls"]
            if cle in cumuls and cle in reference:
                cumuls[cle] = reference[cle]

    return muter


def _doubler_premier_nombre(valeur: Any) -> bool:
    """Double le premier nombre non nul trouvé dans un dict ou une liste, sur place."""
    if isinstance(valeur, dict):
        elements = valeur.items()
    elif isinstance(valeur, list):
        elements = enumerate(valeur)
    else:
        return False
    for cle, element in elements:
        if isinstance(element, (int, float)) and not isinstance(element, bool) and element:
            valeur[cle] = round(float(element) * 2, 2)
            return True
        if _doubler_premier_nombre(element):
            return True
    return False


def _e18(res: dict[str, Any], ctx: Contexte) -> None:
    """Un compteur de congés est crédité deux fois."""
    if ctx["saisies"]:
        _doubler_premier_nombre((res["payslip_data"].get("pied_de_page") or {}).get("solde_conges"))


def _e21(res: dict[str, Any], ctx: Contexte) -> None:
    """La correction se pose sur le premier doublon, pas sur celui qu'on visait."""
    if not ctx["saisies"]:
        return
    lignes = _lignes(res["payslip_data"])
    for rang, ligne in enumerate(lignes):
        if ligne.get("correction"):
            jumelle = next((l for l in lignes[:rang] if l.get("coti_id") == ligne.get("coti_id") and l.get("libelle") == ligne.get("libelle")), None)
            if jumelle is not None:
                jumelle["correction"], ligne["correction"] = ligne["correction"], None
            return


def _e1_dsn(data: dict[str, Any]) -> dict[str, Any]:
    """La DSN ignore les cotisations corrigées : elle lit le bulletin sans leurs corrections."""
    copie = {**data, "cotisations_officielles": []}
    for rubrique in data.get("cotisations_officielles") or []:
        lignes = [l for l in rubrique.get("lignes") or [] if not (l.get("correction") or l.get("regularisation"))]
        copie["cotisations_officielles"].append({**rubrique, "lignes": lignes})
    return copie


def _e9_bases(bases: dict[str, float], ctx: Contexte) -> dict[str, float]:
    return {**bases, "03": round(bases.get("03", 0.0) + 100.0, 2)} if ctx["saisies"] and "03" in bases else bases


def _e14_bases(bases: dict[str, float], ctx: Contexte) -> dict[str, float]:
    """L'assiette de la CSG en DSN double quand la CSG est corrigée (constat A1 de la relecture 6)."""
    if not ctx["saisies"] or not any("csg" in str(s.get("correction_ligne") or {}).lower() for s in ctx["saisies"]):
        return bases
    return {**bases, "04": round(bases.get("04", 0.0) * 2, 2)} if "04" in bases else bases


def _e10_od(ligne: dict[str, Any]) -> dict[str, Any]:
    return {**ligne, "cotisations_detail": [{**c, "montant_patronal": 0.0} for c in ligne.get("cotisations_detail") or []]}


def _e17_od(ligne: dict[str, Any]) -> dict[str, Any]:
    elements = list(ligne.get("elements_hors_brut") or [])
    if not elements:
        return ligne
    return {**ligne, "elements_hors_brut": [*elements, dict(elements[0])]}


@dataclass(frozen=True)
class Mutant:
    nom: str
    quoi: str
    #: L'un au moins de ces constats doit rougir si l'injection a un effet.
    constats: frozenset[str]
    bulletin: Callable[[dict[str, Any], Contexte], None] | None = None
    donnees_dsn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    bases_dsn: Callable[[dict[str, float], Contexte], dict[str, float]] | None = None
    ligne_od: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    #: Pourquoi l'injection peut rester sans effet sur un salarié : ce qu'il lui manque.
    sans_effet_si: str = ""


def _mutant(nom: str, quoi: str, *constats: str, sans_effet_si: str = "", **effets: Any) -> Mutant:
    return Mutant(nom=nom, quoi=quoi, constats=frozenset(constats), sans_effet_si=sans_effet_si, **effets)


MUTANTS: tuple[Mutant, ...] = (
    _mutant("E1", "la DSN ignore la cotisation corrigée", "dsn", donnees_dsn=_e1_dsn),
    _mutant("E2", "net faux de 7,77 € quand il y a une correction", "residu", "residu_nul", bulletin=_e2),
    _mutant("E3", "net faux de 100 € sur tous les bulletins", "residu_nul", "revue_sans_alerte", bulletin=_e3),
    _mutant("E4", "les cotisations ne suivent pas le gain corrigé", "cotisations_attendues", "cotisations_suivent_le_brut", bulletin=_e4),
    _mutant("E5", "la réduction générale ne suit pas", "reduction_suit", bulletin=_e5, sans_effet_si="ce bulletin n'a pas de réduction générale (JEI ou exonéré)"),
    _mutant("E6", "l'impôt ne suit pas", "impot_attendu", "impot_base_fois_taux", "net_attendu", bulletin=_e6, sans_effet_si="impôt nul sur ce bulletin (taux à 0 %)"),
    _mutant("E7", "le net imposable ne suit pas", "net_imposable_attendu", "net_imposable_suit", "base_impot_suit", bulletin=_e7),
    _mutant("E8", "le mois suivant oublie les cumuls sauf le brut", "mois_suivant", bulletin=_e8),
    _mutant("E9", "assiette DSN fausse de 100 €", "dsn_assiettes", bases_dsn=_e9_bases),
    _mutant("E10", "la compta perd les charges patronales", "compta_patronales", ligne_od=_e10_od),
    _mutant("E11", "le montant net social ne suit pas", "net_social_suit", bulletin=_e11),
    _mutant("E12", "la ligne corrigée est perdue au rejeu", "valeur_posee", bulletin=_e12),
    _mutant("E13a", "cumul du net imposable oublié", "cumul_net_imposable", bulletin=_cumul_oublie("net_imposable")),
    _mutant("E13b", "cumul de l'impôt oublié", "cumul_impot", bulletin=_cumul_oublie("impot_preleve_a_la_source")),
    _mutant("E13c", "cumul de brut de l'année civile oublié", "cumul_brut_annee", bulletin=_cumul_oublie("brut_annee_civile")),
    _mutant("E13d", "cumul de la réduction générale oublié", "cumul_reduction", bulletin=_cumul_oublie("reduction_generale_patronale"), sans_effet_si="pas de cumul de réduction générale sur ce salarié"),
    _mutant("E14", "assiette de la CSG doublée en DSN (A1)", "dsn_assiettes", bases_dsn=_e14_bases),
    _mutant("E17", "prime en double dans l'OD", "residu", "residu_nul", ligne_od=_e17_od, sans_effet_si="aucun élément hors brut sur ce bulletin"),
    _mutant("E18", "compteur de congés crédité deux fois", "compteurs_inchanges", bulletin=_e18, sans_effet_si="compteur de congés vide sur ce bulletin"),
    _mutant("E21", "correction appliquée au mauvais doublon", "doublon_a_sa_place", bulletin=_e21, sans_effet_si="aucune ligne en double sur ce bulletin"),
)

def _plus_cent(data: dict[str, Any], *chemin: str) -> None:
    for cle in chemin[:-1]:
        data = data.setdefault(cle, {})
    data[chemin[-1]] = round(_f(data.get(chemin[-1])) + 100.0, 2)


def _doubler_cotisation(data: dict[str, Any]) -> None:
    for ligne in _lignes(data):
        if _f(ligne.get("montant_salarial")) and ligne.get("taux_salarial") is not None:
            ligne["montant_salarial"] = round(_f(ligne["montant_salarial"]) * 2, 2)
            return


def _doubler_reduction(data: dict[str, Any]) -> None:
    ligne = _reduction(data)
    if ligne is not None:
        ligne["montant_patronal"] = round(_f(ligne.get("montant_patronal")) * 2, 2)


#: R-170 : ce que la revue (règles B) voit d'une erreur posée sur un bulletin juste.
ERREURS_SUR_UN_BULLETIN_JUSTE: dict[str, Callable[[dict[str, Any]], None]] = {
    "net à payer +100": lambda d: _plus_cent(d, "net_a_payer"),
    "net imposable +100": lambda d: _plus_cent(d, "synthese_net", "net_imposable"),
    "net social +100": lambda d: _plus_cent(d, "synthese_net", "montant_net_social"),
    "impôt +100": lambda d: _plus_cent(d, "synthese_net", "impot_prelevement_a_la_source", "montant"),
    "cumul brut faux": lambda d: _plus_cent(d, "cumuls", "cumuls", "brut_total"),
    "coût employeur +100": lambda d: _plus_cent(d, "pied_de_page", "cout_total_employeur"),
    "cotisation doublée": _doubler_cotisation,
    "brut +100": lambda d: _plus_cent(d, "salaire_brut"),
    "réduction doublée": _doubler_reduction,
}


def revue_contre_les_erreurs(data: Mapping[str, Any], anomalies: Callable[[dict[str, Any]], list[Any]]) -> dict[str, list[str] | None]:
    """Pour chaque erreur : les règles de la revue qui s'allument, en plus de celles du bulletin juste."""
    deja = {a.rule_id for a in anomalies(copy.deepcopy(dict(data)))}
    resultat: dict[str, list[str] | None] = {}
    for nom, injecter in ERREURS_SUR_UN_BULLETIN_JUSTE.items():
        copie = copy.deepcopy(dict(data))
        injecter(copie)
        # None : rien à abîmer sur ce bulletin (pas de réduction générale, par exemple).
        resultat[nom] = None if copie == dict(data) else sorted({a.rule_id for a in anomalies(copie) if a.level == "CRITIQUE"} - deja)
    return resultat


#: Les 11 injections de la relecture 6 (R-180), et leur constat dans le test.
ERREURS_DU_REGISTRE = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11")
