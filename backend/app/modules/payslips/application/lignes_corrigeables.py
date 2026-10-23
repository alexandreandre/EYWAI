"""Les lignes d'un bulletin et ce qui s'y corrige, pour la carte « Corriger une ligne »."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_en_attente_du_bulletin,
    lignes_corrigeables,
)
from app.modules.payslips.application.dto import PayslipNotFoundError

_CHAMPS_EN_ATTENTE = ("saisie_id", "ligne", "libelle", "motif", "raison")


def lire_lignes_corrigeables(payslip_id: str) -> dict[str, Any]:
    reponse = (
        supabase.table("payslips").select("payslip_data").eq("id", payslip_id).maybe_single().execute()
    )
    if not reponse or not reponse.data:
        raise PayslipNotFoundError("Bulletin non trouvé")
    donnees = reponse.data.get("payslip_data") or {}
    return {
        "lignes": [ligne.en_dict() for ligne in lignes_corrigeables(donnees)],
        "en_attente": [
            {cle: entree.get(cle) for cle in _CHAMPS_EN_ATTENTE}
            for entree in corrections_en_attente_du_bulletin(donnees)
        ],
    }
