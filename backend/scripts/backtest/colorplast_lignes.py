"""Colorplast, ligne à ligne : chaque ligne du bulletin Quadra contre la ligne EYWAI.

Pour un mois, lit le PDF du cabinet (`colorplast_lignes_quadra`), charge le
bulletin EYWAI de la base visée (`payslips.payslip_data`, tel que le rejeu
l'a laissé), apparie les lignes une à une — brut, absences, congés,
cotisations avec base, taux, part salariale et patronale, totaux, net,
colonne de droite, compteurs — et imprime tout ce qui diffère, au centime.

Ce qui n'a pas de vis-à-vis est listé des deux côtés : « Quadra seulement »,
« EYWAI seulement ». Une différence de base ou de taux sans différence de
montant est une différence de présentation, comptée à part.

Usage : python -m scripts.backtest.colorplast_lignes 2026 6 [--json sortie.json] [BUGNY ...]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import supabase  # noqa: E402
from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne, lire_bulletins  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
CENTIME = 0.005


# ---------------------------------------------------------------- EYWAI, aplati
@dataclass
class Entree:
    zone: str
    cle: str
    libelle: str
    base: float | None = None      # quantité (brut) ou base (cotisation)
    taux: float | None = None
    gain: float | None = None
    sal: float | None = None       # perte (brut) ou part salariale (cotisation)
    pat: float | None = None
    utilisee: bool = False

    def valeurs(self) -> dict:
        return {k: v for k, v in (("base", self.base), ("taux", self.taux), ("gain", self.gain), ("sal", self.sal), ("pat", self.pat)) if v is not None}


def _num(x) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def aplatir(data: dict, data_precedent: dict | None) -> list[Entree]:
    e: list[Entree] = []
    for i, lig in enumerate(data.get("calcul_du_brut") or []):
        e.append(Entree("brut", f"brut{i}", lig.get("libelle", ""), _num(lig.get("quantite")), _num(lig.get("taux")), _num(lig.get("gain")), _num(lig.get("perte"))))
    for zone, cle in (("absence", "details_absences"), ("conge", "details_conges")):
        for i, lig in enumerate(data.get(cle) or []):
            e.append(Entree(zone, f"{zone}{i}", lig.get("libelle", ""), _num(lig.get("quantite")), _num(lig.get("taux")), _num(lig.get("gain")), _num(lig.get("perte"))))
    e.append(Entree("brut", "salaire_brut", "SALAIRE BRUT", gain=_num(data.get("salaire_brut"))))
    arb = data.get("arbitrage_conges") or ""
    m = re.search(r"\(?(?:soit )?([\d\s]+\.\d{2}) €\)", arb)
    if m:
        e.append(Entree("conge", "arbitrage", "Arbitrage des congés payés (règle retenue)", gain=float(m.group(1).replace(" ", ""))))
    sc = data.get("structure_cotisations") or {}
    compteur: dict[str, int] = {}
    for bloc in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
        for lig in sc.get(bloc) or []:
            cid = lig.get("coti_id") or ("csg_deductible" if str(lig.get("libelle", "")).lower().startswith("csg déductible")
                                       else "csg_non_deductible" if str(lig.get("libelle", "")).lower().startswith("csg/crds") else "?")
            compteur[cid] = compteur.get(cid, 0) + 1
            e.append(Entree("cotisation", f"{cid}#{compteur[cid]}", lig.get("libelle", ""), _num(lig.get("base")),
                            None if lig.get("taux_salarial") is None and lig.get("taux_patronal") is None else (_num(lig.get("taux_salarial")) if lig.get("taux_salarial") is not None else _num(lig.get("taux_patronal"))),
                            None, _num(lig.get("montant_salarial")), _num(lig.get("montant_patronal"))))
    for lig in (sc.get("bloc_autres_contributions") or {}).get("lignes") or []:
        cid = lig.get("coti_id", "?")
        compteur[cid] = compteur.get(cid, 0) + 1
        e.append(Entree("cotisation", f"{cid}#{compteur[cid]}", lig.get("libelle", ""), _num(lig.get("base")), _num(lig.get("taux_patronal")), None, _num(lig.get("montant_salarial")), _num(lig.get("montant_patronal"))))
    tot = sc.get("total_avant_csg_crds") or {}
    e.append(Entree("total", "total_retenues", "Total des retenues", sal=_num(tot.get("montant_salarial")), pat=_num(sc.get("total_patronal"))))
    sn = data.get("synthese_net") or {}
    pas = sn.get("impot_prelevement_a_la_source") or {}
    e.append(Entree("net", "net_imposable", "Net imposable", gain=_num(sn.get("net_imposable"))))
    e.append(Entree("net", "mns", "Montant net social", gain=_num(sn.get("montant_net_social"))))
    # Quadra imprime « NET A PAYER AVANT IMPOT SUR LE REVENU » APRÈS déduction
    # de l'acompte (Bugny janvier : 2 508,65 de net social, 2 369,63 d'acompte,
    # 139,02 imprimés). Notre `net_social_avant_impot` est le net avant
    # acompte : comparer les deux tels quels inventait un écart par bulletin.
    net_avant = _num(sn.get("net_social_avant_impot"))
    acompte_verse = _num(sn.get("acompte_verse")) or 0.0
    if net_avant is not None and acompte_verse:
        net_avant = round(net_avant - acompte_verse, 2)
    e.append(Entree("net", "net_avant_impot", "Net à payer avant impôt", gain=net_avant))
    e.append(Entree("net", "pas", "Impôt prélevé à la source", base=_num(pas.get("base")), taux=_num(pas.get("taux")), gain=_num(pas.get("montant"))))
    e.append(Entree("net", "net_hs_exo", "Net des heures sup exonérées", gain=_num(sn.get("montant_net_hs_exonerees"))))
    e.append(Entree("net", "net_a_payer", "Net à payer", gain=_num(data.get("net_a_payer"))))
    if _num(sn.get("acompte_verse")):
        e.append(Entree("net", "acompte", "Acompte", gain=_num(sn.get("acompte_verse"))))
    for i, lig in enumerate(data.get("primes_non_soumises") or []):
        e.append(Entree("non_soumis", f"pns{i}", lig.get("libelle", ""), gain=_num(lig.get("montant"))))
    for i, lig in enumerate(data.get("participations") or []):
        e.append(Entree("non_soumis", f"part{i}", lig.get("libelle", "Participation"), gain=_num(lig.get("montant") or lig.get("net"))))
    for i, lig in enumerate(data.get("revenus_hors_brut_imposables") or []):
        e.append(Entree("non_soumis", f"rhbi{i}", lig.get("libelle", ""), gain=_num(lig.get("montant"))))
    for i, lig in enumerate((data.get("retenues_saisies") or {}).get("saisies") or []):
        e.append(Entree("net", f"saisie{i}", lig.get("libelle", "Saisie"), sal=_num(lig.get("montant"))))
    c = (data.get("cumuls") or {}).get("cumuls") or {}
    cp = ((data_precedent or {}).get("cumuls") or {}).get("cumuls") or {}
    hp = _num(c.get("heures_remunerees"))
    if hp is not None and cp.get("heures_remunerees") is not None:
        hp = round(hp - float(cp["heures_remunerees"]), 2)
    prm = data.get("parametres") or {}
    pied = data.get("pied_de_page") or {}
    e += [
        Entree("droite", "smic", "SMIC horaire", gain=_num(prm.get("smic_horaire"))),
        Entree("droite", "plafond", "Plafond Sécu", gain=_num(prm.get("pss_mensuel"))),
        Entree("droite", "heures_periode", "Heures de la période", base=hp),
        Entree("droite", "cumul_heures", "Cumul heures", base=_num(c.get("heures_remunerees"))),
        Entree("droite", "cumul_hs", "Cumul heures sup", base=_num(c.get("heures_supplementaires_remunerees"))),
        Entree("droite", "cumul_bases", "Cumul des bases", gain=_num(c.get("cumul_brut_agirc_arrco"))),
        Entree("droite", "cumul_bruts", "Cumul des bruts", gain=_num(c.get("brut_total"))),
        Entree("droite", "allegement_mois", "Allègement cotisations employeur", pat=-_num(pied.get("total_allegements_patronaux")) if _num(pied.get("total_allegements_patronaux")) is not None else None),
        Entree("droite", "verse_employeur", "Total versé employeur", pat=_num(pied.get("cout_total_employeur"))),
        Entree("net", "net_imposable_cumul", "Net imposable cumulé", gain=_num(c.get("net_imposable"))),
        Entree("net", "pas_cumul", "Impôt prélevé cumulé", gain=_num(c.get("impot_preleve_a_la_source"))),
        Entree("net", "net_hs_exo_cumul", "Net des heures sup exonérées cumulé", gain=_num(c.get("montant_net_hs_exonerees_cumul"))),
    ]
    return e


# ---------------------------------------------------------------- appariement
def _lib(lig: Ligne) -> str:
    return lig.libelle.lower()


def _somme(entrees: list[Entree], champ: str) -> float | None:
    vals = [getattr(x, champ) for x in entrees if getattr(x, champ) is not None]
    return round(sum(vals), 6) if vals else None


def _base_commune(entrees: list[Entree]) -> float | None:
    vals = [x.base for x in entrees if x.base is not None]
    if not vals:
        return None
    return vals[0] if all(abs(v - vals[0]) < 0.011 for v in vals) else round(sum(vals), 2)


@dataclass
class Regle:
    nom: str
    quadra: callable                       # (ligne, precedente) -> bool
    eywai: callable                        # (entrees libres, ligne) -> list[Entree]
    champs: list                           # [(champ_quadra, champ_eywai, nature)]
    grouper: bool = False                  # sommer les lignes Quadra consécutives de même libellé
    taux_pct: bool = False                 # taux Quadra en %, EYWAI en fraction
    somme_base: bool = False               # plusieurs lignes EYWAI : base = somme (sinon commune)


def _brut(lib_debut: str, zone: str = "brut"):
    return lambda libres, lig: [x for x in libres if x.zone == zone and x.libelle.lower().startswith(lib_debut.lower())][:1]


def _coti(*ids: str, lib: str | None = None):
    def f(libres, lig):
        out = []
        for cid in ids:
            out += [x for x in libres if x.zone == "cotisation" and x.cle.split("#")[0] == cid and (lib is None or lib.lower() in x.libelle.lower())][:1]
        return out
    return f


def _cle(cle: str):
    return lambda libres, lig: [x for x in libres if x.cle == cle][:1]


def _absence_datee(libres, lig):
    m = re.search(r"(\d{2})(\d{2})(\d{2})\b", lig.libelle)
    cands = [x for x in libres if (x.zone == "absence" and "arrêt" not in x.libelle.lower() and "accident" not in x.libelle.lower()
                                   and "réduction" not in x.libelle.lower() and "entrée ou sortie" not in x.libelle.lower())
             or (x.zone == "brut" and (x.libelle.lower().startswith("abs.") or "férié" in x.libelle.lower()))]
    if "jf" in lig.libelle.lower() or "férié" in lig.libelle.lower():
        cands = [x for x in cands if "férié" in x.libelle.lower()] or cands
    dates = re.findall(r"(\d{2})(\d{2})(\d{2})\b", lig.libelle)
    if len(dates) >= 2:
        d1 = (dates[0][2], dates[0][1], dates[0][0])
        d2 = (dates[1][2], dates[1][1], dates[1][0])
        dans = []
        for x in cands:
            mx = re.search(r"(\d{2})/(\d{2})/(\d{2})", x.libelle)
            if mx and d1 <= (mx.group(3), mx.group(2), mx.group(1)) <= d2:
                dans.append(x)
        if dans:
            return dans
    if m:
        d = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        datees = [x for x in cands if d in x.libelle]
        if datees:
            return datees[:1]
    return cands[:1]


def _arret(libres, lig):
    """Les jours d'arrêt EYWAI (7 h chacun) jusqu'à concurrence des heures de la ligne Quadra."""
    cands = [x for x in libres if x.zone == "absence" and ("arrêt" in x.libelle.lower() or "accident" in x.libelle.lower())]
    if lig.base is None:
        return cands
    out, total = [], 0.0
    for x in cands:
        if total + (x.base or 0) > lig.base + 0.5 and out:
            break
        out.append(x)
        total += x.base or 0
    return out


def _n_jours(libres, lig, debut: str, zone: str = "conge"):
    n = max(1, int(round(lig.base or 1))) if (lig.base or 0) < 20 else 1
    return [x for x in libres if x.zone == zone and x.libelle.lower().startswith(debut.lower())][:n]


def _csg(prefixe: str, taux: float | None = None):
    """Une ligne CSG Quadra peut réunir salaire et participation : on prend l'entrée dont la base colle, sinon la somme."""
    def f(libres, lig):
        cands = [x for x in libres if x.cle.startswith(prefixe) and (taux is None or (x.taux is not None and abs(x.taux - taux) < 1e-6))]
        if lig.base is not None:
            for x in cands:
                if x.base is not None and abs(x.base - lig.base) <= 0.02:
                    return [x]
            if cands and abs(sum(x.base or 0 for x in cands) - lig.base) <= 0.02:
                return cands
        return cands[:1]
    return f


