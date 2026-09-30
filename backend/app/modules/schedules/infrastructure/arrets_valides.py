"""Arrêts validés des salariés sur une période (table `absence_requests`).

La validation d'un arrêt retype ses jours ouvrés en `arret_maladie`, mais pas
ses week-ends, repos et fériés : ils gardent leur type et ne portent que des
métadonnées d'arrêt, que la première sauvegarde du planning efface
(`schedules.domain.rules.merge_planned_entries` retire les clés serveur d'un
jour qui n'est pas une absence). La demande validée est donc la seule source
fiable des jours qu'un arrêt couvre. Sert à `conflits_arret.jours_en_conflit`.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Sequence

from app.core.database import supabase
from app.modules.schedules.domain.conflits_arret import est_un_arret


def _touche_la_periode(selected_days: Any, debut: date, fin: date) -> bool:
    for brut in selected_days or []:
        try:
            jour = date.fromisoformat(str(brut)[:10])
        except ValueError:
            continue
        if debut <= jour <= fin:
            return True
    return False


class ArretsValidesReader:
    def par_salarie(
        self, employee_ids: Sequence[str], debut: date, fin: date
    ) -> Dict[str, List[Dict[str, Any]]]:
        """`{employee_id: [{employee_id, type, status, selected_days}]}` : les arrêts
        validés dont un jour tombe dans [debut, fin].

        Le type se trie ici, en Python : filtrer sur l'enum PostgreSQL
        `absence_type` fait échouer toute la requête dès qu'un libellé du code
        manque à l'enum (07/09/2026, cf. `payslip_generator._stamp_source_absence_conges`).
        """
        ids = list(dict.fromkeys(str(e) for e in employee_ids if e))
        if not ids:
            return {}
        resp = (
            supabase.table("absence_requests")
            .select("employee_id, type, status, selected_days")
            .in_("employee_id", ids)
            .eq("status", "validated")
            .execute()
        )
        arrets: Dict[str, List[Dict[str, Any]]] = {}
        for ligne in resp.data or []:
            if not est_un_arret(ligne.get("type")):
                continue
            if not _touche_la_periode(ligne.get("selected_days"), debut, fin):
                continue
            arrets.setdefault(str(ligne.get("employee_id")), []).append(ligne)
        return arrets


arrets_valides_reader = ArretsValidesReader()

__all__ = ["ArretsValidesReader", "arrets_valides_reader"]
