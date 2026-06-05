import { CalendarDays, Percent } from "lucide-react";
import type { CompanyDetails } from "@/api/company";
import CollectiveAgreementCard from "@/components/CollectiveAgreementCard";
import MaintenanceSettingsCard from "@/features/company/components/MaintenanceSettingsCard";
import NetEntreprisesConfigCard from "@/features/net-entreprises/components/NetEntreprisesConfigCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";

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

export function CompanyPayrollTab({
  company,
}: {
  company: CompanyDetails;
}): JSX.Element {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <CollectiveAgreementCard companyId={company.id} companyName={company.company_name} />

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

        <Card className="md:col-span-2">
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

      <NetEntreprisesConfigCard />

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
    </div>
  );
}
