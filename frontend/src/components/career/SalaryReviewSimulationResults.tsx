import type { EmployeSimule, SimulationCollectiveResultat } from "@/api/augmentations";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatEuroAmount } from "@/lib/careerFormat";
import { ligneAugmentation } from "@/components/career/salaryReviewUtils";

type SalaryReviewSimulationResultsProps = {
  simResult: SimulationCollectiveResultat;
  employes: EmployeSimule[];
  selectedIds: Set<string>;
  allSelected: boolean;
  onToggleOne: (id: string, checked: boolean) => void;
  onToggleAll: (checked: boolean) => void;
  onApply: () => void;
};

export function SalaryReviewSimulationResults({
  simResult,
  employes,
  selectedIds,
  allSelected,
  onToggleOne,
  onToggleAll,
  onApply,
}: SalaryReviewSimulationResultsProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Salariés concernés</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{simResult.nb_employes}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Impact masse salariale</CardDescription>
            <CardTitle className="text-xl tabular-nums text-emerald-700">
              +{formatEuroAmount(simResult.difference_masse_salariale)}/mois
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Charges patronales supplémentaires</CardDescription>
            <CardTitle className="text-xl tabular-nums text-emerald-700">
              +{formatEuroAmount(simResult.cout_charges_patronales_supplementaires)}/mois
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Coût total employeur supplémentaire</CardDescription>
            <CardTitle className="text-xl tabular-nums text-emerald-700">
              +{formatEuroAmount(simResult.cout_total_supplementaire)}/mois
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
          <div>
            <CardTitle>Détail par salarié</CardTitle>
            <CardDescription>
              Sélectionnez ceux à inclure dans l&apos;application.
            </CardDescription>
          </div>
          <Button type="button" disabled={!selectedIds.size} onClick={onApply}>
            Appliquer aux salariés sélectionnés
          </Button>
        </CardHeader>
        <CardContent className="w-full overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Poste</TableHead>
                <TableHead>Ancien brut</TableHead>
                <TableHead>Nouveau brut</TableHead>
                <TableHead>Augmentation</TableHead>
                <TableHead className="w-[120px] text-center">
                  <div className="flex flex-col items-center gap-1">
                    <span>Sélectionné</span>
                    <Checkbox
                      checked={allSelected}
                      onCheckedChange={(c) => onToggleAll(c === true)}
                      aria-label="Tout sélectionner"
                    />
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {employes.map((e) => (
                <TableRow key={e.employee_id}>
                  <TableCell className="font-medium">{e.nom_complet}</TableCell>
                  <TableCell>{e.poste ?? "—"}</TableCell>
                  <TableCell>{formatEuroAmount(e.ancien_salaire_brut)}</TableCell>
                  <TableCell>{formatEuroAmount(e.nouveau_salaire_brut)}</TableCell>
                  <TableCell>
                    <span className="font-medium text-emerald-700 whitespace-nowrap">
                      {ligneAugmentation(e)}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <Checkbox
                      checked={selectedIds.has(e.employee_id)}
                      onCheckedChange={(c) => onToggleOne(e.employee_id, c === true)}
                      aria-label={`Sélectionner ${e.nom_complet}`}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
