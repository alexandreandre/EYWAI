from typing import List, Literal

from pydantic import BaseModel

SeveriteAnomalie = Literal["bloquant", "avertissement"]


class AnomaliePayslipItem(BaseModel):
    employee_id: str
    employee_name: str
    payslip_id: str
    type: str
    severite: SeveriteAnomalie
    message: str
    valeur_detectee: str
    suggestion_correction: str


class PayslipsAnomaliesReport(BaseModel):
    year: int
    month: int
    total_bulletins: int
    bulletins_avec_anomalies: int
    anomalies: List[AnomaliePayslipItem]
