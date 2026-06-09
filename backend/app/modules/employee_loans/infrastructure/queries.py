"""Constantes requêtes Supabase prêts employeur."""

TABLE_EMPLOYEE_LOANS = "employee_loans"
TABLE_EMPLOYEE_LOAN_INSTALLMENTS = "employee_loan_installments"
TABLE_EMPLOYEE_LOAN_REPAYMENTS = "employee_loan_repayments"

SELECT_LOAN_WITH_EMPLOYEE = (
    "*, employee:employees(id, first_name, last_name)"
)
