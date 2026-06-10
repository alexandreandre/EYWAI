import { useNavigate } from "react-router-dom";
import { AlertTriangle, FileText, FlaskConical } from "lucide-react";
import type { CompanyOverview, CompanyOverviewAlert } from "@/api/company";
import type { ComplianceAnchor } from "@/features/company/components/CompanyComplianceBand";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

const CC_COMPANY_CODE = "missing_company_collective_agreement";
const CC_EMPLOYEES_CODE = "employees_without_collective_agreement";
const JEI_NO_RD_CODE = "jei_enabled_no_rd_employees";
const JEI_RD_WITHOUT_COMPANY_CODE = "jei_rd_without_company_status";

function GenericAlertItem({ alert }: { alert: CompanyOverviewAlert }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" aria-hidden />
      <span>{alert.label}</span>
    </li>
  );
}

function CompanyCcAlert({
  onGoToPayrollSection,
}: {
  onGoToPayrollSection: (anchor?: ComplianceAnchor) => void;
}) {
  return (
    <Alert className="border-amber-200 bg-amber-50/80">
      <FileText className="h-4 w-4 text-amber-700" />
      <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm text-foreground">
          Convention collective non assignée à l&apos;entreprise.
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0 border-amber-300 bg-white hover:bg-amber-50"
          onClick={() => onGoToPayrollSection("convention-collective")}
        >
          Assigner dans Paramètres paie
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function JeiAlert({
  alert,
  onGoToPayrollSection,
}: {
  alert: CompanyOverviewAlert;
  onGoToPayrollSection: (anchor?: ComplianceAnchor) => void;
}) {
  const navigate = useNavigate();
  const preview = alert.employees ?? [];
  const remaining = (alert.count ?? preview.length) - preview.length;

  return (
    <Alert className="border-amber-200 bg-amber-50/80">
      <FlaskConical className="h-4 w-4 text-amber-700" />
      <AlertDescription className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-foreground">{alert.label}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0 border-amber-300 bg-white hover:bg-amber-50"
            onClick={() => onGoToPayrollSection("jei")}
          >
            Configurer dans Paramètres paie
          </Button>
        </div>
        {preview.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {preview.map((emp) => (
              <li key={emp.id} className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground truncate">
                  {`${emp.first_name} ${emp.last_name}`.trim()}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 shrink-0"
                  onClick={() => navigate(`/employees/${emp.id}`)}
                >
                  Fiche
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {remaining > 0 ? (
          <p className="text-xs text-muted-foreground">
            + {remaining} autre{remaining > 1 ? "s" : ""} collaborateur
            {remaining > 1 ? "s" : ""}
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function EmployeesCcAlert({
  alert,
}: {
  alert: CompanyOverviewAlert;
}) {
  const navigate = useNavigate();
  const preview = alert.employees ?? [];
  const remaining = (alert.count ?? preview.length) - preview.length;

  return (
    <Alert className="border-amber-200 bg-amber-50/80">
      <AlertTriangle className="h-4 w-4 text-amber-700" />
      <AlertDescription className="space-y-2">
        <p className="text-sm font-medium text-foreground">{alert.label}</p>
        {preview.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {preview.map((emp) => (
              <li key={emp.id} className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground truncate">
                  {`${emp.first_name} ${emp.last_name}`.trim()}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 shrink-0"
                  onClick={() => navigate(`/employees/${emp.id}`)}
                >
                  Fiche
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {remaining > 0 ? (
          <p className="text-xs text-muted-foreground">
            + {remaining} autre{remaining > 1 ? "s" : ""} collaborateur
            {remaining > 1 ? "s" : ""}
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

export function CompanyOverviewAlerts({
  alerts,
  onGoToPayrollSection,
}: {
  alerts: CompanyOverview["alerts"];
  onGoToPayrollSection: (anchor?: ComplianceAnchor) => void;
}): JSX.Element | null {
  if (!alerts.length) return null;

  const companyCcAlert = alerts.find((a) => a.code === CC_COMPANY_CODE);
  const employeesCcAlert = alerts.find((a) => a.code === CC_EMPLOYEES_CODE);
  const jeiNoRdAlert = alerts.find((a) => a.code === JEI_NO_RD_CODE);
  const jeiRdWithoutCompanyAlert = alerts.find((a) => a.code === JEI_RD_WITHOUT_COMPANY_CODE);
  const genericAlerts = alerts.filter(
    (a) =>
      a.code !== CC_COMPANY_CODE
      && a.code !== CC_EMPLOYEES_CODE
      && a.code !== JEI_NO_RD_CODE
      && a.code !== JEI_RD_WITHOUT_COMPANY_CODE,
  );

  return (
    <div className="space-y-3">
      {companyCcAlert ? (
        <CompanyCcAlert onGoToPayrollSection={onGoToPayrollSection} />
      ) : null}
      {employeesCcAlert ? <EmployeesCcAlert alert={employeesCcAlert} /> : null}
      {jeiNoRdAlert ? (
        <JeiAlert alert={jeiNoRdAlert} onGoToPayrollSection={onGoToPayrollSection} />
      ) : null}
      {jeiRdWithoutCompanyAlert ? (
        <JeiAlert
          alert={jeiRdWithoutCompanyAlert}
          onGoToPayrollSection={onGoToPayrollSection}
        />
      ) : null}
      {genericAlerts.length > 0 ? (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <ul className="space-y-1 pl-0 list-none">
              {genericAlerts.map((a) => (
                <GenericAlertItem key={a.code} alert={a} />
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}

export { CC_COMPANY_CODE, CC_EMPLOYEES_CODE };
