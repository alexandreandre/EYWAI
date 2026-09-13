"""Salaire de base mensuel sur lequel un bulletin déjà généré a été établi.

Sert au rappel de salaire : quand une revalorisation est enregistrée après
coup, seuls les mois réellement payés à l'ancien taux sont à rappeler. Le
bulletin porte cette information dans `parametres.salaire_base_mensuel`
depuis le 13/09/2026 ; pour les bulletins antérieurs, on relit la ligne
« Salaire de base » (taux horaire × heures mensuelles de base).

Sans cette lecture, Demory (Colorplast) se voyait rappeler 16,69 € en
juillet pour un juin déjà payé au SMIC revalorisé — et chaque bulletin
suivant l'aurait rappelé à nouveau.
"""

from __future__ import annotations

from typing import Any, Mapping

from . import legal_constants as lc


def heures_base_mensuelles(duree_hebdo: Any) -> float:
    """Heures mensuelles payées au taux de base : 151,67 à temps plein, au
    prorata en deçà de 35 h. Au-delà de 35 h, le surplus est structurel et
    payé majoré, hors du salaire de base mensuel."""
    try:
        duree = float(duree_hebdo or 0)
    except (TypeError, ValueError):
        duree = 0.0
    if duree <= 0:
        duree = lc.DUREE_LEGALE_HEBDO
    return round(min(duree, lc.DUREE_LEGALE_HEBDO) * 52 / 12, 2)


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def base_mensuelle_du_bulletin(
    payslip_data: Mapping[str, Any] | None, heures_base: float | None
) -> float | None:
    """Salaire de base mensuel appliqué par ce bulletin, ou None si illisible.

    Un mois d'entrée ou de sortie paie moins que le mois complet : on
    reconstruit le mensuel depuis le taux horaire plutôt que de lire le
    montant payé. Sans taux (forfait), le montant de la ligne fait foi.
    """
    if not isinstance(payslip_data, Mapping):
        return None
    parametres = payslip_data.get("parametres") or {}
    memorise = _nombre(parametres.get("salaire_base_mensuel")) if isinstance(parametres, Mapping) else None
    if memorise and memorise > 0:
        return round(memorise, 2)

    lignes = payslip_data.get("calcul_du_brut") or []
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            continue
        libelle = str(ligne.get("libelle") or "").strip().lower()
        if not libelle.startswith("salaire de base"):
            continue
        taux = _nombre(ligne.get("taux"))
        if taux and taux > 0 and heures_base:
            return round(taux * heures_base, 2)
        gain = _nombre(ligne.get("gain"))
        if gain and gain > 0:
            return round(gain, 2)
        return None
    return None
