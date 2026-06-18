"""Énumérations domaine suivi IJSS."""

from typing import Literal

PeriodStatus = Literal["open", "partial", "reconciled", "closed"]
ExpectedLineStatus = Literal["pending", "partial", "ok", "variance", "justified"]
ReceivedSource = Literal["cpam_decompte", "bank_transfer", "manual"]
MatchConfidence = Literal["none", "weak", "medium", "strong", "manual"]
MatchStatus = Literal["unmatched", "matched", "disputed"]
ImportBatchType = Literal["bank_recap", "cpam_decompte_file", "cpam_api_sync"]
ImportBatchStatus = Literal["parsed", "previewed", "committed", "failed"]

IJSS_ELIGIBLE_ABSENCE_TYPES = frozenset(
    {
        "arret_maladie",
        "arret_at",
        "arret_paternite",
        "arret_maternite",
        "arret_maladie_pro",
    }
)
