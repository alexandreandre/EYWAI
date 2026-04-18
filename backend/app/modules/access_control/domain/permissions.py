"""
Codes canoniques des permissions « Pack Talent » (Formation & Talents).

Alignés sur la catégorie catalogue `formation_talents` et le script SQL
`backend/db/seeds/pack_talent_permissions.sql`. Utiliser ces constantes
dans les garde-fous (`check_user_has_permission`, etc.).
"""

from __future__ import annotations

from enum import StrEnum


class FormationTalentsPermission(StrEnum):
    """Actions Pack Talent — codes = colonne `permissions.code` en base."""

    # Entretiens
    CREATE_INTERVIEW_TEMPLATE = "create_interview_template"
    CONDUCT_INTERVIEW = "conduct_interview"
    SEND_INTERVIEW_SIGNATURE = "send_interview_signature"

    # Objectifs & KPI
    CREATE_INDIVIDUAL_OBJECTIVE = "create_individual_objective"
    CREATE_SERVICE_OBJECTIVE = "create_service_objective"
    UPDATE_OBJECTIVE_MILESTONE = "update_objective_milestone"
    EVALUATE_OBJECTIVE = "evaluate_objective"
    CANCEL_OBJECTIVE = "cancel_objective"
    VIEW_OBJECTIVES_REPORTING = "view_objectives_reporting"
    EXPORT_OBJECTIVES_EXCEL = "export_objectives_excel"

    # Habilitations
    MANAGE_CERTIFICATION_REF = "manage_certification_ref"
    RECORD_CERTIFICATION = "record_certification"
    VIEW_ALL_CERTIFICATIONS = "view_all_certifications"
    EXPORT_CERTIFICATIONS_EXCEL = "export_certifications_excel"

    # Formations
    MANAGE_TRAINING_CATALOG = "manage_training_catalog"
    ENROLL_EMPLOYEE_TRAINING = "enroll_employee_training"
    VIEW_TRAINING_CATALOG = "view_training_catalog"
    MANAGE_TRAINING_BUDGET = "manage_training_budget"
    VIEW_BUDGET_ALERTS = "view_budget_alerts"
    VIEW_SPENDING_DETAIL = "view_spending_detail"

    # Compétences
    MANAGE_COMPETENCY_REF = "manage_competency_ref"
    EVALUATE_COMPETENCY = "evaluate_competency"
    VIEW_COMPETENCY_MATRIX = "view_competency_matrix"
    EXPORT_COMPETENCY_MATRIX = "export_competency_matrix"


FORMATION_TALENTS_CATEGORY_CODE = "formation_talents"
