"""
Types et sources de crédits repos compensateur (domain).

À migrer/aligner avec la table repos_compensateur_credits (source: 'cor', 'rcr', 'manual').
"""

from __future__ import annotations

from typing import Literal

SourceCredit = Literal["cor", "rcr", "manual"]
