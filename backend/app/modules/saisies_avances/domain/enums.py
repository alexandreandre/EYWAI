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

# Avances sur salaire
SalaryAdvanceStatus = Literal["pending", "approved", "rejected", "paid"]
RepaymentMode = Literal["single", "multiple"]
PaymentMethod = Literal["virement", "cheque", "especes"]

# Constantes métier (à centraliser ici après migration)
AUTO_APPROVAL_THRESHOLD_EUR = 100
BUCKET_ADVANCE_PAYMENTS = "advance_payments"
MAX_ADVANCE_DAYS = 10
