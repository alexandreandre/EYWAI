"""Constantes métier prêts employeur."""

from decimal import Decimal

DECLARATION_2062_THRESHOLD_EUR = Decimal("5000.00")

LOAN_STATUSES = frozenset(
    {"draft", "active", "suspended", "repaid", "cancelled", "defaulted"}
)

INSTALLMENT_STATUSES = frozenset({"pending", "paid", "skipped"})

DEFAULT_LEGAL_INTEREST_RATE = Decimal("0.0352")