def _csg_non_ded(libres, lig):
    taux = None if lig.taux is None else round(lig.taux / 100, 6)
    return _csg("csg_non_deductible", taux)(libres, lig)


def _csg_participation(libres, lig):
    cands = [x for x in libres if x.zone == "cotisation" and "participation" in x.libelle.lower() and x.cle.startswith("csg")]
    if lig.base is not None:
        proches = [x for x in cands if x.base is not None and abs(x.base - lig.base) <= 0.02]
        if proches:
            return proches
    return cands


def _autres_contrib(libres, lig):
    grandes = [x for x in libres if x.zone == "cotisation" and x.cle.split("#")[0] in ("CFP", "csa", "dialogue_social", "fnal", "taxe_apprentissage", "taxe_apprentissage_solde", "cpf_cdd")]
    toutes_libres = [x for x in libres if x.zone == "cotisation" and x.cle.split("#")[0] in ("CFP", "csa", "dialogue_social", "fnal", "taxe_apprentissage", "taxe_apprentissage_solde", "cpf_cdd")]
    if grandes and len(toutes_libres) == len(grandes) and grandes[0].base is not None and (lig.base or 0) >= 0.5 * grandes[0].base:
        return grandes  # première ligne du bulletin : le groupe, même si la base diffère
    petites = [x for x in libres if x.cle.startswith("forfait_social")]
    if lig.base is not None:
        proches = [x for x in petites if x.base is not None and abs(x.base - lig.base) <= 0.02]
        if proches:
            return proches[:1]
    return []


