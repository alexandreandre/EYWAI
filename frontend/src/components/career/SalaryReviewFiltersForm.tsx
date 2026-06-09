import { Calculator, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export type SalaryReviewFilterState = {
  filterServiceId: string;
  filterStatut: string;
  filterContract: string;
  ancienneteMinMois: string;
  salaireMin: string;
  salaireMax: string;
  simType: "pourcentage" | "montant_fixe";
  perimetre: "brut_seul" | "brut_et_hs";
  valeurSim: string;
  effectiveDate: string;
};

type SalaryReviewFiltersFormProps = {
  filters: SalaryReviewFilterState;
  onChange: (patch: Partial<SalaryReviewFilterState>) => void;
  services: { id: string; name: string }[];
  servicesLoading: boolean;
  simLoading: boolean;
  companyId: string;
  onSimulate: () => void;
};

export function SalaryReviewFiltersForm({
  filters,
  onChange,
  services,
  servicesLoading,
  simLoading,
  companyId,
  onSimulate,
}: SalaryReviewFiltersFormProps) {
  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle className="text-base">Sélection des salariés</CardTitle>
        <CardDescription>Filtres appliqués aux collaborateurs actifs.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Service</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={filters.filterServiceId}
            onChange={(e) => onChange({ filterServiceId: e.target.value })}
            disabled={servicesLoading}
          >
            <option value="">Tous</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label>Statut</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={filters.filterStatut}
            onChange={(e) => onChange({ filterStatut: e.target.value })}
          >
            <option value="">Tous</option>
            <option value="Cadre">Cadre</option>
            <option value="Non-Cadre">Non-Cadre</option>
          </select>
        </div>
        <div className="space-y-2">
          <Label>Type de contrat</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={filters.filterContract}
            onChange={(e) => onChange({ filterContract: e.target.value })}
          >
            <option value="">Tous</option>
            <option value="CDI">CDI</option>
            <option value="CDD">CDD</option>
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="filtre-anciennete">Ancienneté minimum (mois)</Label>
          <Input
            id="filtre-anciennete"
            type="number"
            min={0}
            placeholder="Ex. 12"
            value={filters.ancienneteMinMois}
            onChange={(e) => onChange({ ancienneteMinMois: e.target.value })}
          />
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="smin">Salaire min (€)</Label>
            <Input
              id="smin"
              type="number"
              min={0}
              step="100"
              value={filters.salaireMin}
              onChange={(e) => onChange({ salaireMin: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="smax">Salaire max (€)</Label>
            <Input
              id="smax"
              type="number"
              min={0}
              step="100"
              value={filters.salaireMax}
              onChange={(e) => onChange({ salaireMax: e.target.value })}
            />
          </div>
        </div>

        <div className="space-y-3 border-t pt-4">
          <Label>Type d&apos;augmentation</Label>
          <RadioGroup
            value={filters.simType}
            onValueChange={(val) =>
              onChange({ simType: val as "pourcentage" | "montant_fixe" })
            }
            className="flex flex-col gap-2"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="pourcentage" id="drawer-pct" />
              <Label htmlFor="drawer-pct" className="cursor-pointer font-normal">
                Pourcentage
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="montant_fixe" id="drawer-fixe" />
              <Label htmlFor="drawer-fixe" className="cursor-pointer font-normal">
                Montant fixe
              </Label>
            </div>
          </RadioGroup>
          <div className="space-y-3">
            <Label>Périmètre</Label>
            <RadioGroup
              value={filters.perimetre}
              onValueChange={(val) =>
                onChange({ perimetre: val as "brut_seul" | "brut_et_hs" })
              }
              className="flex flex-col gap-2"
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="brut_seul" id="drawer-brut-seul" />
                <Label htmlFor="drawer-brut-seul" className="cursor-pointer font-normal">
                  Salaire de base (35 h)
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="brut_et_hs" id="drawer-brut-hs" />
                <Label htmlFor="drawer-brut-hs" className="cursor-pointer font-normal">
                  Salaire mensuel total (base + HS structurelles)
                </Label>
              </div>
            </RadioGroup>
          </div>
          <div className="space-y-2">
            <Label htmlFor="drawer-val">
              {filters.simType === "pourcentage" ? "Valeur (%)" : "Montant (€)"}
            </Label>
            <Input
              id="drawer-val"
              type="number"
              min={0}
              step={filters.simType === "pourcentage" ? "0.1" : "1"}
              value={filters.valeurSim}
              onChange={(e) => onChange({ valeurSim: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="drawer-date">Date d&apos;effet</Label>
            <Input
              id="drawer-date"
              type="date"
              value={filters.effectiveDate}
              onChange={(e) => onChange({ effectiveDate: e.target.value })}
            />
          </div>
          <Button
            type="button"
            className="w-full"
            disabled={simLoading || !companyId || !filters.valeurSim.trim()}
            onClick={onSimulate}
          >
            {simLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Calculator className="mr-2 h-4 w-4" />
            )}
            Simuler l&apos;impact
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
