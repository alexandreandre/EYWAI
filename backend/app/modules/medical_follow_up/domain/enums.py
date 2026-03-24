# app/modules/medical_follow_up/domain/enums.py
"""Types de visite, déclencheurs et statuts (alignés migration 35 / legacy)."""

from enum import StrEnum


class VisitType(StrEnum):
    """Types de visite médicale."""

    APTITUDE_SIR_AVANT_AFFECTATION = "aptitude_sir_avant_affectation"
    VIP_AVANT_AFFECTATION_MINEUR_NUIT = "vip_avant_affectation_mineur_nuit"
    REPRISE = "reprise"
    VIP = "vip"
    SIR = "sir"
    MI_CARRIERE_45 = "mi_carriere_45"
    DEMANDE = "demande"


class ObligationStatus(StrEnum):
    """Statut d'une obligation."""

    A_FAIRE = "a_faire"
    PLANIFIEE = "planifiee"
    REALISEE = "realisee"
    ANNULEE = "annulee"


class TriggerType(StrEnum):
    """Déclencheur de l'obligation (ex. poste_sir, periodicite_vip)."""

    POSTE_SIR = "poste_sir"
    NUIT_MINEUR = "nuit_mineur"
    ARRET_LONG = "arret_long"
    AGE_45 = "age_45"
    PERIODICITE_VIP = "periodicite_vip"
    EMBANCHE = "embauche"
    PERIODICITE_SIR = "periodicite_sir"
    DEMANDE = "demande"
