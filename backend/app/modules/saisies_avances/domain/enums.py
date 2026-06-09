"""
Types et énumérations du domaine saisies et avances.

Alignés sur les schémas legacy (schemas.saisies_avances).
À migrer ici en propre lors du basculement.
"""

from typing import Literal

# Saisies sur salaire
SalarySeizureType = Literal["saisie_arret", "pension_alimentaire", "atd", "satd"]
SalarySeizureStatus = Literal["active", "suspended", "closed"]
CalculationMode = Literal["fixe", "pourcentage", "barème_legal"]

# Avances / acomptes sur salaire et acomptes sur prime
AdvanceType = Literal["avance_salaire", "acompte_salaire", "acompte_prime"]
SalaryAdvanceStatus = Literal["pending", "approved", "rejected", "paid"]
RepaymentMode = Literal["single", "multiple"]
PaymentMethod = Literal["virement", "cheque", "especes"]

DEFAULT_ACCOUNTING_ACCOUNTS: dict[str, str] = {
    "avance_salaire": "4252",
    "acompte_salaire": "4251",
    "acompte_prime": "4253",
}

# Constantes métier (à centraliser ici après migration)
AUTO_APPROVAL_THRESHOLD_EUR = 100
BUCKET_ADVANCE_PAYMENTS = "advance_payments"
MAX_ADVANCE_DAYS = 10
MAX_ADVANCE_NET_RATIO = 0.5