def _non_soumis(mots: tuple[str, ...]):
    return lambda libres, lig: [x for x in libres if x.zone in ("non_soumis", "net") and any(m in x.libelle.lower() for m in mots)][:1]


M = "montant"
P = "presentation"
Q_GAIN = [("base", "base", P), ("taux", "taux", P), ("gain", "gain", M)]
Q_RET = [("base", "base", P), ("taux", "taux", P), ("montant_sal", "sal", M)]
Q_COTI = [("base", "base", P), ("taux", "taux", P), ("montant_sal", "sal", M), ("montant_pat", "pat", M)]

REGLES: list[Regle] = [
    Regle("salaire de base", lambda lig, p: _lib(lig).startswith("salaire de base"), _brut("Salaire de base"), Q_GAIN),
    Regle("HS structurelles", lambda lig, p: _lib(lig).startswith("h. supp majorées") and lig.gain is not None, _brut("Heures suppl. structurelles"), Q_GAIN),
    Regle("indemnité CP part HS", lambda lig, p: _lib(lig).startswith("h. supp majorées") and lig.montant_sal is not None and p is not None and _lib(p).startswith("h.absence congés"), _brut("Indemnité de congés payés (partie HS", "conge"), [("base", "base", P), ("taux", "taux", P), ("montant_sal", "gain", M)], grouper=True, somme_base=True),
    Regle("réduction HS structurelles (absence)", lambda lig, p: _lib(lig).startswith("h. supp majorées") and lig.montant_sal is not None, lambda libres, lig: [x for x in libres if x.zone in ("absence", "brut") and "réduction hs" in x.libelle.lower()], Q_RET, somme_base=True),
    Regle("sous-total", lambda lig, p: _lib(lig).startswith("sous total"), _brut("SOUS-TOTAL"), Q_GAIN),
    Regle("HS 25 %", lambda lig, p: _lib(lig).startswith("heures supplémentaires 25"), _brut("Heures suppl. majorées à 25"), Q_GAIN),
    Regle("HS 50 %", lambda lig, p: _lib(lig).startswith("heures supplémentaires 50"), _brut("Heures suppl. majorées à 50"), Q_GAIN),
    Regle("prime exceptionnelle", lambda lig, p: _lib(lig).startswith("prime exceptionnelle"), _brut("Prime exceptionnelle"), [("gain", "gain", M)]),
    Regle("prime d'ancienneté", lambda lig, p: _lib(lig).startswith("prime ancienneté"), _brut("Prime d'ancienneté"), Q_GAIN, taux_pct=True),
    Regle("PPV", lambda lig, p: "partage de la valeur" in _lib(lig) or _lib(lig).startswith("ppv"), _non_soumis(("partage de la valeur", "ppv")), [("gain", "gain", M)]),
    Regle("congé payé (jours)", lambda lig, p: _lib(lig).startswith("congés payés :"), _brut("Absence congés payés", "conge"), [("gain", "sal", M)], grouper=True),
    Regle("indemnité CP part base", lambda lig, p: _lib(lig).startswith("h.absence congés"), _brut("Indemnité de congés payés (partie base", "conge"), [("base", "base", P), ("taux", "taux", P), ("montant_sal", "gain", M)], grouper=True, somme_base=True),
    Regle("arbitrage CP", lambda lig, p: _lib(lig).startswith("arbitrage des conges"), _cle("arbitrage"), [("gain", "gain", M)]),
    Regle("indemnité compensatrice CP", lambda lig, p: "compensatrice" in _lib(lig) or "ind.de cp" in _lib(lig) or "cp des cdd" in _lib(lig), _brut("Indemnité compensatrice", "conge"), [("gain", "gain", M)]),
    Regle("indemnité de précarité", lambda lig, p: "précarité" in _lib(lig) or "precarite" in _lib(lig), _brut("Prime de précarité"), [("gain", "gain", M)]),
    Regle("absence non payée / événement", lambda lig, p: _lib(lig).startswith("abs."), _absence_datee, Q_RET, somme_base=True),
    Regle("absence maladie / accident", lambda lig, p: _lib(lig).startswith(("absence maladie", "absence accident", "absence a.t")), _arret, Q_RET, somme_base=True),
    Regle("absence entrée / sortie", lambda lig, p: _lib(lig).startswith("absence pour entrée"), _brut("Absence pour entrée ou sortie", "absence"), Q_RET),
    Regle("maintien de salaire", lambda lig, p: _lib(lig).startswith("maintien de salaire"), _brut("Maintien de salaire"), [("gain", "gain", M)]),
    Regle("participation", lambda lig, p: "participation" in _lib(lig) and "acompte" not in _lib(lig), lambda libres, lig: [x for x in libres if x.zone == "brut" and x.libelle.lower().startswith("participation")][:1], [("gain", "gain", M)]),
    Regle("acompte sur participation", lambda lig, p: "participation" in _lib(lig) and "acompte" in _lib(lig), lambda libres, lig: [x for x in libres if x.zone == "non_soumis" and "acompte" in x.libelle.lower() and "participation" in x.libelle.lower()][:1], [("gain", "gain", M), ("montant_sal", "gain", M)]),
    Regle("CSG sur participation", lambda lig, p: "csg autres revenus" in _lib(lig) or ("csg" in _lib(lig) and "part" in _lib(lig) and "rbst" not in _lib(lig)), _csg_participation, [("base", "base", P), ("taux", "taux", P), ("montant_sal", "sal", M)], taux_pct=True),
    Regle("salaire brut", lambda lig, p: _lib(lig).startswith("salaire brut"), _cle("salaire_brut"), [("gain", "gain", M)]),
    Regle("maladie", lambda lig, p: _lib(lig).startswith("sécu.soc-mal"), _coti("securite_sociale_maladie"), [("base", "base", P), ("montant_pat", "pat", M)], grouper=True),
    Regle("AT-MP", lambda lig, p: _lib(lig).startswith("acc. du trav"), _coti("at_mp"), [("base", "base", P), ("montant_pat", "pat", M)]),
    Regle("vieillesse plafonnée", lambda lig, p: _lib(lig).startswith("sécu.soc plafonnée"), _coti("retraite_secu_plafond"), Q_COTI, taux_pct=True),
    Regle("vieillesse déplafonnée", lambda lig, p: _lib(lig).startswith("sécu.soc déplafonnée"), _coti("retraite_secu_deplafond"), Q_COTI, taux_pct=True),
    Regle("retraite complémentaire T1", lambda lig, p: _lib(lig).startswith("complémentaire tranche 1"), _coti("retraite_comp_t1", "ceg_t1"), Q_COTI, taux_pct=True),
    Regle("retraite complémentaire T2", lambda lig, p: _lib(lig).startswith("complémentaire tranche 2"), _coti("retraite_comp_t2", "ceg_t2"), Q_COTI, taux_pct=True),
    Regle("APEC", lambda lig, p: _lib(lig).startswith("apec"), _coti("apec"), Q_COTI, taux_pct=True),
    Regle("famille", lambda lig, p: _lib(lig).startswith("famille"), _coti("allocations_familiales"), [("base", "base", P), ("montant_pat", "pat", M)]),
    Regle("chômage", lambda lig, p: _lib(lig).startswith("chômage"), _coti("assurance_chomage"), [("base", "base", P), ("montant_pat", "pat", M)]),
    Regle("AGS", lambda lig, p: _lib(lig).startswith("ags"), _coti("ags"), [("base", "base", P), ("montant_pat", "pat", M)]),
    Regle("autres contributions", lambda lig, p: _lib(lig).startswith("autres contrib"), _autres_contrib, [("base", "base", P), ("montant_pat", "pat", M)]),
    Regle("CSG déductible", lambda lig, p: _lib(lig).startswith("csg déductible"), _csg("csg_deductible"), Q_RET, taux_pct=True),
    Regle("réduction générale", lambda lig, p: _lib(lig).startswith("exo., ecret"), _coti("reduction_generale"), [("montant_pat", "pat", M)]),
    Regle("prévoyance", lambda lig, p: "prevoyance" in _lib(lig) or "prévoyance" in _lib(lig), lambda libres, lig: [x for x in libres if x.zone == "cotisation" and x.cle.startswith("prevoyance")][:1], Q_COTI, taux_pct=True),
    Regle("retraite supplémentaire", lambda lig, p: "retraite sup" in _lib(lig) or "art 83" in _lib(lig), lambda libres, lig: [x for x in libres if x.zone == "cotisation" and "retraite_sup" in x.cle][:1], Q_COTI, taux_pct=True),
    Regle("mutuelle isolé", lambda lig, p: "mutuelle isole" in _lib(lig) or "mutuelle isolé" in _lib(lig), _coti("mutuelle", lib="Isolé"), [("montant_sal", "sal", M), ("montant_pat", "pat", M)]),
    Regle("mutuelle famille", lambda lig, p: "mutuelle famille" in _lib(lig), _coti("mutuelle", lib="Famille"), [("gain", "sal", M), ("montant_sal", "sal", M)]),
    Regle("réduction salariale HS", lambda lig, p: _lib(lig).startswith("reduction salariale hs"), _coti("reduction_hs_salariale"), Q_RET, taux_pct=True),
    Regle("déduction patronale HS", lambda lig, p: _lib(lig).startswith("reduct heures suppl"), _coti("deduction_hs_patronale"), [("base", "base", P), ("montant_pat", "pat", M)]),
    Regle("total des retenues", lambda lig, p: _lib(lig).startswith("total des retenues"), _cle("total_retenues"), [("montant_sal", "sal", M), ("montant_pat", "pat", M)]),
    Regle("mutuelle patronale réintégrée", lambda lig, p: _lib(lig).startswith("cotis. retraite/prév"), lambda libres, lig: [x for x in libres if x.zone == "cotisation" and x.cle.startswith("mutuelle") and "isolé" in x.libelle.lower()][:1], [("gain", "pat", M), ("montant_sal", "pat", M)]),
    Regle("retraite supplémentaire cadre", lambda lig, p: _lib(lig).startswith("retraite supplémentaire"), lambda libres, lig: [x for x in libres if x.zone == "cotisation" and "retraite_sup" in x.cle][:1], Q_COTI, taux_pct=True),
    Regle("net imposable", lambda lig, p: _lib(lig).startswith("net imposable"), _cle("net_imposable"), [("gain", "gain", M)]),
    Regle("CSG/CRDS non déductible", lambda lig, p: _lib(lig).startswith("csg/crds non déductible"), _csg_non_ded, Q_RET, taux_pct=True),
    Regle("acompte", lambda lig, p: _lib(lig).startswith("acompte"), _cle("acompte"), [("gain", "gain", M), ("montant_sal", "gain", M)]),
    Regle("report de net négatif", lambda lig, p: _lib(lig).startswith("report nap"), _cle("acompte"), [("montant_sal", "gain", M)]),
    Regle("note de frais", lambda lig, p: "note de frais" in _lib(lig) or "notes de frais" in _lib(lig) or (_lib(lig).startswith("rbst") and "csg" not in _lib(lig)), _non_soumis(("notes de frais", "note de frais", "remb", "fournitures")), [("gain", "gain", M)]),
    Regle("indemnité de transport", lambda lig, p: "transport" in _lib(lig), _non_soumis(("transport",)), [("gain", "gain", M)]),
    Regle("trop-perçu / saisie", lambda lig, p: "trop" in _lib(lig) or "saisie" in _lib(lig) or "sgc" in _lib(lig), _non_soumis(("trop", "saisie", "sgc", "acompte")), [("gain", "gain", M), ("montant_sal", "gain", M)]),
]

