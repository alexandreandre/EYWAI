import { useNavigate } from "react-router-dom";
import { AlertTriangle, Copy, FileText, FlaskConical, RefreshCw } from "lucide-react";
import type { CompanyOverview, CompanyOverviewAlert } from "@/api/company";
import type { ComplianceAnchor } from "@/features/company/components/CompanyComplianceBand";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

const CC_COMPANY_CODE = "missing_company_collective_agreement";
const CC_EMPLOYEES_CODE = "employees_without_collective_agreement";
const JEI_NO_RD_CODE = "jei_enabled_no_rd_employees";
const JEI_RD_WITHOUT_COMPANY_CODE = "jei_rd_without_company_status";
const DSN_CODES = new Set([
  "dsn_never_imported",
  "dsn_onboarding_incomplete",
  "dsn_month_missing",
  "dsn_month_late",
]);

function DsnRhAlert({ alert }: { alert: CompanyOverviewAlert }) {
  const { toast } = useToast();
  const expected = (alert as CompanyOverviewAlert & { expected_period?: string }).expected_period;
  const monthLabel = expected ?? "le mois attendu";

  const copyRequest = async () => {
    const text = `Bonjour,\n\nPourriez-vous importer la DSN de ${monthLabel} dans EYWAI ? Nos cumuls de paie peuvent être incomplets sans cet import.\n\nMerci.`;
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: "Demande copiée", description: "Collez-la dans votre message à l'administrateur EYWAI." });
    } catch {
      toast({ title: "Copie impossible", variant: "destructive" });
    }
  };

  return (
    <Alert className="border-amber-200 bg-amber-50/80">
      <RefreshCw className="h-4 w-4 text-amber-700" />
      <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm text-foreground">
          {alert.label}
          {alert.code === "dsn_month_missing" || alert.code === "dsn_never_imported"
            ? " — vos cumuls de paie peuvent être incomplets. Contactez votre administrateur EYWAI."
            : null}
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0 border-amber-300 bg-white hover:bg-amber-50"
          onClick={() => void copyRequest()}
        >
          <Copy className="mr-1.5 h-3.5 w-3.5" />
          Copier la demande
        </Button>
      </AlertDescription>
    </Alert>
  );
}

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
  const dsnAlerts = alerts.filter((a) => DSN_CODES.has(a.code));
  const genericAlerts = alerts.filter(
    (a) =>
      a.code !== CC_COMPANY_CODE
      && a.code !== CC_EMPLOYEES_CODE
      && a.code !== JEI_NO_RD_CODE
      && a.code !== JEI_RD_WITHOUT_COMPANY_CODE
      && !DSN_CODES.has(a.code),
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
      {dsnAlerts.map((a) => (
        <DsnRhAlert key={a.code} alert={a} />
      ))}
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
