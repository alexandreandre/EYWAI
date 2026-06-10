export type PayrollGenerateEmployee = {
  id: string;
  first_name: string;
  last_name: string;
  payroll_eligible?: boolean | null;
  missing_payroll_fields?: string[] | null;
  employment_status?: string | null;
};
