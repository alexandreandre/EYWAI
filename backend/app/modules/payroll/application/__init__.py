# Couche application du module payroll (commands, queries, service, dto).
# Les routers et modules externes appellent exclusivement cette couche.

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.application.writer import generer_et_enregistrer_evenements

# Commandes bulletins
from app.modules.payroll.application.payslip_commands import (
    is_forfait_jour,
    process_payslip_generation,
    process_payslip_generation_forfait,
    save_edited_payslip,
    restore_payslip_version,
)

# Indemnités de sortie
from app.modules.payroll.application.indemnites_commands import (
    calculer_indemnites_sortie,
)

# Forfait jour (période + analyse)
from app.modules.payroll.application.forfait_commands import (
    definir_periode_de_paie_forfait,
    analyser_jours_forfait_du_mois,
)

# Documents de sortie (certificat, attestation, solde)
from app.modules.payroll.application.exit_document_commands import (
    get_exit_document_generator,
)

# Simulation et calcul inverse
from app.modules.payroll.application.simulation_commands import (
    run_reverse_calculation,
    creer_simulation_bulletin,
    comparer_simulation_reel,
    generer_scenarios_predefinis,
    get_simulated_payslip_generator,
)

# Exports (facade vers exports/)
from app.modules.payroll.application import export_service

__all__ = [
    "analyser_horaires_du_mois",
    "generer_et_enregistrer_evenements",
    "is_forfait_jour",
    "process_payslip_generation",
    "process_payslip_generation_forfait",
    "save_edited_payslip",
    "restore_payslip_version",
    "calculer_indemnites_sortie",
    "definir_periode_de_paie_forfait",
    "analyser_jours_forfait_du_mois",
    "get_exit_document_generator",
    "run_reverse_calculation",
    "creer_simulation_bulletin",
    "comparer_simulation_reel",
    "generer_scenarios_predefinis",
    "get_simulated_payslip_generator",
    "export_service",
]
