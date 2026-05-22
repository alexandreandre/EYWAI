import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { CareerActivityTab } from "@/components/career/types";

export const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "draft", label: "Brouillon" },
  { value: "effective", label: "Effective" },
  { value: "cancelled", label: "Annulée" },
  { value: "brouillon", label: "Avenant brouillon" },
  { value: "envoye", label: "Avenant envoyé" },
  { value: "signe", label: "Avenant signé" },
];

export const TYPE_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "poste", label: "Changement de poste" },
  { value: "salaire", label: "Augmentation de salaire" },
  { value: "statut", label: "Changement de statut" },
  { value: "classification", label: "Changement de classification" },
  { value: "mixte", label: "Promotion mixte" },
];

type CareerFiltersBarProps = {
  search: string;
  onSearchChange: (value: string) => void;
  year: number | "all";
  onYearChange: (value: number | "all") => void;
  status: string;
  onStatusChange: (value: string) => void;
  type: string;
  onTypeChange: (value: string) => void;
  activeTab: CareerActivityTab;
  onReset: () => void;
};

export function CareerFiltersBar({
  search,
  onSearchChange,
  year,
  onYearChange,
  status,
  onStatusChange,
  type,
  onTypeChange,
  activeTab,
  onReset,
}: CareerFiltersBarProps) {
  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);

  const showStatus = activeTab !== "salary_review_session";
  const showType = activeTab === "all" || activeTab === "promotion";

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative max-w-sm flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Rechercher par nom, poste ou libellé..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-10"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={year === "all" ? "all" : String(year)}
          onValueChange={(v) => onYearChange(v === "all" ? "all" : Number(v))}
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Année" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes les années</SelectItem>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {showStatus && (
          <Select value={status} onValueChange={onStatusChange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {showType && (
          <Select value={type} onValueChange={onTypeChange}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              {TYPE_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <Button variant="outline" onClick={onReset}>
          Réinitialiser
        </Button>
      </div>
    </div>
  );
}
