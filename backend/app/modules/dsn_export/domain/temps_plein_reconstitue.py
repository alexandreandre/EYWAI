"""S21.G00.40.044 « Salarié à temps partiel cotisant à temps plein ».

Cahier technique DSN 2026.1 : « 01 - pour la vieillesse régime de base »,
« 02 - pour la vieillesse régime de base et la retraite complémentaire ».
La valeur se lit sur le bulletin : les lignes de surcotisation que le moteur a
réellement posées (engine/retraite_progressive). Le réglage de la fiche
(`specificites_paie.retraite_progressive`) ne suffit pas : au forfait jours
au-delà de 1,7 SMIC, ou sur un brut nul, le moteur ne pose rien, et déclarer la
rubrique annoncerait un temps plein sans base 22 ni 24.

La complémentaire seule (forfait jours au-delà de 1,7 SMIC, avenant 23 de
l'Agirc-Arrco) n'a pas de valeur dans le cahier 2026 : la rubrique reste vide
et l'aperçu le dit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.modules.payroll.engine.retraite_progressive import COMPLEMENTAIRE, VIEILLESSE_DE_BASE, lire_reglage

VIEILLESSE_DE_BASE_CODE = "01"
BASE_ET_COMPLEMENTAIRE = "02"

_IDS_VIEILLESSE = frozenset(s for _, s, _ in VIEILLESSE_DE_BASE)
_IDS_COMPLEMENTAIRE = frozenset(s for _, s, _ in COMPLEMENTAIRE)


@dataclass(frozen=True)
class TempsPleinDeclare:
    code: Optional[str] = None
    avertissement: Optional[str] = None


def _poses(lignes: Iterable[Any], ids: frozenset) -> bool:
    return any(
        isinstance(l, dict)
        and str(l.get("coti_id") or "") in ids
        and (float(l.get("montant_salarial") or 0.0) or float(l.get("montant_patronal") or 0.0))
        for l in lignes or ()
    )


def salarie_cotisant_a_temps_plein(
    specificites_paie: Any, period: str, lignes_du_bulletin: Iterable[Any]
) -> TempsPleinDeclare:
    """La valeur de S21.G00.40.044 pour le mois « AAAA-MM », ou rien.

    ``lignes_du_bulletin`` : les lignes de cotisation du bulletin du mois.
    """
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
    lignes = list(lignes_du_bulletin or ())
    vieillesse = _poses(lignes, _IDS_VIEILLESSE)
    complementaire = _poses(lignes, _IDS_COMPLEMENTAIRE)
    if vieillesse and complementaire:
        return TempsPleinDeclare(BASE_ET_COMPLEMENTAIRE)
    if vieillesse:
        return TempsPleinDeclare(VIEILLESSE_DE_BASE_CODE)
    if complementaire:
        return TempsPleinDeclare(
            avertissement=(
                "retraite complémentaire seule sur un temps plein : S21.G00.40.044 n'a pas de "
                "valeur pour ce cas au cahier 2026, rubrique laissée vide (à vérifier avec l'Agirc-Arrco)"
            )
        )
    return TempsPleinDeclare(
        avertissement=(
            "retraite progressive sur la fiche, mais aucune surcotisation au bulletin du mois "
            "(forfait jours au-delà de 1,7 SMIC, brut nul ou aucune cotisation cochée) : "
            "S21.G00.40.044 non déclarée"
        )
    )
