import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarDays, ChevronDown, Percent } from "lucide-react";
import type { CompanyDetails } from "@/api/company";
import type { DsnCoverage } from "@/api/dsnImport";
import CollectiveAgreementCard from "@/components/CollectiveAgreementCard";
import MaintenanceSettingsCard from "@/features/company/components/MaintenanceSettingsCard";
import JeiSettingsCard from "@/features/company/components/JeiSettingsCard";
import WorkMedalSettingsCard from "@/features/company/components/WorkMedalSettingsCard";
import { DsnSyncModeCard } from "@/features/dsn-import/components/DsnSyncModeCard";
import { WorkMedalCasesList } from "@/features/work-medals/components/WorkMedalCasesList";
import OethSettingsCard from "@/features/company/components/OethSettingsCard";
import NetEntreprisesConfigCard from "@/features/net-entreprises/components/NetEntreprisesConfigCard";
import type { ComplianceAnchor } from "@/features/company/components/CompanyComplianceBand";
import { formatCollectiveAgreementLabel } from "@/features/company/lib/companyPageTabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";

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

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h3>
  );
}

export function CompanyPayrollTab({
  company,
  scrollAnchor,
  cseObligation,
  dsnCoverage = null,
  canEditDsn = false,
  onDsnUpdated,
}: {
  company: CompanyDetails;
  scrollAnchor?: ComplianceAnchor | null;
  cseObligation?: boolean;
  dsnCoverage?: DsnCoverage | null;
  canEditDsn?: boolean;
  onDsnUpdated?: () => void;
}): JSX.Element {
  const cc = formatCollectiveAgreementLabel(company.collective_agreement, company.idcc);
  const anchorRefs = useRef<Partial<Record<ComplianceAnchor, HTMLElement | null>>>({});

  useEffect(() => {
    if (!scrollAnchor) return;
    const el = anchorRefs.current[scrollAnchor];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [scrollAnchor]);

  const setAnchorRef = (anchor: ComplianceAnchor) => (el: HTMLElement | null) => {
    anchorRefs.current[anchor] = el;
  };

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <SectionHeading>Convention collective</SectionHeading>
        {!cc.configured ? (
          <Alert className="border-amber-200 bg-amber-50/80">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              Aucune convention collective n&apos;est configurée. Elle est indispensable pour le
              calcul de la paie et l&apos;application des grilles salariales.
            </AlertDescription>
          </Alert>
        ) : null}
        <div id="convention-collective" ref={setAnchorRef("convention-collective")}>
          <CollectiveAgreementCard companyId={company.id} companyName={company.company_name} />
        </div>
      </section>

      <section
        className="space-y-3"
        id="jei"
        ref={setAnchorRef("jei")}
      >
        <SectionHeading>Dispositifs d&apos;exonération</SectionHeading>
        <JeiSettingsCard />
      </section>

      <section className="space-y-3">
        <SectionHeading>Taux et période de paie</SectionHeading>
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
      </section>

      {cseObligation ? (
        <section className="space-y-3" id="cse" ref={setAnchorRef("cse")}>
          <SectionHeading>Dialogue social</SectionHeading>
          <Card>
            <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Votre effectif déclenche des obligations CSE. Gérez les élections et réunions
                depuis le module dédié.
              </p>
              <Button variant="outline" size="sm" asChild>
                <Link to="/cse">Ouvrir CSE & Dialogue Social</Link>
              </Button>
            </CardContent>
          </Card>
        </section>
      ) : (
        <div id="cse" ref={setAnchorRef("cse")} className="hidden" aria-hidden />
      )}

      <section className="space-y-3">
        <SectionHeading>Déclarations</SectionHeading>
        <DsnSyncModeCard
          company={company}
          coverage={dsnCoverage}
          readOnly={!canEditDsn}
          onUpdated={onDsnUpdated}
        />
        <NetEntreprisesConfigCard />
      </section>

      <section className="space-y-3">
        <SectionHeading>Primes et distinctions</SectionHeading>
        <WorkMedalSettingsCard />
        <WorkMedalCasesList statusFilter="awaiting_rh" />
      </section>

      <section className="space-y-3">
        <SectionHeading>OETH / DOETH</SectionHeading>
        <OethSettingsCard />
      </section>

      <section className="space-y-3">
        <SectionHeading>Avancé</SectionHeading>
        <Collapsible defaultOpen={false}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" className="w-full justify-between">
              Maintien de salaire (paramètres avancés)
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-4">
            <MaintenanceSettingsCard />
          </CollapsibleContent>
        </Collapsible>
      </section>
    </div>
  );
}
