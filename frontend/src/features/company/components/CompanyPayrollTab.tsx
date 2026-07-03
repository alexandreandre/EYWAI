import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarDays, Percent } from "lucide-react";
import type { CompanyDetails } from "@/api/company";
import type { DsnCoverage } from "@/api/dsnImport";
import CollectiveAgreementCard from "@/components/CollectiveAgreementCard";
import CseStatusCard from "@/features/company/components/CseStatusCard";
import MaintenanceSettingsCard from "@/features/company/components/MaintenanceSettingsCard";
import PrimeAncienneteSettingsCard from "@/features/company/components/PrimeAncienneteSettingsCard";
import JeiSettingsCard from "@/features/company/components/JeiSettingsCard";
import WorkMedalSettingsCard from "@/features/company/components/WorkMedalSettingsCard";
import { DsnSyncModeCard } from "@/features/dsn-import/components/DsnSyncModeCard";
import { CompanyPayrollParamsEditCard } from "@/features/company/components/CompanyPayrollParamsEditCard";
import { CompanyMutuelleSection } from "@/features/company/components/CompanyMutuelleSection";
import { WorkMedalCasesList } from "@/features/work-medals/components/WorkMedalCasesList";
import OethSettingsCard from "@/features/company/components/OethSettingsCard";
import OvertimeContingentSettingsCard from "@/features/company/components/OvertimeContingentSettingsCard";
import LeaveSettingsCard from "@/features/company/components/LeaveSettingsCard";
import CetSettingsCard from "@/features/company/components/CetSettingsCard";
import CpFractionnementSettingsCard from "@/features/company/components/CpFractionnementSettingsCard";
import CpSenioritySettingsCard from "@/features/company/components/CpSenioritySettingsCard";
import ModulationSettingsCard from "@/features/company/components/ModulationSettingsCard";
import WorkTimePeriodsCard from "@/features/company/components/WorkTimePeriodsCard";
import WeekTemplatesSettingsCard from "@/features/company/components/WeekTemplatesSettingsCard";
import { CompanySetupCalendarsPanel } from "@/features/admin-import/components/CompanySetupCalendarsPanel";
import TimesheetImportSettingsCard from "@/features/company/components/TimesheetImportSettingsCard";
import PunchAccountingSettingsCard from "@/features/company/components/PunchAccountingSettingsCard";
import IjssImportProfileCard from "@/features/company/components/IjssImportProfileCard";
import PayrollVariableRulesCard from "@/features/company/components/PayrollVariableRulesCard";
import PayrollSpecialDaysCard from "@/features/company/components/PayrollSpecialDaysCard";
import PlanningSettingsCard from "@/features/company/components/PlanningSettingsCard";
import PublicHolidaysSettingsCard from "@/features/company/components/PublicHolidaysSettingsCard";
import NetEntreprisesConfigCard from "@/features/net-entreprises/components/NetEntreprisesConfigCard";
import type { ComplianceAnchor } from "@/features/company/components/CompanyComplianceBand";
import { WorkTimeHubIntro } from "@/features/work-time-tracking/components/WorkTimeHubIntro";
import { formatCollectiveAgreementLabel } from "@/features/company/lib/companyPageTabs";
import {
  DEFAULT_OPEN_PAYROLL_SECTIONS,
  PAYROLL_SECTION_KEYS,
  PayrollSettingsSection,
  type PayrollSectionKey,
} from "@/features/company/components/PayrollSettingsSection";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";

const ANCHOR_TO_SECTION: Record<ComplianceAnchor, PayrollSectionKey> = {
  "convention-collective": "convention-collective",
  jei: "exoneration",
  "taux-at-mp": "taux-paie",
  "taux-vm": "taux-paie",
  cse: "dialogue-social",
  "temps-travail": "temps-travail",
};

const formatPayday = (day: number | null | undefined): string => {
  if (day === null || day === undefined) return "Non défini";
  const dayMap: Record<number, string> = {
    0: "Lundi",
    1: "Mardi",
    2: "Mercredi",
    3: "Jeudi",
    4: "Vendredi",
    5: "Samedi",
    6: "Dimanche",
  };
  return dayMap[day] || String(day);
};

const formatOccurrence = (occ: number | null | undefined): string => {
  if (occ === null || occ === undefined) return "Non défini";
  const occurrenceMap: Record<number, string> = {
    "-1": "Dernier du mois",
    "-2": "Avant-dernier du mois",
    "-3": "Antepénultième du mois",
    "1": "Premier du mois",
    "2": "Deuxième du mois",
    "3": "Troisième du mois",
    "4": "Quatrième du mois",
    "5": "Cinquième du mois",
  };
  return occurrenceMap[occ] || String(occ);
};

