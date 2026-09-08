import { Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePeriodeVariables } from "@/features/payroll/hooks/usePeriodeVariables";
import { estSurLeMoisCivil, formatFr } from "@/features/payroll/lib/fenetreVariables";

interface Props {
  selectedDate: { year: number; month: number };
  isLoadingSaisies: boolean;
  employeeSaisies: Array<{
    id: string;
    name: string;
    amount: number;
    is_socially_taxed: boolean;
    is_taxable: boolean;
  }>;
  onAddSaisie: () => void;
  onDeleteSaisie: (id: string) => void;
}

export function EmployeeDetailSaisiesTab({
  selectedDate,
  isLoadingSaisies,
  employeeSaisies,
  onAddSaisie,
  onDeleteSaisie,
}: Props) {
  // Les saisies du mois ne portent pas de date : aucune fenêtre ne peut les
  // découper. Elles valent pour la paie du mois, telle que la gestionnaire les
  // saisit — d'où ce rappel de la période sur laquelle elle compte.
  const { data: fenetre } = usePeriodeVariables(
    selectedDate.year,
    selectedDate.month,
  );

  return (
          <Card>
            <CardHeader className="flex flex-row justify-between items-center">
              <div>
                <CardTitle>Primes de {new Date(selectedDate.year, selectedDate.month - 1).toLocaleString("fr-FR", { month: "long" })}</CardTitle>
                <CardDescription>
                  Primes, acomptes et autres variables pour la paie de ce mois.
                  {fenetre && !estSurLeMoisCivil(fenetre) ? (
                    <>
                      {" "}Heures sup et paniers sont comptés du {formatFr(fenetre.debut)} au{" "}
                      {formatFr(fenetre.fin)}.
                    </>
                  ) : null}
                </CardDescription>
              </div>
              <Button onClick={() => onAddSaisie()}>+ Ajouter une saisie</Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Montant</TableHead>
                    <TableHead>Soumis à cotisations</TableHead>
                    <TableHead>Soumis à impôt</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoadingSaisies ? (
                    <TableRow><TableCell colSpan={5} className="text-center h-24"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></TableCell></TableRow>
                  ) : employeeSaisies.length > 0 ? employeeSaisies.map((saisie) => (
                    <TableRow key={saisie.id}>
                      <TableCell className="font-medium">{saisie.name}</TableCell>
                      <TableCell>{saisie.amount.toFixed(2)} €</TableCell>
                      <TableCell>{saisie.is_socially_taxed ? 'Oui' : 'Non'}</TableCell>
                      <TableCell>{saisie.is_taxable ? 'Oui' : 'Non'}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => onDeleteSaisie(saisie.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center h-24">Aucune saisie pour ce mois.</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

  );
}
