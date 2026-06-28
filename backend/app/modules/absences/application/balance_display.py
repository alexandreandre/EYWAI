"""Conversion soldes domaine → listes API."""

from __future__ import annotations

from app.modules.absences.domain.cp_seniority import CpSenioritySettings
from app.modules.absences.domain.leave_policy import LeavePolicySettings


def _official_balance_row(row: dict[str, float]) -> dict[str, float]:
    """
    Ligne affichée RH / salarié : acquis = pris + restant (compteur paie cohérent).

    Les droits théoriques (embauche) et la reprise bulletin peuvent diverger ;
    seul le triplet pris + restant reflète le solde officiel utilisable.
    """
    pris = round(float(row.get("pris") or 0), 2)
    restant = round(max(0.0, float(row.get("solde") or 0)), 2)
    return {
        "acquired": round(restant + pris, 2),
        "taken": pris,
        "remaining": restant,
    }


def balances_to_api_list(
    soldes: dict[str, dict[str, float]],
    *,
    policy: LeavePolicySettings | None = None,
    cp_seniority: CpSenioritySettings | None = None,
) -> list[dict]:
    policy = policy or LeavePolicySettings()
    result: list[dict] = []

    if policy.cp_carryover_enabled:
        n1 = soldes.get("conges_payes_n1") or {}
        n = soldes.get("conges_payes_n") or {}
        n1_row = _official_balance_row(n1)
        n_row = _official_balance_row(n)
        result.append(
            {
                "type": "Congés Payés (période précédente)",
                **n1_row,
            }
        )
        result.append(
            {
                "type": "Congés Payés (période en cours)",
                **n_row,
            }
        )

    cp = _official_balance_row(soldes["conges_payes"])
    result.append(
        {
            "type": "Congés Payés",
            **cp,
        }
    )

    seniority_days = float(soldes.get("cp_seniority_days") or 0)
    if cp_seniority and cp_seniority.is_active and seniority_days > 0:
        anciennete = soldes.get("conges_payes_anciennete") or {}
        anc_row = _official_balance_row(anciennete)
        result.append(
            {
                "type": "Congés Payés (ancienneté)",
                **anc_row,
            }
        )

    frac_days = float(soldes.get("fractionnement_days") or 0)
    if frac_days > 0:
        result.append(
            {
                "type": "Congés Payés (fractionnement)",
                "acquired": frac_days,
                "taken": 0,
                "remaining": frac_days,
            }
        )

    rtt = _official_balance_row(soldes["rtt"])
    result.append(
        {
            "type": "RTT",
            **rtt,
        }
    )

    repos = _official_balance_row(soldes["repos_compensateur"])
    result.append(
        {
            "type": "Repos compensateur",
            **repos,
        }
    )
    mod = soldes.get("compte_modulation")
    if mod:
        mod_row = _official_balance_row(mod)
        result.append(
            {
                "type": "Compte modulation",
                **mod_row,
            }
        )
    result.append(
        {
            "type": "Événement familial",
            "acquired": 0,
            "taken": 0,
            "remaining": "selon événement",
        }
    )
    return result
