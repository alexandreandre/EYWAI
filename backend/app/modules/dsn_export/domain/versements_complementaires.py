"""Versement trimestriel aux organismes complémentaires (prévoyance, santé).

FAQ DSN Organismes complémentaires (net-entreprises, V4 2023-10, p. 47-48) :
pour une échéance trimestrielle à terme échu, chaque DSN déclare les cotisations
individuelles du mois (blocs 78, 79, 81) ; celle du dernier mois du trimestre
porte en plus un bloc 20 et ses blocs 55 « pour le montant des cotisations dues
du trimestre », la somme des 55 égale au 20.005, 55.004 au format AAAATnn.
Pour un organisme complémentaire, 20.006 et 20.007 sont une « donnée non
exploitée, à renseigner au 01012000 ». Les modalités de paiement (mode, date)
sont celles du contrat : elles viennent du paramétrage repris du cabinet.
"""

from __future__ import annotations

import calendar
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from app.modules.dsn_export.domain.cotisation_mapping import BASE_PREVOYANCE
from app.modules.dsn_import.domain.model import EtablissementBlock, VersementOrganismeBlock

#: 20.006 et 20.007 d'un organisme complémentaire : donnée non exploitée.
DATE_NON_EXPLOITEE = "01012000"


def _annee_mois(period: str) -> tuple[int, int]:
    annee, mois = period.split("-")[:2]
    return int(annee), int(mois)


def est_fin_de_trimestre(period: str) -> bool:
    return _annee_mois(period)[1] % 3 == 0


def periode_d_affectation(period: str) -> str:
    """« 2026T04 » : le trimestre civil du mois déclaré."""
    annee, mois = _annee_mois(period)
    return f"{annee}T{(mois - 1) // 3 + 1:02d}"


def mois_precedents_du_trimestre(period: str) -> List[str]:
    """Les mois du trimestre avant celui déclaré, du plus ancien au plus récent."""
    annee, mois = _annee_mois(period)
    premier = mois - (mois - 1) % 3
    return [f"{annee}-{m:02d}" for m in range(premier, mois)]


def date_de_paiement(period: str, jour: Optional[str]) -> Optional[str]:
    """JJMMAAAA : le jour de paiement du contrat, le mois qui suit le trimestre."""
    try:
        jour_voulu = int(str(jour or "").strip())
    except ValueError:
        return None
    if jour_voulu < 1:
        return None
    annee, mois = _annee_mois(period)
    annee, mois = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    jour_reel = min(jour_voulu, calendar.monthrange(annee, mois)[1])
    return f"{jour_reel:02d}{mois:02d}{annee:04d}"


def cotisations_par_contrat(etab: EtablissementBlock) -> Dict[str, Decimal]:
    """Cotisations individuelles de prévoyance et de santé du mois, par contrat.

    Une cotisation de base 31 cite l'affiliation du salarié (78.005) ; le bloc
    70 de cette affiliation désigne le contrat par son ordre (70.013, l'ordre
    15.005 du bloc 15). Clé : cet ordre.
    """
    totaux: Dict[str, Decimal] = {}
    for individu in etab.individus:
        for contrat in individu.contrats:
            ordre_de = {
                a.identifiant_affiliation: str((a.rubriques or {}).get("S21.G00.70.013") or "")
                for a in contrat.affiliations
            }
            for versement in contrat.versements:
                for cotisation in versement.cotisations_individuelles:
                    rubriques = cotisation.rubriques or {}
                    if str(rubriques.get("_base") or "").split("#")[0] != BASE_PREVOYANCE:
                        continue
                    ordre = ordre_de.get(cotisation.identifiant_affiliation)
                    if not ordre:
                        continue
                    totaux[ordre] = totaux.get(ordre, Decimal("0")) + Decimal(
                        str(rubriques.get("S21.G00.81.004") or "0")
                    )
    return totaux


def bloc_versement_complementaire(
    versement: Mapping[str, Any],
    contrats: List[Mapping[str, Any]],
    montants: Mapping[str, Decimal],
    period: str,
) -> VersementOrganismeBlock:
    """Le bloc 20 d'un organisme et un bloc 55 par contrat de cet organisme,
    même à zéro (le cabinet les déclarait ainsi)."""
    organisme = str(versement.get("organisme") or "")
    affectation = periode_d_affectation(period)
    composants: List[Dict[str, str]] = []
    total = Decimal("0")
    for contrat in contrats:
        if str(contrat.get("organisme") or "") != organisme:
            continue
        montant = montants.get(str(contrat.get("ordre") or ""), Decimal("0")).quantize(
            Decimal("0.01")
        )
        total += montant
        composant = {
            "S21.G00.55.001": f"{montant:.2f}",
            "S21.G00.55.003": str(contrat.get("reference") or ""),
            "S21.G00.55.004": affectation,
        }
        if contrat.get("type_population"):
            composant["S21.G00.55.002"] = str(contrat["type_population"])
        composants.append(dict(sorted(composant.items())))
    rubriques: Dict[str, Any] = {
        "S21.G00.20.001": organisme,
        "S21.G00.20.002": str(versement.get("entite") or ""),
        "S21.G00.20.003": str(versement.get("bic") or ""),
        "S21.G00.20.004": str(versement.get("iban") or ""),
        "S21.G00.20.005": f"{total:.2f}",
        "S21.G00.20.006": DATE_NON_EXPLOITEE,
        "S21.G00.20.007": DATE_NON_EXPLOITEE,
        "S21.G00.20.008": str(versement.get("delegataire") or ""),
        "S21.G00.20.010": str(versement.get("mode") or "05"),
        "S21.G00.20.011": date_de_paiement(period, versement.get("jour_paiement")) or "",
    }
    rubriques = {k: v for k, v in rubriques.items() if v}
    rubriques["_composants_55"] = composants
    return VersementOrganismeBlock(
        identifiant=organisme,
        montant=float(total),
        rubriques=rubriques,
    )