const formatPercentage = (value: number | null | undefined) => {
  if (value === null || value === undefined) return "N/A";
  const percent = value > 1 ? value : value * 100;
  return `${percent.toFixed(2)} %`;
};

function PayrollSectionsToolbar({
  onExpandAll,
  onCollapseAll,
}: {
  onExpandAll: () => void;
  onCollapseAll: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Button type="button" variant="ghost" size="sm" onClick={onExpandAll}>
        Tout développer
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={onCollapseAll}>
        Tout replier
      </Button>
    </div>
  );
}

export function CompanyPayrollTab({
  company,
  scrollAnchor,
  cseObligation,
  dsnCoverage = null,
  canEditDsn = false,
  canEditPayrollParams = false,
  onDsnUpdated,
  onPayrollParamsUpdated,
}: {
  company: CompanyDetails;
  scrollAnchor?: ComplianceAnchor | null;
  cseObligation?: boolean;
  dsnCoverage?: DsnCoverage | null;
  canEditDsn?: boolean;
  canEditPayrollParams?: boolean;
  onDsnUpdated?: () => void;
  onPayrollParamsUpdated?: () => void;
}): JSX.Element {
  const cc = formatCollectiveAgreementLabel(company.collective_agreement, company.idcc);
  const anchorRefs = useRef<Partial<Record<ComplianceAnchor, HTMLElement | null>>>({});

  const [openSections, setOpenSections] = useState<Set<PayrollSectionKey>>(
    () => new Set(DEFAULT_OPEN_PAYROLL_SECTIONS),
  );

  const expandAll = useCallback(() => {
    setOpenSections(new Set(PAYROLL_SECTION_KEYS));
  }, []);

  const collapseAll = useCallback(() => {
    setOpenSections(new Set());
  }, []);

  const setSectionOpen = useCallback((key: PayrollSectionKey, open: boolean) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (open) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!scrollAnchor) return;
    const section = ANCHOR_TO_SECTION[scrollAnchor];
    setOpenSections((prev) => {
      if (prev.has(section)) return prev;
      const next = new Set(prev);
      next.add(section);
      return next;
    });

    const timer = window.setTimeout(() => {
      const el = anchorRefs.current[scrollAnchor];
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 200);

    return () => window.clearTimeout(timer);
  }, [scrollAnchor]);

  const setAnchorRef = (anchor: ComplianceAnchor) => (el: HTMLElement | null) => {
    anchorRefs.current[anchor] = el;
  };

  const renderSection = (
    key: PayrollSectionKey,
    title: string,
    description: string | undefined,
    children: ReactNode,
  ) => (
    <PayrollSettingsSection
      key={key}
      title={title}
      description={description}
      open={openSections.has(key)}
      onOpenChange={(open) => setSectionOpen(key, open)}
    >
      {children}
    </PayrollSettingsSection>
  );

  return (
    <div className="space-y-3">
      <PayrollSectionsToolbar onExpandAll={expandAll} onCollapseAll={collapseAll} />

      {renderSection(
        "convention-collective",
        "Convention collective",
        "CCN, prime d'ancienneté et règles associées",
        <>
          {!cc.configured ? (
            <Alert className="border-amber-200 bg-amber-50/80">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <AlertDescription>
                Aucune convention collective n&apos;est configurée. Elle est indispensable pour
                le calcul de la paie et l&apos;application des grilles salariales.
              </AlertDescription>
            </Alert>
          ) : null}
          <div id="convention-collective" ref={setAnchorRef("convention-collective")}>
            <CollectiveAgreementCard companyId={company.id} companyName={company.company_name} />
          </div>
          <PrimeAncienneteSettingsCard />
        </>,
      )}

      {renderSection(
        "taux-paie",
        "Taux et période de paie",
        "AT/MP, versement mobilité, FNAL et calendrier de paie",
        <>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div id="taux-at-mp" ref={setAnchorRef("taux-at-mp")}>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center text-base">
                    <Percent className="mr-2 h-5 w-5 text-amber-600" />
                    Taux spécifiques
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableBody>
                      <TableRow>
                        <TableCell className="font-medium text-muted-foreground">
                          Taux Accident Travail (AT/MP)
                        </TableCell>
                        <TableCell className="font-semibold">
                          {formatPercentage(company.taux_at_mp)}
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium text-muted-foreground">
                          Taux Versement Mobilité (VM)
                        </TableCell>
                        <TableCell className="font-semibold">
                          {formatPercentage(company.taux_vm)}
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium text-muted-foreground">Taux FNAL</TableCell>
                        <TableCell className="font-semibold">
                          {formatPercentage(company.taux_fnal)}
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
            <div id="taux-vm" ref={setAnchorRef("taux-vm")} className="sr-only" aria-hidden />

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center text-base">
                  <CalendarDays className="mr-2 h-5 w-5 text-muted-foreground" />
                  Paramètres de période de paie
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableBody>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground">
                        Jour de fin de période
                      </TableCell>
                      <TableCell className="font-medium">
                        {formatPayday(company.paie_jour_de_fin)}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground">
                        Occurrence de la paie
                      </TableCell>
                      <TableCell className="font-medium">
                        {formatOccurrence(company.paie_occurrence)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
          <CompanyPayrollParamsEditCard
            company={company}
            canEdit={canEditPayrollParams}
            onSaved={onPayrollParamsUpdated}
          />
        </>,
      )}

      {renderSection(
        "declarations",
        "Déclarations",
        "Synchronisation DSN, télétransmission Net-entreprises",
        <>
          <DsnSyncModeCard
            company={company}
            coverage={dsnCoverage}
            readOnly={!canEditDsn}
            onUpdated={onDsnUpdated}
          />
          <NetEntreprisesConfigCard />
        </>,
      )}

      {renderSection(
        "mutuelle",
        "Mutuelle & complémentaire santé",
        "Organisme, catalogue de formules et affectation salariés",
        <CompanyMutuelleSection canEdit={canEditPayrollParams} embedded />,
      )}

      {renderSection(
        "temps-travail",
        "Temps de travail",
        "Congés, RTT, modulation, plafond HS, pointages",
        <div id="temps-travail" ref={setAnchorRef("temps-travail")} className="space-y-4">
          <WorkTimeHubIntro />

          <PayrollSettingsSection
            nested
            title="Jours fériés & congés"
            description="Fériés légaux, CP, RTT, CP ancienneté, fractionnement"
            defaultOpen
          >
            <PublicHolidaysSettingsCard />
            <LeaveSettingsCard />
            <CpSenioritySettingsCard />
            <CpFractionnementSettingsCard />
          </PayrollSettingsSection>

          <PayrollSettingsSection
            nested
            title="Organisation du temps & compte d'heures"
            description="Modulation, périodes horaires, plafond HS, CET"
            defaultOpen={false}
          >
            <ModulationSettingsCard />
            <WorkTimePeriodsCard />
            <OvertimeContingentSettingsCard />
            <CetSettingsCard />
          </PayrollSettingsSection>

          <PayrollSettingsSection
            nested
            title="Pointages & imports"
            description="Comptabilisation, imports CSV, profils IJSS"
            defaultOpen={false}
          >
            <IjssImportProfileCard />
            <PunchAccountingSettingsCard />
            <TimesheetImportSettingsCard />
          </PayrollSettingsSection>
        </div>,
      )}

      {renderSection(
        "exoneration",
        "Dispositifs d'exonération",
        "Statut JEI et personnel R&D éligible",
        <div id="jei" ref={setAnchorRef("jei")}>
          <JeiSettingsCard />
        </div>,
      )}

      {cseObligation
        ? renderSection(
            "dialogue-social",
            "Dialogue social",
            "CSE, élections et obligations légales",
            <div id="cse" ref={setAnchorRef("cse")} className="space-y-4">
              <CseStatusCard />
              <Card>
                <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted-foreground">
                    Gérez les élections, réunions et documents CSE depuis le module dédié.
                  </p>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/cse">Ouvrir CSE & Dialogue Social</Link>
                  </Button>
                </CardContent>
              </Card>
            </div>,
          )
        : null}

      {!cseObligation ? (
        <div id="cse" ref={setAnchorRef("cse")} className="hidden" aria-hidden />
      ) : null}

      {renderSection(
        "primes-distinctions",
        "Primes et distinctions",
        "Médailles du travail et dossiers en attente",
        <>
          <WorkMedalSettingsCard />
          <WorkMedalCasesList statusFilter="awaiting_rh" />
        </>,
      )}

      {renderSection(
        "oeth",
        "OETH / DOETH",
        "Obligation d'emploi TH et déclaration annuelle",
        <OethSettingsCard />,
      )}

      {renderSection(
        "planning",
        "Planning & primes équipe",
        "Modèles de semaine, types de poste, paniers et nuit",
        <>
          <WeekTemplatesSettingsCard />
          <CompanySetupCalendarsPanel companyId={company.id} />
          <PlanningSettingsCard />
        </>,
      )}

      {renderSection(
        "variables-paie",
        "Variables de paie",
        "Jours spéciaux, règles récurrentes et génération mensuelle",
        <>
          <PayrollSpecialDaysCard />
          <PayrollVariableRulesCard />
        </>,
      )}

      {renderSection(
        "avance",
        "Avancé",
        "Maintien de salaire et paramètres expert",
        <MaintenanceSettingsCard />,
      )}
    </div>
  );
}
