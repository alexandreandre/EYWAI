"""Construction des blocs rémunération DSN (S21.G00.51) depuis un bulletin MARTINE."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.modules.dsn_import.domain.model import RemunerationBlock


@dataclass
class RemunerationBuildResult:
    remunerations: List[RemunerationBlock]
    activites: List[Dict[str, Any]]
    heures_activite: float
    salaire_base: float
    hs_structurelles_montant: float
    hs_structurelles_heures: float
    hs_aleatoires_montant: float
    hs_aleatoires_heures: float
    salaire_retabli: float


def _f(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _lib(line: Dict[str, Any]) -> str:
    return str(line.get("libelle") or "").strip().lower()


def _is_sous_total(line: Dict[str, Any]) -> bool:
    if line.get("is_sous_total"):
        return True
    lib = _lib(line)
    return lib.startswith("sous-total") or lib.startswith("sous total")


def _is_hs_structurelle(lib: str) -> bool:
    return "suppl" in lib and "structurell" in lib


def _is_hs_aleatoire(lib: str) -> bool:
    if "suppl" not in lib and "heure" not in lib:
        return False
    if "structurell" in lib:
        return False
    return bool(
        re.search(r"heures?\s+suppl|h\.?\s*s\.?|compl[eé]mentaires?", lib, re.I)
    )


def _iter_brut_lines(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    calc = payslip_data.get("calcul_du_brut")
    if isinstance(calc, list):
        return [x for x in calc if isinstance(x, dict)]
    if isinstance(calc, dict):
        lines = calc.get("lignes") or calc.get("lines") or []
        if isinstance(lines, list):
            return [x for x in lines if isinstance(x, dict)]
    return []


def _sum_absence_pertes(payslip_data: Dict[str, Any]) -> float:
    total = 0.0
    for key in ("details_absences", "details_conges"):
        rows = payslip_data.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                total += _f(row.get("perte"))
    return round(total, 2)


@dataclass
class Absences:
    """Ce que les absences du mois retirent au bulletin, en heures et en euros.

    Les congés payés n'en sont pas : ils sont rémunérés (la retenue et
    l'indemnité se compensent), et la réduction d'heures sup structurelles qui
    suit leur ligne leur appartient. L'absence pour entrée ou sortie réduit les
    heures payées mais n'est pas une absence du salarié (pas de type 02).
    """

    heures_non_payees: float = 0.0
    heures_absence: float = 0.0
    # Retenues d'absence, entrée / sortie comprises : ce qu'il faut rendre au
    # brut pour reconstituer le salaire d'un mois complet (003).
    retenues: float = 0.0
    # Part des retenues due à des absences injustifiées : hors salaire
    # rétabli (003), dans la rémunération habituelle du mois complet (029).
    retenues_injustifiees: float = 0.0
    compensations: float = 0.0
    entree_sortie: bool = False


def _est_conges_payes(libelle: str) -> bool:
    texte = libelle.replace("é", "e").replace("É", "E").lower()
    return "conges payes" in texte or "absence cp" in texte


def analyser_absences(payslip_data: Dict[str, Any]) -> Absences:
    """Lit les lignes d'absence du brut, bulletin calculé ou repris.

    Un bulletin calculé range ses absences dans ``details_absences`` (et ses CP
    dans ``details_conges``, ignorés ici) ; un bulletin repris les garde dans
    ``calcul_du_brut``. On lit les deux.
    """
    resultat = Absences()
    lignes = _iter_brut_lines(payslip_data) + [
        l for l in (payslip_data.get("details_absences") or []) if isinstance(l, dict)
    ]
    ligne_precedente_cp = False
    ligne_precedente_injustifiee = False
    for ligne in lignes:
        libelle = _lib(ligne)
        perte = _f(ligne.get("perte"))
        gain = _f(ligne.get("gain"))
        heures = _f(ligne.get("quantite"))
        if perte <= 0:
            explication = str(ligne.get("explication") or "").lower()
            if gain > 0 and ("maintien" in libelle or explication.startswith("absence")):
                # Maintien de salaire, ou retenue plafonnée au salaire du mois :
                # rend une partie de ce que l'absence avait retiré.
                resultat.compensations += gain
            continue
        if _est_conges_payes(libelle):
            ligne_precedente_cp = True
            continue
        if "structurell" in libelle and ligne_precedente_cp:
            continue
        ligne_precedente_cp = False
        injustifiee = "injustifi" in libelle or (
            "structurell" in libelle and ligne_precedente_injustifiee
        )
        ligne_precedente_injustifiee = injustifiee
        resultat.heures_non_payees += heures
        resultat.retenues += perte
        if injustifiee:
            resultat.retenues_injustifiees += perte
        if "entrée ou sortie" in libelle or "entree ou sortie" in libelle:
            resultat.entree_sortie = True
            continue
        resultat.heures_absence += heures
    resultat.heures_non_payees = round(resultat.heures_non_payees, 2)
    resultat.heures_absence = round(resultat.heures_absence, 2)
    resultat.retenues = round(resultat.retenues, 2)
    resultat.retenues_injustifiees = round(resultat.retenues_injustifiees, 2)
    resultat.compensations = round(resultat.compensations, 2)
    return resultat


HEURES_LEGALES_MOIS = 151.67


def _manque_du_mois(payslip_data: Dict[str, Any], heures_contrat_mois: float) -> float:
    """Ce que la base et les HS structurelles auraient payé de plus sur un mois complet."""
    pleines = {
        "base": min(heures_contrat_mois, HEURES_LEGALES_MOIS),
        "hs": max(0.0, round(heures_contrat_mois - HEURES_LEGALES_MOIS, 2)),
    }
    manque = 0.0
    for ligne in _iter_brut_lines(payslip_data):
        if _is_sous_total(ligne):
            continue
        libelle = _lib(ligne)
        if "salaire de base" in libelle or libelle.startswith("salaire base"):
            nature = "base"
        elif _is_hs_structurelle(libelle):
            nature = "hs"
        else:
            continue
        taux, heures = _f(ligne.get("taux")), _f(ligne.get("quantite"))
        if taux > 0 and heures > 0 and pleines[nature] > heures:
            manque += round(taux * pleines[nature], 2) - _f(ligne.get("gain"))
    return round(manque, 2)


def jours_calendaires(debut_dsn: str, fin_dsn: str) -> int:
    """Jours calendaires de la période, bornes comprises (dates JJMMAAAA)."""
    from datetime import datetime

    try:
        debut = datetime.strptime(debut_dsn, "%d%m%Y")
        fin = datetime.strptime(fin_dsn, "%d%m%Y")
    except (TypeError, ValueError):
        return 0
    return max(0, (fin - debut).days + 1)


def _rem_block(
    *,
    type_code: str,
    montant: float,
    period_start: str,
    period_end: str,
    heures: float = 0.0,
    contrat_ref: str = "00000",
) -> RemunerationBlock:
    rubriques: Dict[str, str] = {
        "S21.G00.51.001": period_start,
        "S21.G00.51.002": period_end,
        "S21.G00.51.010": contrat_ref,
        "S21.G00.51.011": type_code,
        "S21.G00.51.013": f"{round(montant, 2):.2f}",
    }
    if heures > 0:
        rubriques["S21.G00.51.012"] = f"{round(heures, 2):.2f}"
    return RemunerationBlock(
        type_code=type_code,
        montant=round(montant, 2),
        heures=round(heures, 2) if heures > 0 else 0.0,
        rubriques=rubriques,
    )


def analyze_calcul_du_brut(payslip_data: Dict[str, Any]) -> Dict[str, float]:
    """Agrège le détail brut pour ventiler les types DSN."""
    salaire_base = 0.0
    sous_total_contractuel = 0.0
    hs_struct_m = hs_struct_h = 0.0
    hs_alea_m = hs_alea_h = 0.0
    autres_gains = 0.0
    heures_base = 0.0

    for line in _iter_brut_lines(payslip_data):
        lib = _lib(line)
        gain = _f(line.get("gain"))
        quantite = _f(line.get("quantite"))
        if _is_sous_total(line):
            if "contractuel" in lib or sous_total_contractuel <= 0:
                sous_total_contractuel = gain
            continue
        if "salaire de base" in lib or lib.startswith("salaire base"):
            salaire_base += gain
            heures_base += quantite
            continue
        if _is_hs_structurelle(lib):
            hs_struct_m += gain
            hs_struct_h += quantite
            continue
        if _is_hs_aleatoire(lib):
            hs_alea_m += gain
            hs_alea_h += quantite
            continue
        # Primes et autres éléments positifs (hors pertes)
        if gain:
            autres_gains += gain

    # Repli : si pas de sous-total, reconstituer
    if sous_total_contractuel <= 0:
        sous_total_contractuel = round(salaire_base + hs_struct_m, 2)

    return {
        "salaire_base": round(salaire_base, 2),
        "sous_total_contractuel": round(sous_total_contractuel, 2),
        "hs_structurelles_montant": round(hs_struct_m, 2),
        "hs_structurelles_heures": round(hs_struct_h, 2),
        "hs_aleatoires_montant": round(hs_alea_m, 2),
        "hs_aleatoires_heures": round(hs_alea_h, 2),
        "autres_gains": round(autres_gains, 2),
        "heures_base": round(heures_base, 2),
        "absence_pertes": _sum_absence_pertes(payslip_data),
    }


def build_remunerations_from_payslip(
    payslip_data: Dict[str, Any],
    *,
    brut: float,
    period_start: str,
    period_end: str,
    period: str,
    contrat_ref: str = "00000",
    jours_plafond: Optional[int] = None,
    indemnites_rupture: float = 0.0,
    heures_contrat_mois: Optional[float] = None,
    mois_incomplet: bool = False,
    mesure_activite: Optional[float] = None,
) -> RemunerationBuildResult:
    """Produit les types 001/002/003/010/017/018/028/029 alignés sur Cegid.

    ``jours_plafond`` : jours calendaires retenus pour le plafond (53 unité
    40) ; à défaut, ceux de la période. ``indemnites_rupture`` : indemnités de
    fin de contrat comprises dans le brut et déclarées en bloc 52 — elles
    n'entrent ni dans le salaire chômage (002, CT 51.011), ni dans les
    rémunérations hors éléments non affectés par l'absence (028, 029).
    ``mois_incomplet`` et ``heures_contrat_mois`` : entrée ou sortie en cours
    de mois, base proratisée sans ligne d'absence — le rétabli reconstitue le
    mois complet. ``mesure_activite`` : mesure du travail rémunéré (53 type
    01) quand elle ne se compte pas en heures (forfait jours).
    """
    parts = analyze_calcul_du_brut(payslip_data)
    absences = analyser_absences(payslip_data)
    brut_r = round(float(brut or 0), 2)

    # 010 = salaire de base contractuel (sous-total Cegid)
    montant_010 = parts["sous_total_contractuel"] or parts["salaire_base"] or brut_r

    # 017 / 018 depuis le détail
    m_017, h_017 = parts["hs_aleatoires_montant"], parts["hs_aleatoires_heures"]
    m_018, h_018 = parts["hs_structurelles_montant"], parts["hs_structurelles_heures"]

    # 003 salaire rétabli : le brut auquel on rend ce que les absences ont
    # retiré, moins ce qui les a indemnisées (maintien). Sur le rejeu de juin,
    # 2026,41 + 93,93 + 13,39 = 2133,73 : le brut d'un mois sans absence.
    # Une absence injustifiée ne se reconstitue pas dans le rétabli (003) ;
    # elle reste dans la rémunération habituelle du mois complet (029).
    habituelle = max(
        brut_r, round(brut_r + absences.retenues - absences.compensations, 2)
    )
    retabli = max(brut_r, round(habituelle - absences.retenues_injustifiees, 2))
    if mois_incomplet and not absences.entree_sortie and heures_contrat_mois:
        # Entrée ou sortie sans ligne d'absence : la base payée est déjà
        # proratisée. On rend les heures manquantes au taux de chaque ligne —
        # 49 h payées sur 151,67 : le rétabli est le mois complet.
        manque = _manque_du_mois(payslip_data, heures_contrat_mois)
        retabli = round(retabli + manque, 2)
        habituelle = round(habituelle + manque, 2)
    # 028 / 029 : sans les éléments que l'absence n'affecte pas — les heures
    # sup aléatoires, payées comme travaillées — ni les indemnités de rupture.
    # Comme l'ancien logiciel, seulement un mois d'absence : sans absence, 028
    # et 029 suivent 001 et 003.
    hors_absence = (
        round(float(indemnites_rupture or 0) + m_017, 2)
        if absences.heures_absence > 0
        else 0.0
    )
    montant_002 = round(brut_r - float(indemnites_rupture or 0), 2)

    remus: List[RemunerationBlock] = [
        _rem_block(
            type_code="001",
            montant=brut_r,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
        _rem_block(
            type_code="002",
            montant=montant_002,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
        _rem_block(
            type_code="003",
            montant=retabli,
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
        _rem_block(
            type_code="010",
            montant=round(montant_010, 2),
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        ),
    ]
    if m_017 > 0 or h_017 > 0:
        remus.append(
            _rem_block(
                type_code="017",
                montant=m_017,
                heures=h_017,
                period_start=period_start,
                period_end=period_end,
                contrat_ref=contrat_ref,
            )
        )
    if m_018 > 0 or h_018 > 0:
        remus.append(
            _rem_block(
                type_code="018",
                montant=m_018,
                heures=h_018,
                period_start=period_start,
                period_end=period_end,
                contrat_ref=contrat_ref,
            )
        )
    # 028 ~ assiette CSG déclarée comme rémunération (Cegid = 001)
    remus.append(
        _rem_block(
            type_code="028",
            montant=round(brut_r - hors_absence, 2),
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        )
    )
    # 029 suit le rétabli quand distinct, sinon le brut (comportement Cegid)
    remus.append(
        _rem_block(
            type_code="029",
            montant=round(habituelle - hors_absence, 2),
            period_start=period_start,
            period_end=period_end,
            contrat_ref=contrat_ref,
        )
    )

    # Activités. Les jours calendaires du plafond (unité 40) se rattachent au
    # brut (001, CCH-12) et se comptent sur la période d'emploi du mois, moins
    # les jours d'arrêt et de suspension non rémunérée. Les heures se
    # rattachent au salaire chômage (002, CCH-11) : travail rémunéré (01) et
    # durée d'absence partiellement ou pas rémunérée (02).
    if jours_plafond is not None:
        days = max(0, int(jours_plafond))
    else:
        days = jours_calendaires(period_start, period_end)
        if days <= 0:
            try:
                year, month = [int(x) for x in period.split("-")[:2]]
                days = calendar.monthrange(year, month)[1]
            except Exception:
                days = 30
    heures_activite = round(
        (parts["heures_base"] or 0)
        + parts["hs_structurelles_heures"]
        + parts["hs_aleatoires_heures"],
        2,
    )
    if heures_activite <= 0:
        heures_activite = round(
            _f(payslip_data.get("heures_remunerees"))
            or _f(payslip_data.get("heures_travaillees"))
            or 151.67,
            2,
        )
    heures_activite = round(heures_activite - absences.heures_non_payees, 2)
    if mesure_activite is not None:
        heures_activite = round(float(mesure_activite), 2)

    activites: List[Dict[str, Any]] = [
        {"type": "01", "mesure": float(days), "unite": "40", "remuneration": "001"},
        {"type": "01", "mesure": heures_activite, "unite": "", "remuneration": "002"},
    ]
    if absences.heures_absence > 0:
        activites.append(
            {
                "type": "02",
                "mesure": absences.heures_absence,
                "unite": "",
                "remuneration": "002",
            }
        )

    return RemunerationBuildResult(
        remunerations=remus,
        activites=activites,
        heures_activite=heures_activite,
        salaire_base=parts["salaire_base"],
        hs_structurelles_montant=m_018,
        hs_structurelles_heures=h_018,
        hs_aleatoires_montant=m_017,
        hs_aleatoires_heures=h_017,
        salaire_retabli=retabli,
    )
