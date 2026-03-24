// frontend/src/components/PromotionComparison.tsx
// Composant pour afficher un tableau comparatif avant/après d'une promotion

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowRight, TrendingUp, User, DollarSign, Briefcase, Award, Shield } from "lucide-react";
import type { Promotion, Salary, Classification, RhAccessRole } from "@/api/promotions";
import { cn } from "@/lib/utils";

interface PromotionComparisonProps {
  promotion: Promotion;
  className?: string;
}

const ROLE_LABELS: Record<string, string> = {
  collaborateur: "Collaborateur",
  collaborateur_rh: "Collaborateur RH",
  rh: "RH",
  admin: "Administrateur",
};

function formatCurrency(salary: Salary | null): string {
  if (!salary || !salary.valeur) return "—";
  return `${salary.valeur.toLocaleString("fr-FR")} ${salary.devise || "EUR"}`;
}

function formatClassification(classification: Classification | null): string {
  if (!classification) return "—";
  const parts: string[] = [];
  if (classification.coefficient) {
    parts.push(`Coeff. ${classification.coefficient}`);
  }
  if (classification.classe_emploi) {
    parts.push(`Classe ${classification.classe_emploi}`);
  }
  if (classification.groupe_emploi) {
    parts.push(`Groupe ${classification.groupe_emploi}`);
  }
  return parts.length > 0 ? parts.join(", ") : "—";
}

function calculateSalaryIncrease(
  previous: Salary | null,
  newSalary: Salary | null
): string {
  if (!previous?.valeur || !newSalary?.valeur || previous.valeur === 0) {
    return "";
  }
  const increase = ((newSalary.valeur - previous.valeur) / previous.valeur) * 100;
  return `(+${increase.toFixed(1)}%)`;
}

export function PromotionComparison({
  promotion,
  className,
}: PromotionComparisonProps) {
  const comparisonRows: Array<{
    label: string;
    icon: React.ReactNode;
    previous: string;
    newValue: string;
    increase?: string;
  }> = [];

  // Changement de poste
  if (promotion.new_job_title || promotion.previous_job_title) {
    comparisonRows.push({
      label: "Poste",
      icon: <Briefcase className="h-4 w-4" />,
      previous: promotion.previous_job_title || "—",
      newValue: promotion.new_job_title || "—",
    });
  }

  // Changement de salaire
  if (promotion.new_salary || promotion.previous_salary) {
    const increase = calculateSalaryIncrease(
      promotion.previous_salary,
      promotion.new_salary
    );
    comparisonRows.push({
      label: "Salaire mensuel brut",
      icon: <DollarSign className="h-4 w-4" />,
      previous: formatCurrency(promotion.previous_salary),
      newValue: formatCurrency(promotion.new_salary),
      increase,
    });
  }

  // Changement de statut
  if (promotion.new_statut || promotion.previous_statut) {
    comparisonRows.push({
      label: "Statut",
      icon: <User className="h-4 w-4" />,
      previous: promotion.previous_statut || "—",
      newValue: promotion.new_statut || "—",
    });
  }

  // Changement de classification
  if (promotion.new_classification || promotion.previous_classification) {
    comparisonRows.push({
      label: "Classification conventionnelle",
      icon: <Award className="h-4 w-4" />,
      previous: formatClassification(promotion.previous_classification),
      newValue: formatClassification(promotion.new_classification),
    });
  }

  // Changement d'accès RH
  if (promotion.grant_rh_access && promotion.new_rh_access) {
    const previousLabel =
      promotion.previous_rh_access
        ? ROLE_LABELS[promotion.previous_rh_access] || promotion.previous_rh_access
        : "Aucun accès RH";
    const newLabel =
      ROLE_LABELS[promotion.new_rh_access] || promotion.new_rh_access;
    comparisonRows.push({
      label: "Accès RH",
      icon: <Shield className="h-4 w-4" />,
      previous: previousLabel,
      newValue: newLabel,
    });
  }

  if (comparisonRows.length === 0) {
    return null;
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">
          Comparaison avant/après
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Élément</TableHead>
              <TableHead className="w-[250px]">Avant</TableHead>
              <TableHead className="w-[50px]"></TableHead>
              <TableHead className="w-[250px]">Après</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {comparisonRows.map((row, index) => (
              <TableRow key={index}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    {row.icon}
                    <span>{row.label}</span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {row.previous}
                </TableCell>
                <TableCell className="text-center">
                  <ArrowRight className="h-4 w-4 text-muted-foreground mx-auto" />
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{row.newValue}</span>
                    {row.increase && (
                      <span className="text-green-600 font-medium flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {row.increase}
                      </span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
