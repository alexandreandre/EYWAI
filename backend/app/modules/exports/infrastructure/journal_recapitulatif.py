"""Journal de paie récapitulatif, au format de Quadra (Elsa, 17/11).

Le modèle du cabinet (journal de paie de Zone 404, octobre 2026) cumule le mois
par rubrique, tous salariés confondus : la rémunération jusqu'au brut, chaque
cotisation avec sa base et ses parts salariale et patronale, le total des
retenues, le net imposable, ce qui suit le net imposable (frais, CSG/CRDS non
déductible, impôt, saisies), le net à payer, puis l'effectif payé.

Les lignes sont celles des bulletins enregistrés (les mêmes que le bulletin
imprimé, sans la ligne agrégée « Autres contributions » : le journal garde le
détail, comme Quadra). Rien n'est recalculé.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from app.modules.payroll.documents.bulletin_view import (
    RUBRIQUE_APRES_NET_IMPOSABLE,
    _ligne_brut,
    _lignes_hors_brut,
)

EN_TETES = ["Libellé", "Montant salarial", "Base", "Charges patronales"]

REMUNERATION, COTISATIONS, APRES_NET = "remuneration", "cotisations", "apres_net"

# « Absence maladie du 12/10/26 », « Congés payés du 05/10 au 09/10 » : la
# rubrique, sans ses dates, pour cumuler les salariés.
_DATES = re.compile(r"\s+(du|le|au|à partir du)\s+\d{1,2}/\d{1,2}.*$", re.IGNORECASE)


def _rubrique(libelle: str) -> str:
    libelle = str(libelle or "").strip()
    if libelle.endswith(" *"):
        libelle = libelle[:-2]
    return _DATES.sub("", libelle).strip() or libelle


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def lignes_du_bulletin(bulletin: Dict[str, Any]) -> Iterable[Tuple[str, str, float, float, float]]:
    """(section, libellé, base, salarial, patronal) de chaque ligne du bulletin."""
    for source in ("calcul_du_brut", "details_conges", "details_absences"):
        for detail in bulletin.get(source) or []:
            if not isinstance(detail, dict):
                continue
            ligne = _ligne_brut(detail)
            yield REMUNERATION, _rubrique(ligne["libelle"]), _nombre(ligne["base"]), _nombre(ligne["montant_salarial"]), 0.0

    for rubrique in bulletin.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        apres = rubrique.get("code") == RUBRIQUE_APRES_NET_IMPOSABLE
        for ligne in rubrique.get("lignes") or []:
            if not isinstance(ligne, dict):
                continue
            salarial = _nombre(ligne.get("montant_salarial"))
            yield (
                APRES_NET if apres else COTISATIONS,
                _rubrique(ligne.get("libelle")),
                _nombre(ligne.get("base")),
                # Après le net imposable, une cotisation se retire du net : négative.
                -salarial if apres else salarial,
                _nombre(ligne.get("montant_patronal")),
            )

    for ligne in _lignes_hors_brut(bulletin):
        yield APRES_NET, _rubrique(ligne["libelle"]), _nombre(ligne["base"]), _nombre(ligne["montant_salarial"]), 0.0

    impot = (bulletin.get("synthese_net") or {}).get("impot_prelevement_a_la_source") or {}
    if isinstance(impot, dict) and _nombre(impot.get("montant")):
        yield APRES_NET, "Prélèvement à la source", _nombre(impot.get("base")), -_nombre(impot.get("montant")), 0.0


def _arrondi(valeur: float) -> float | None:
    valeur = round(valeur, 2)
    return valeur if valeur else None


def journal_recapitulatif(bulletins: List[Dict[str, Any]], nb_salaries: int) -> List[Dict[str, Any]]:
    """Les lignes du journal, dans l'ordre du modèle de Quadra."""
    cumuls: Dict[str, Dict[str, List[float]]] = {REMUNERATION: {}, COTISATIONS: {}, APRES_NET: {}}
    brut = net_imposable = net_a_payer = 0.0
    for bulletin in bulletins:
        if not isinstance(bulletin, dict):
            continue
        brut += _nombre(bulletin.get("salaire_brut"))
        net_imposable += _nombre((bulletin.get("synthese_net") or {}).get("net_imposable"))
        net_a_payer += _nombre(bulletin.get("net_a_payer"))
        for section, libelle, base, salarial, patronal in lignes_du_bulletin(bulletin):
            if not (base or salarial or patronal):
                continue
            cumul = cumuls[section].setdefault(libelle, [0.0, 0.0, 0.0])
            cumul[0] += base
            cumul[1] += salarial
            cumul[2] += patronal

    def section(nom: str) -> List[Dict[str, Any]]:
        return [
            {
                "Libellé": libelle,
                "Montant salarial": _arrondi(salarial),
                "Base": _arrondi(base),
                "Charges patronales": _arrondi(patronal),
            }
            for libelle, (base, salarial, patronal) in cumuls[nom].items()
            if round(salarial, 2) or round(patronal, 2)
        ]

    def total(libelle: str, salarial: float, patronal: float | None = None) -> Dict[str, Any]:
        return {
            "Libellé": libelle,
            "Montant salarial": round(salarial, 2),
            "Base": None,
            "Charges patronales": round(patronal, 2) if patronal is not None else None,
        }

    retenues_salariales = sum(c[1] for c in cumuls[COTISATIONS].values())
    charges_patronales = sum(c[2] for c in cumuls[COTISATIONS].values()) + sum(
        c[2] for c in cumuls[APRES_NET].values()
    )
    return [
        *section(REMUNERATION),
        total("SALAIRE BRUT", brut),
        *section(COTISATIONS),
        total("TOTAL DES RETENUES", retenues_salariales, charges_patronales),
        total("NET IMPOSABLE", net_imposable),
        *section(APRES_NET),
        total("NET A PAYER", net_a_payer),
        {"Libellé": f"Salariés payés sur la période : {nb_salaries}", "Montant salarial": None, "Base": None, "Charges patronales": None},
    ]
