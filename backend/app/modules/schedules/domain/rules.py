"""
Règles métier pures du module schedules (forfait jour, normalisation calendrier).

Cible de migration : logique actuellement dans api/routers/schedules.py
(is_forfait_jour, normalize_planned_calendar_for_forfait_jour,
normalize_actual_hours_for_forfait_jour). Aucune I/O, pas de dépendance FastAPI/DB.
"""

from typing import Any, Dict, List


from app.shared.domain.absence_calendar import (
    ABSENCE_CALENDAR_TYPES,
    SERVER_OWNED_ABSENCE_KEYS,
    is_absence_day,
    strip_server_owned_keys,
)
from app.shared.domain.employment_rules import is_forfait_jour as is_forfait_jour


def normalize_planned_calendar_for_forfait_jour(
    calendrier_prevu: List[Dict[str, Any]], employee_statut: str | None
) -> List[Dict[str, Any]]:
    """
    Normalise les valeurs heures_prevues pour les employés en forfait jour.
    Convertit les valeurs > 0 en 1, et les valeurs 0 ou null en 0.
    """
    if not is_forfait_jour(employee_statut):
        return calendrier_prevu

    normalized = []
    for entry in calendrier_prevu:
        normalized_entry = entry.copy()
        heures_prevues = entry.get("heures_prevues")

        if heures_prevues is None:
            normalized_entry["heures_prevues"] = 0
        elif isinstance(heures_prevues, (int, float)):
            normalized_entry["heures_prevues"] = 1 if heures_prevues > 0 else 0
        else:
            normalized_entry["heures_prevues"] = 0

        normalized.append(normalized_entry)

    return normalized


def coerce_jour(raw: Any) -> int | None:
    """Normalise un numéro de jour du mois en int, ou None s'il est illisible.

    Des `jour` en chaîne existent en base (imports historiques) :
    `calendar_generation_rules.build_month_calendrier_prevu` s'en défend déjà
    explicitement. Sans normalisation, une même journée existe deux fois dans
    la fusion et le tri lève un TypeError sur tout le mois.
    """
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        jour = int(raw)
    except (TypeError, ValueError):
        return None
    return jour if 1 <= jour <= 31 else None


def merge_planned_entries(
    existing: List[Dict[str, Any]] | None,
    incoming: List[Dict[str, Any]],
    *,
    preserve_absence_days: bool = False,
    warnings: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Fusionne le calendrier entrant sur le calendrier stocké, jour par jour.

    Le payload d'un client ne porte souvent que ``jour``/``type``/
    ``heures_prevues`` : remplacer le mois effacerait les métadonnées
    d'absence (nature d'arrêt, subrogation, historique) posées par la
    validation d'absence. On part donc de l'entrée stockée et on superpose
    uniquement les champs fournis.

    Les clés de ``SERVER_OWNED_ABSENCE_KEYS`` ne sont **jamais** reprises du
    payload : elles ne viennent que de l'entrée stockée. En contrepartie, un
    jour dont le type résultant n'est plus un type d'absence les perd : sans
    cela il garderait ``origine="absence"`` et resterait gelé à vie contre les
    régénérations, sans aucun moyen de le débloquer depuis l'interface.

    Enfin, la fusion porte sur **tout le mois** et non sur les seuls jours
    cités : un jour stocké absent du payload est conservé tel quel, sinon un
    payload partiel ferait disparaître une absence validée. La sortie est
    triée par jour, les `jour` étant normalisés en int des deux côtés et les
    entrées inexploitables ignorées — plutôt que de faire échouer tout le mois.

    Deux modes, selon l'intention de l'appelant :
    - édition délibérée (défaut) : requalifier un jour d'absence validée est
      permis (et purge alors les clés serveur), mais **signalé** dans
      ``warnings`` (code ``absence_validee_requalifiee``) ;
    - écriture de masse (``preserve_absence_days=True`` — apply-model, copie
      de mois…) : un jour d'absence validée est conservé tel quel, le jour
      généré est écarté et signalé (code ``absence_validee_preservee``).
    """
    par_jour: Dict[int, Dict[str, Any]] = {}
    for e in existing or []:
        if not isinstance(e, dict):
            continue
        jour_stocke = coerce_jour(e.get("jour"))
        if jour_stocke is None:
            continue
        stocke = dict(e)
        stocke["jour"] = jour_stocke
        par_jour[jour_stocke] = stocke

    fusionnes: Dict[int, Dict[str, Any]] = dict(par_jour)
    for entree in incoming:
        if not isinstance(entree, dict):
            continue
        jour = coerce_jour(entree.get("jour"))
        if jour is None:
            continue
        stocke = par_jour.get(jour, {})
        type_entrant = entree.get("type")
        # Tout CHANGEMENT de type sur un jour d'absence validée compte comme
        # requalification — y compris vers un autre type d'absence : un modèle
        # « fermeture collective » en jours Congé ne doit pas transformer un
        # arrêt maladie en CP (maintien/IJSS perdus, CP débités) en silence.
        requalifie = (
            is_absence_day(stocke)
            and type_entrant is not None
            and type_entrant != stocke.get("type")
        )
        if requalifie and preserve_absence_days:
            if warnings is not None:
                warnings.append(
                    {
                        "jour": jour,
                        "code": "absence_validee_preservee",
                        "type_avant": stocke.get("type"),
                        "type_refuse": type_entrant,
                    }
                )
            continue
        base = dict(stocke)
        for cle, valeur in entree.items():
            if cle in SERVER_OWNED_ABSENCE_KEYS:
                continue
            if valeur is not None or cle in base:
                base[cle] = valeur
        base["jour"] = jour
        if requalifie:
            # Les métadonnées appartenaient à l'absence validée d'origine :
            # elles ne survivent pas à sa requalification (même vers un autre
            # type d'absence — un arret_type orphelin sur un jour de congé
            # n'a aucun sens).
            strip_server_owned_keys(base)
            if warnings is not None:
                warnings.append(
                    {
                        "jour": jour,
                        "code": "absence_validee_requalifiee",
                        "type_avant": stocke.get("type"),
                        "type_apres": type_entrant,
                    }
                )
        elif base.get("type") not in ABSENCE_CALENDAR_TYPES:
            # Filet : un jour non-absence ne porte jamais de clés serveur.
            strip_server_owned_keys(base)
        fusionnes[jour] = base
    return [fusionnes[jour] for jour in sorted(fusionnes)]


def normalize_actual_hours_for_forfait_jour(
    calendrier_reel: List[Dict[str, Any]], employee_statut: str | None
) -> List[Dict[str, Any]]:
    """
    Normalise les valeurs heures_faites pour les employés en forfait jour.
    Convertit les valeurs > 0 en 1, et les valeurs 0 ou null en 0.
    """
    if not is_forfait_jour(employee_statut):
        return calendrier_reel

    normalized = []
    for entry in calendrier_reel:
        normalized_entry = entry.copy()
        heures_faites = entry.get("heures_faites")

        if heures_faites is None:
            normalized_entry["heures_faites"] = 0
        elif isinstance(heures_faites, (int, float)):
            normalized_entry["heures_faites"] = 1 if heures_faites > 0 else 0
        else:
            normalized_entry["heures_faites"] = 0

        normalized.append(normalized_entry)

    return normalized
