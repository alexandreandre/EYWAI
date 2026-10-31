"""Un mois à deux contrats : un individu, deux contrats, deux versements (D3.2).

Un CDD finit le 10/11, un nouveau contrat commence le 17/11 : novembre a un
bulletin par contrat (D3). Chaque bulletin se construit seul, comme un mois
ordinaire ; `fusionner` réunit ensuite les deux sous un individu, et
`evenements_du_contrat` donne à chaque contrat ses arrêts et sa sortie.

Cahier technique DSN 2026.1 : numéro de contrat unique par individu (40.009
CCH-12), numéro de versement distinct (50.003 CCH-11 et CCH-12), numéro du
contrat sur chaque base quand il y en a plusieurs (78.006), identifiant
d'affiliation unique par salarié (70.012 CCH-11). Spécification :
docs/superpowers/specs/2026-10-31-dsn-deux-contrats-design.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from app.modules.dsn_import.domain.model import ContratBlock, IndividuBlock

#: Ce que l'export pose pour refaire le SMIC de la réduction générale d'un
#: bulletin qui ne le porte pas : le cumul d'heures du contrat de la fiche.
_REPLI_SMIC = ("smic_horaire_reduction", "heures_cumulees_avant")


def _jour(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def _touche(jours: list[date], debut: date, fin: date | None) -> bool:
    return bool(jours) and jours[-1] >= debut and (fin is None or jours[0] <= fin)


def evenements_du_contrat(
    evenements: Mapping[str, Any],
    debut: date,
    fin: date | None,
    *,
    contrat_de_la_fiche: bool = True,
) -> dict[str, Any]:
    """Les événements du mois qui reviennent au contrat [debut, fin].

    Les arrêts qui touchent ses dates, la sortie qui y tombe (la dernière),
    le taux PAS reçu ; le repli du SMIC de réduction pour le seul contrat de
    la fiche (fin ouverte).
    """
    resultat = {
        cle: valeur
        for cle, valeur in evenements.items()
        if cle not in ("absences_dsn", "sortie_dsn", "sorties_dsn")
        and (contrat_de_la_fiche or cle not in _REPLI_SMIC)
    }
    absences = [
        a
        for a in evenements.get("absences_dsn") or []
        if isinstance(a, dict)
        and _touche(sorted(j for j in map(_jour, a.get("selected_days") or []) if j), debut, fin)
    ]
    if absences:
        resultat["absences_dsn"] = absences
    sorties = [
        s
        for s in evenements.get("sorties_dsn") or []
        if isinstance(s, dict)
        and (jour := _jour(s.get("last_working_day")))
        and debut <= jour
        and (fin is None or jour <= fin)
    ]
    if sorties:
        resultat["sortie_dsn"] = max(sorties, key=lambda s: str(s.get("last_working_day")))
    return resultat


def _decaler_affiliations(ancien: ContratBlock, nouveau: ContratBlock) -> None:
    """Les identifiants d'affiliation de l'ancien contrat passent après ceux du
    nouveau ; ses bases 31 et ses cotisations les suivent."""
    pris = [int(a.identifiant_affiliation) for a in nouveau.affiliations if a.identifiant_affiliation.isdigit()]
    decalage = max(pris, default=0)
    if not decalage:
        return
    nouveaux: dict[str, str] = {}
    for affiliation in ancien.affiliations:
        if not affiliation.identifiant_affiliation.isdigit():
            continue
        nouvel_id = str(int(affiliation.identifiant_affiliation) + decalage)
        nouveaux[affiliation.identifiant_affiliation] = nouvel_id
        affiliation.identifiant_affiliation = nouvel_id
        if affiliation.rubriques.get("S21.G00.70.012"):
            affiliation.rubriques["S21.G00.70.012"] = nouvel_id
    for versement in ancien.versements:
        for base in versement.bases_assujetties:
            cite = (base.rubriques or {}).get("S21.G00.78.005")
            if cite in nouveaux:
                base.rubriques["S21.G00.78.005"] = nouveaux[cite]
        for cotisation in versement.cotisations_individuelles:
            if cotisation.identifiant_affiliation in nouveaux:
                cotisation.identifiant_affiliation = nouveaux[cotisation.identifiant_affiliation]


def fusionner(ancien: IndividuBlock, nouveau: IndividuBlock) -> IndividuBlock:
    """L'individu du nouveau contrat, avec l'ancien contrat avant le sien.

    Chacun garde son versement, numéroté (01 l'ancien, 02 le nouveau) ; chaque
    base cite son contrat. Deux contrats sous le même numéro ne se distinguent
    pas : `ValueError`.
    """
    contrat_ancien, contrat_nouveau = ancien.contrats[0], nouveau.contrats[0]
    if contrat_ancien.numero_contrat == contrat_nouveau.numero_contrat:
        raise ValueError(
            f"Deux contrats sous le même numéro DSN ({contrat_nouveau.numero_contrat}) "
            f"pour le NIR {nouveau.nir} : la déclaration ne peut pas les distinguer (40.009)"
        )
    _decaler_affiliations(contrat_ancien, contrat_nouveau)
    numero = 0
    for contrat in (contrat_ancien, contrat_nouveau):
        for versement in contrat.versements:
            numero += 1
            versement.rubriques["S21.G00.50.003"] = f"{numero:02d}"
            for base in versement.bases_assujetties:
                if base.rubriques:
                    base.rubriques["S21.G00.78.006"] = contrat.numero_contrat
    nouveau.contrats = [contrat_ancien, contrat_nouveau]
    for cle in ("_cot_sal", "_cot_pat"):
        total = float(ancien.rubriques.get(cle) or 0) + float(nouveau.rubriques.get(cle) or 0)
        nouveau.rubriques[cle] = f"{total:.2f}"
    return nouveau
