export type PayrollGenerateEmployee = {
  id: string;
  first_name: string;
  last_name: string;
  payroll_eligible?: boolean | null;
  missing_payroll_fields?: string[] | null;
  employment_status?: string | null;
  /** Dernier jour travaillé (sortie la plus récente) : un parti n'apparaît que sur ses mois de présence. */
  exit_last_working_day?: string | null;
};
