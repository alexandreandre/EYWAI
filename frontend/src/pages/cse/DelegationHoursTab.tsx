// frontend/src/pages/cse/DelegationHoursTab.tsx
// Onglet Heures de délégation

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { getDelegationSummary, type DelegationSummary } from "@/api/cse";
import { Plus, Clock, Loader2 } from "lucide-react";
import { DelegationHourModal } from "@/components/cse/DelegationHourModal";

export default function DelegationHoursTab() {
  const { toast } = useToast();
  const [searchTerm, setSearchTerm] = useState("");
  const [hourModalOpen, setHourModalOpen] = useState(false);
  
  // Période : mois en cours
  const now = new Date();
  const periodStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const periodEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  const { data: summary = [], isLoading } = useQuery({
    queryKey: ["cse", "delegation-summary", periodStart, periodEnd],
    queryFn: () => getDelegationSummary(periodStart, periodEnd),
  });

  const filteredSummary = summary.filter((item) => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        item.first_name.toLowerCase().includes(search) ||
        item.last_name.toLowerCase().includes(search)
      );
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <Input
            placeholder="Rechercher un élu..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <Button onClick={() => setHourModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Saisir une heure
        </Button>
      </div>

      {/* Récapitulatif */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Récapitulatif des heures de délégation
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredSummary.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Aucun élu trouvé
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Élu</TableHead>
                  <TableHead>Quota mensuel</TableHead>
                  <TableHead>Consommé</TableHead>
                  <TableHead>Restant</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSummary.map((item) => (
                  <TableRow key={item.employee_id}>
                    <TableCell className="font-medium">
                      {item.first_name} {item.last_name}
                    </TableCell>
                    <TableCell>{item.quota_hours_per_month}h</TableCell>
                    <TableCell>{item.consumed_hours}h</TableCell>
                    <TableCell>
                      <span className={item.remaining_hours < 0 ? "text-red-600 font-medium" : ""}>
                        {item.remaining_hours}h
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modal saisie heure */}
      {hourModalOpen && (
        <DelegationHourModal
          open={hourModalOpen}
          onOpenChange={setHourModalOpen}
        />
      )}
    </div>
  );
}
