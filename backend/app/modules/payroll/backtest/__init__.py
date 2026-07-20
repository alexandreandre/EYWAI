"""Backtest paie autonome — comparaison EYWAI vs référentiel Cegid."""

from app.modules.payroll.backtest.comparator import compare_bulletins
from app.modules.payroll.backtest.models import (
    DiscrepancyLine,
    DiscrepancyReport,
    EmployeeConvergenceStatus,
    ReferenceBulletin,
    ReferenceRubricLine,
    RemediationColor,
    RemediationProposal,
    Verdict,
)
from app.modules.payroll.backtest.reference_parser import parse_cegid_text
from app.modules.payroll.backtest.thresholds import ThresholdConfig, default_thresholds

__all__ = [
    "DiscrepancyLine",
    "DiscrepancyReport",
    "EmployeeConvergenceStatus",
    "ReferenceBulletin",
    "ReferenceRubricLine",
    "RemediationColor",
    "RemediationProposal",
    "ThresholdConfig",
    "Verdict",
    "compare_bulletins",
    "default_thresholds",
    "parse_cegid_text",
]