DROITE_NET = [  # (clé Quadra, clé EYWAI, champ EYWAI, nature)
    ("smic", "smic", "gain", M), ("plafond", "plafond", "gain", M), ("heures_periode", "heures_periode", "base", P),
    ("cumul_heures", "cumul_heures", "base", P), ("cumul_hs", "cumul_hs", "base", P),
    ("cumul_bases", "cumul_bases", "gain", M), ("cumul_bruts", "cumul_bruts", "gain", M),
    ("allegement_mois", "allegement_mois", "pat", M), ("verse_employeur", "verse_employeur", "pat", M),
]
NET_CHAMPS = [
    ("mns", "mns", "gain", M), ("net_avant_impot", "net_avant_impot", "gain", M), ("net_imposable", "net_imposable", "gain", M),
    ("net_imposable_cumul", "net_imposable_cumul", "gain", M), ("pas_base", "pas", "base", P), ("pas_taux", "pas", "taux", P),
    ("pas_montant", "pas", "gain", M), ("pas_cumul", "pas_cumul", "gain", M), ("net_hs_exo", "net_hs_exo", "gain", M),
    ("net_hs_exo_cumul", "net_hs_exo_cumul", "gain", M), ("net_a_payer", "net_a_payer", "gain", M),
]


def comparer(b: Bulletin, entrees: list[Entree]) -> dict:
    lignes_out, quadra_seul = [], []
    precedente: Ligne | None = None
    i = 0
    while i < len(b.lignes):
        lig = b.lignes[i]
        groupe = [lig]
        regle = next((r for r in REGLES if r.quadra(lig, precedente)), None)
        if regle is None:
            if lig.valeurs():
                quadra_seul.append({"libelle": lig.libelle, "code": lig.code, **lig.valeurs()})
            precedente = lig
            i += 1
            continue
        if regle.grouper:
            prefixe = lig.libelle.split(":")[0].strip().lower()
            while i + 1 < len(b.lignes) and b.lignes[i + 1].libelle.split(":")[0].strip().lower() == prefixe:
                i += 1
                groupe.append(b.lignes[i])
        libres = [x for x in entrees if not x.utilisee]
        cibles = regle.eywai(libres, lig)
        if not cibles and regle.nom == "mutuelle patronale réintégrée":
            cibles = [x for x in entrees if x.zone == "cotisation" and x.cle.startswith("mutuelle") and "isolé" in x.libelle.lower()][:1]
        if not cibles:
            quadra_seul.append({"libelle": lig.libelle, "code": lig.code, "regle": regle.nom, **{k: v for g in groupe for k, v in g.valeurs().items()}})
            precedente = lig
            i += 1
            continue
        for x in cibles:
            if regle.nom != "mutuelle patronale réintégrée":
                x.utilisee = True
        q = {
            # Un groupe de congés (une ligne par jour) additionne ses bases ; un groupe de cotisations sur la
            # même base (maladie 7 % + 6 %, contributions patronales) garde la base commune.
            "base": (round(sum(g.base or 0 for g in groupe), 2) if regle.somme_base and len(groupe) > 1
                     else groupe[0].base if all(g.base == groupe[0].base for g in groupe)
                     else round(sum(g.base or 0 for g in groupe), 2)),
            "taux": groupe[0].taux,
            "gain": round(sum(g.gain for g in groupe if g.gain is not None), 2) if any(g.gain is not None for g in groupe) else None,
            "montant_sal": round(sum(g.montant_sal for g in groupe if g.montant_sal is not None), 2) if any(g.montant_sal is not None for g in groupe) else None,
            "montant_pat": round(sum(g.montant_pat for g in groupe if g.montant_pat is not None), 2) if any(g.montant_pat is not None for g in groupe) else None,
        }
        ey = {
            "base": _somme(cibles, "base") if regle.somme_base else _base_commune(cibles),
            # plusieurs lignes EYWAI (une absence par jour) : le taux est commun, il ne s'additionne pas
            "taux": _base_commune([type(c)(**{**c.__dict__, "base": c.taux}) for c in cibles]) if len(cibles) > 1 else _somme(cibles, "taux"),
            "gain": _somme(cibles, "gain"), "sal": _somme(cibles, "sal"), "pat": _somme(cibles, "pat"),
        }
        if regle.taux_pct and ey["taux"] is not None:
            ey["taux"] = round(ey["taux"] * 100, 4)
        champs = []
        for cq, ce, nature in regle.champs:
            vq, ve = q.get(cq), ey.get(ce)
            if vq is None or ve is None:
                continue
            if nature == M:
                vq, ve = abs(vq), abs(ve)
            ecart = round(vq - ve, 2)
            champs.append({"champ": cq, "quadra": vq, "eywai": ve, "ecart": ecart, "nature": nature, "ok": abs(ecart) < CENTIME})
        lignes_out.append({
            "regle": regle.nom, "section": lig.section, "code": lig.code,
            "quadra": " + ".join(g.libelle for g in groupe) if len(groupe) > 1 else lig.libelle,
            "eywai": " + ".join(x.libelle for x in cibles), "champs": champs,
        })
        precedente = lig
        i += 1

    def bloc(liste, prefixe):
        for cq, ce, champ, nature in liste:
            vq = b.droite.get(cq) if prefixe == "droite" else b.net.get(cq)
            x = next((y for y in entrees if y.cle == ce), None)
            ve = getattr(x, champ) if x else None
            if vq is None and ve is None:
                continue
            if x:
                x.utilisee = True
            if vq is None or ve is None:
                (quadra_seul if ve is None else eywai_seul).append({"libelle": cq if ve is None else x.libelle, "valeur": vq if ve is None else ve})
                continue
            if nature == M:
                vq, ve = abs(vq), abs(ve)
            ecart = round(vq - ve, 2)
            lignes_out.append({"regle": prefixe, "section": prefixe, "code": None, "quadra": cq, "eywai": x.libelle,
                               "champs": [{"champ": champ, "quadra": vq, "eywai": ve, "ecart": ecart, "nature": nature, "ok": abs(ecart) < CENTIME}]})

    eywai_seul: list = []
    bloc(DROITE_NET, "droite")
    bloc(NET_CHAMPS, "net")
    # Petites lignes « Autres contrib. » sans vis-à-vis une à une : comparées en somme aux forfaits sociaux restants.
    restes_q = [q for q in quadra_seul if q.get("regle") == "autres contributions"]
    restes_e = [x for x in entrees if not x.utilisee and x.cle.startswith("forfait_social")]
    if restes_q and restes_e:
        for q in restes_q:
            quadra_seul.remove(q)
        for x in restes_e:
            x.utilisee = True
        bq, pq = round(sum(q.get("base") or 0 for q in restes_q), 2), round(sum(q.get("montant_pat") or 0 for q in restes_q), 2)
        be, pe = round(sum(x.base or 0 for x in restes_e), 2), round(sum(x.pat or 0 for x in restes_e), 2)
        lignes_out.append({"regle": "forfaits sociaux (somme)", "section": "Q600", "code": None,
                           "quadra": " + ".join(q["libelle"] for q in restes_q), "eywai": " + ".join(x.libelle for x in restes_e),
                           "champs": [{"champ": "base", "quadra": bq, "eywai": be, "ecart": round(bq - be, 2), "nature": P, "ok": abs(bq - be) < CENTIME},
                                      {"champ": "montant_pat", "quadra": pq, "eywai": pe, "ecart": round(pq - pe, 2), "nature": M, "ok": abs(pq - pe) < CENTIME}]})
    for x in entrees:
        if x.utilisee:
            continue
        v = x.valeurs()
        if not any(k in v and abs(v[k]) >= CENTIME for k in ("gain", "sal", "pat")):
            continue
        eywai_seul.append({"libelle": x.libelle, "zone": x.zone, **v})
    n_montant = sum(1 for lig in lignes_out for c in lig["champs"] if c["nature"] == M and not c["ok"])
    n_pres = sum(1 for lig in lignes_out for c in lig["champs"] if c["nature"] == P and not c["ok"])
    n_ok = sum(1 for lig in lignes_out for c in lig["champs"] if c["ok"])
    etat = "identique" if n_montant == 0 and not quadra_seul and not eywai_seul and n_pres == 0 else ("presentation" if n_montant == 0 and not quadra_seul and not eywai_seul else "ecart")
    return {"etat": etat, "champs_identiques": n_ok, "ecarts_montant": n_montant, "ecarts_presentation": n_pres,
            "lignes": lignes_out, "quadra_seulement": quadra_seul, "eywai_seulement": eywai_seul, "cp_quadra": {k: list(v) for k, v in b.cp.items()}}


