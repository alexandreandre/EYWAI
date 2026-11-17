"""Plafond annuel d'exonération des trajets domicile-travail : une alerte, pour
les deux générateurs.

Contrôle non bloquant qui n'altère jamais le bulletin. Il ne vivait que dans le
générateur des heures ; le forfait jours ne le faisait pas (audit du 17/11/2026,
test de parité).
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def alertes_plafond_transport(
    client: Any, employee_id: str, employee_data: dict[str, Any], year: int, month: int
) -> list[dict[str, Any]]:
    """Les alertes du plafond transport du mois, sur le cumul de l'année civile."""
    try:
        from app.modules.payroll.engine.baremes_loader import (
            assembler_baremes,
            charger_db_baremes,
        )
        from app.modules.payroll.engine.controles_convention import (
            controle_plafond_transport,
        )

        saisies_annee = (
            client.table("monthly_inputs")
            .select("amount, name, month")
            .eq("employee_id", employee_id)
            .eq("year", year)
            .execute()
            .data
            or []
        )

        # Le cumul s'arrête au mois du bulletin. Sans cette borne, un mois déjà
        # saisi mais pas encore payé était compté comme versé : sur un bulletin
        # de juillet, l'août saisi d'avance faisait annoncer 2 000 € versés au
        # lieu de 1 750 €.
        def _cumul_transport(jusqu_au_mois: int) -> float:
            return sum(
                float(s.get("amount") or 0)
                for s in saisies_annee
                if "transport" in (s.get("name") or "").lower()
                and int(s.get("month") or 0) <= jusqu_au_mois
            )

        cumul_transport = _cumul_transport(month)
        if cumul_transport <= 0:
            return []
        spec_transport = (employee_data.get("specificites_paie") or {}).get("transport") or {}
        abonnement = float(spec_transport.get("abonnement_mensuel_total") or 0)
        frais_pro = assembler_baremes(charger_db_baremes(client)).get("frais_pro")
        return list(
            controle_plafond_transport(
                cumul_transport,
                frais_pro,
                avec_abonnement_public=abonnement > 0,
                annee=year,
                cumul_mois_precedents=_cumul_transport(month - 1),
            )
        )
    except Exception as transport_err:  # noqa: BLE001 — contrôle non bloquant
        logger.warning(f"[WARNING] contrôle plafond transport: {transport_err}")
        return []
