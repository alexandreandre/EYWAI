"""Ce que le générateur lit pour ranger une prime de partage de la valeur.

Les règles sont dans `engine.ppv` ; ici, seulement les lectures :
- les PPV déjà versées dans l'année civile (variables des mois d'avant,
  reconnues par leur nature) : deux primes et 3 000 € par an au plus ;
- la rémunération moyenne des 12 mois précédant le versement (bulletins
  enregistrés) : la condition des 3 Smic ;
- l'accord d'intéressement de la société (`settings.ppv_accord_interessement`) :
  plafond porté à 6 000 €.

Rien n'est lu quand le mois n'a pas de PPV : les autres bulletins ne font pas
une lecture de plus.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.modules.monthly_inputs.domain.rules import est_saisie_retiree
from app.modules.payroll.engine.ppv import est_une_ppv

CLE_SAISIES = "ppv"
CLE_ACCORD_INTERESSEMENT = "ppv_accord_interessement"


def _est_une_ppv_saisie(row: Dict[str, Any]) -> bool:
    if row.get("sur_le_net") or est_saisie_retiree(row):
        return False
    return est_une_ppv(row.get("catalog_prime_id") or "", row.get("name"))


def _montant(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def donnees_ppv_du_mois(
    supabase: Any,
    employee_id: str,
    year: int,
    month: int,
    company_data: Optional[Dict[str, Any]],
    saisies_du_mois: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Les données de `engine.ppv.classer_ppv`, ou None sans PPV dans le mois."""
    if not any(_est_une_ppv_saisie(row) for row in saisies_du_mois or []):
        return None

    variables = (
        supabase.table("monthly_inputs")
        .select("year, month, name, amount, catalog_prime_id, sur_le_net, description")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .lt("month", month)
        .execute()
        .data
        or []
    )
    deja_versees: List[float] = [
        round(_montant(row.get("amount")), 2)
        for row in sorted(variables, key=lambda r: int(r.get("month") or 0))
        if _est_une_ppv_saisie(row) and _montant(row.get("amount")) > 0
    ]

    rang = year * 12 + month
    bulletins = (
        supabase.table("payslips")
        .select("year, month, salaire_brut:payslip_data->salaire_brut")
        .eq("employee_id", employee_id)
        .in_("year", [year - 1, year])
        .execute()
        .data
        or []
    )
    bruts = [
        _montant(b.get("salaire_brut"))
        for b in bulletins
        if rang - 12 <= int(b.get("year") or 0) * 12 + int(b.get("month") or 0) < rang
    ]
    moyenne = round(sum(bruts) / len(bruts), 2) if bruts else None

    reglages = (company_data or {}).get("settings")
    accord = bool(
        isinstance(reglages, dict) and reglages.get(CLE_ACCORD_INTERESSEMENT)
    )
    return {
        "deja_versees": deja_versees,
        "remuneration_mensuelle_moyenne": moyenne,
        "mois_de_remuneration": len(bruts),
        "accord_interessement": accord,
    }