# ---------------------------------------------------------------- pilotage
def charger_eywai(annee: int) -> dict[tuple[str, int], dict]:
    emps = supabase.table("employees").select("id, last_name").eq("company_id", COMPANY_ID).execute().data or []
    par_id = {e["id"]: e["last_name"].upper().replace(" ", "") for e in emps}
    rows = supabase.table("payslips").select("employee_id, month, payslip_data").in_("employee_id", list(par_id)).eq("year", annee).execute().data or []
    return {(par_id[r["employee_id"]], r["month"]): r["payslip_data"] for r in rows}


def comparer_le_mois(annee: int, mois: int, eywai: dict, seuls: list[str] | None = None) -> dict:
    bulletins = lire_bulletins(annee, mois)
    out = {}
    for mat, b in bulletins.items():
        if seuls and mat not in seuls:
            continue
        data = eywai.get((mat, mois))
        if data is None:
            out[mat] = {"etat": "absent", "message": "pas de bulletin EYWAI"}
            continue
        entrees = aplatir(data, eywai.get((mat, mois - 1)))
        out[mat] = comparer(b, entrees)
    return out


def imprimer(mois: int, resultats: dict) -> None:
    for mat, r in resultats.items():
        if r.get("etat") == "absent":
            print(f"\n=== {mat} {mois:02d} : {r['message']}")
            continue
        print(f"\n=== {mat} {mois:02d} : {r['etat']} — {r['champs_identiques']} champs identiques, "
              f"{r['ecarts_montant']} écart(s) de montant, {r['ecarts_presentation']} de présentation, "
              f"{len(r['quadra_seulement'])} ligne(s) Quadra seule(s), {len(r['eywai_seulement'])} EYWAI seule(s)")
        for lig in r["lignes"]:
            for c in lig["champs"]:
                if not c["ok"]:
                    print(f"    {c['nature'][:4]}  {lig['quadra'][:38]:38s} ↔ {lig['eywai'][:38]:38s} {c['champ']:11s} Quadra {c['quadra']:>10.4g}  EYWAI {c['eywai']:>10.4g}  écart {c['ecart']:+.2f}")
        for q in r["quadra_seulement"]:
            print(f"    QUADRA SEUL  {q}")
        for e in r["eywai_seulement"]:
            print(f"    EYWAI  SEUL  {e}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    chemin_json = None
    if "--json" in argv:
        i = argv.index("--json")
        chemin_json = argv[i + 1]
        del argv[i:i + 2]
    annee, mois = int(argv[0]), int(argv[1])
    seuls = argv[2:] or None
    eywai = charger_eywai(annee)
    res = comparer_le_mois(annee, mois, eywai, seuls)
    imprimer(mois, res)
    if chemin_json:
        json.dump(res, open(chemin_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
