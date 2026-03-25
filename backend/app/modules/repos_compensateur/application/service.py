"""
Service applicatif repos_compensateur.

Orchestration via domain (règles COR + extraction HS) et infrastructure (DB, queries, providers).
Aucune logique métier lourde : délégation au domain et à l'infrastructure.
Comportement strictement identique.
"""
from __future__ import annotations

from app.modules.repos_compensateur.application.dto import CalculerCreditsResult
from app.modules.repos_compensateur.domain.entities import ReposCredit
from app.modules.repos_compensateur.domain.rules import (
    CONTINGENT_DEFAUT,
    HEURES_PAR_JOUR_REPOS,
    calculer_heures_cor_mois,
    cumuler_heures_hs_annee,
    get_taux_cor_par_effectif,
    heures_vers_jours,
)
from app.modules.repos_compensateur.infrastructure import (
    get_bulletins_par_mois_par_employe,
    get_company_effectif,
    get_employees_for_company,
    upsert_credit,
)


def calculer_credits_repos(
    year: int,
    month: int,
    target_company_id: str,
) -> CalculerCreditsResult:
    """
    Calcule les crédits COR pour tous les employés de l'entreprise sur le mois donné.
    Lit les bulletins via infrastructure ; règles COR et extraction HS dans le domain.
    """
    effectif = get_company_effectif(target_company_id)
    taux_cor = get_taux_cor_par_effectif(effectif)

    employees = get_employees_for_company(target_company_id)
    employee_ids = [e["id"] for e in employees]

    if not employee_ids:
        return CalculerCreditsResult(
            company_id=target_company_id,
            year=year,
            month=month,
            employees_processed=0,
            credits_created=0,
        )

    bulletins_par_employe = get_bulletins_par_mois_par_employe(
        target_company_id, year, employee_ids
    )

    credits_created = 0
    for emp in employees:
        emp_id = emp["id"]
        company_id_emp = emp["company_id"]
        bulletins_mois = bulletins_par_employe.get(emp_id, {})
        cumuls = cumuler_heures_hs_annee(bulletins_mois)
        cumul_mois = cumuls.get(month, 0.0)
        cumul_precedent = cumuls.get(month - 1, 0.0) if month > 1 else 0.0

        heures_cor = calculer_heures_cor_mois(
            cumul_hs_fin_mois=cumul_mois,
            cumul_hs_fin_mois_precedent=cumul_precedent,
            contingent=CONTINGENT_DEFAUT,
            taux_cor=taux_cor,
        )

        if heures_cor > 0:
            jours = heures_vers_jours(heures_cor, HEURES_PAR_JOUR_REPOS)
            credit = ReposCredit(
                employee_id=emp_id,
                company_id=company_id_emp,
                year=year,
                month=month,
                source="cor",
                heures=heures_cor,
                jours=jours,
            )
            if upsert_credit(credit):
                credits_created += 1

    return CalculerCreditsResult(
        company_id=target_company_id,
        year=year,
        month=month,
        employees_processed=len(employees),
        credits_created=credits_created,
    )


def recalculer_credits_repos_employe(
    employee_id: str, company_id: str, year: int
) -> int:
    """
    Recalcule les crédits COR pour un employé sur toute l'année.
    Upsert tous les mois (y compris 0). Comportement identique à l'ancien recalc_service.
    """
    try:
        effectif = get_company_effectif(company_id)
        taux_cor = get_taux_cor_par_effectif(effectif)

        bulletins_par_employe = get_bulletins_par_mois_par_employe(
            company_id, year, [employee_id]
        )
        bulletins_mois = bulletins_par_employe.get(employee_id, {})
        cumuls = cumuler_heures_hs_annee(bulletins_mois)

        credits_upserted = 0
        for month in range(1, 13):
            cumul_mois = cumuls.get(month, 0.0)
            cumul_precedent = cumuls.get(month - 1, 0.0) if month > 1 else 0.0

            heures_cor = calculer_heures_cor_mois(
                cumul_hs_fin_mois=cumul_mois,
                cumul_hs_fin_mois_precedent=cumul_precedent,
                contingent=CONTINGENT_DEFAUT,
                taux_cor=taux_cor,
            )
            jours = heures_vers_jours(heures_cor, HEURES_PAR_JOUR_REPOS)
            credit = ReposCredit(
                employee_id=employee_id,
                company_id=company_id,
                year=year,
                month=month,
                source="cor",
                heures=heures_cor,
                jours=jours,
            )
            if upsert_credit(credit):
                credits_upserted += 1

        return credits_upserted
    except Exception as e:
        print(f"[WARNING] recalculer_credits_repos_employe failed: {e}")
        return 0
