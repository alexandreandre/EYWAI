"""Conversion soldes domaine → listes API."""

from __future__ import annotations

from app.modules.absences.domain.cp_seniority import CpSenioritySettings
from app.modules.absences.domain.leave_policy import LeavePolicySettings


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
        result.append(
            {
                "type": "Congés Payés (période précédente)",
                "acquired": n1.get("acquis", 0),
                "taken": n1.get("pris", 0),
                "remaining": max(0.0, n1.get("solde", 0)),
            }
        )
        result.append(
            {
                "type": "Congés Payés (période en cours)",
                "acquired": n.get("acquis", 0),
                "taken": n.get("pris", 0),
                "remaining": max(0.0, n.get("solde", 0)),
            }
        )

    cp = soldes["conges_payes"]
    result.append(
        {
            "type": "Congés Payés",
            "acquired": cp["acquis"],
            "taken": cp["pris"],
            "remaining": cp["solde"],
        }
    )

    seniority_days = float(soldes.get("cp_seniority_days") or 0)
    if cp_seniority and cp_seniority.is_active and seniority_days > 0:
        anciennete = soldes.get("conges_payes_anciennete") or {}
        result.append(
            {
                "type": "Congés Payés (ancienneté)",
                "acquired": anciennete.get("acquis", seniority_days),
                "taken": anciennete.get("pris", 0),
                "remaining": anciennete.get("solde", seniority_days),
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

    rtt = soldes["rtt"]
    result.append(
        {
            "type": "RTT",
            "acquired": rtt["acquis"],
            "taken": rtt["pris"],
            "remaining": rtt["solde"],
        }
    )

    repos = soldes["repos_compensateur"]
    result.append(
        {
            "type": "Repos compensateur",
            "acquired": repos["acquis"],
            "taken": repos["pris"],
            "remaining": repos["solde"],
        }
    )
    mod = soldes.get("compte_modulation")
    if mod:
        result.append(
            {
                "type": "Compte modulation",
                "acquired": mod.get("acquis", 0),
                "taken": mod.get("pris", 0),
                "remaining": mod.get("solde", 0),
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
