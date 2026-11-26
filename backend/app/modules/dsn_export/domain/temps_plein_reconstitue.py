"""S21.G00.40.044 « Salarié à temps partiel cotisant à temps plein ».

Cahier technique DSN 2026.1 : « 01 - pour la vieillesse régime de base »,
« 02 - pour la vieillesse régime de base et la retraite complémentaire ».
La valeur se lit sur le réglage de retraite progressive de la fiche
(`specificites_paie.retraite_progressive`, engine/retraite_progressive).

La complémentaire seule (forfait jours au-delà de 1,7 SMIC, avenant 23 de
l'Agirc-Arrco) n'a pas de valeur dans le cahier 2026 : la rubrique reste vide
et l'aperçu le dit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.modules.payroll.engine.retraite_progressive import lire_reglage

VIEILLESSE_DE_BASE = "01"
BASE_ET_COMPLEMENTAIRE = "02"


@dataclass(frozen=True)
class TempsPleinDeclare:
    code: Optional[str] = None
    avertissement: Optional[str] = None


def salarie_cotisant_a_temps_plein(specificites_paie: Any, period: str) -> TempsPleinDeclare:
    """La valeur de S21.G00.40.044 pour le mois « AAAA-MM », ou rien."""
    try:
        reglage = lire_reglage(specificites_paie)
    except ValueError as erreur:
        return TempsPleinDeclare(avertissement=str(erreur))
    try:
        annee, mois = (int(x) for x in str(period)[:7].split("-"))
    except ValueError:
        return TempsPleinDeclare()
    if reglage is None or not reglage.couvre(annee, mois):
        return TempsPleinDeclare()
    if reglage.vieillesse_temps_plein and reglage.complementaire_temps_plein:
        return TempsPleinDeclare(BASE_ET_COMPLEMENTAIRE)
    if reglage.vieillesse_temps_plein:
        return TempsPleinDeclare(VIEILLESSE_DE_BASE)
    if reglage.complementaire_temps_plein:
        return TempsPleinDeclare(
            avertissement=(
                "retraite complémentaire seule sur un temps plein : S21.G00.40.044 n'a pas de "
                "valeur pour ce cas au cahier 2026, rubrique laissée vide (à vérifier avec l'Agirc-Arrco)"
            )
        )
    return TempsPleinDeclare()
