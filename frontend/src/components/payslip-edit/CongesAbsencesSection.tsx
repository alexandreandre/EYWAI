// frontend/src/components/payslip-edit/CongesAbsencesSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Calendar, Plus, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import type { MaintenancePreview } from '@/api/absences';
import {
  isPayslipBlocMaintienPresent,
  type BulletinLigneBrut,
  type PayslipSyntheseNet,
} from '@/api/payslips';

interface CongesAbsencesSectionProps {
  congesData: any[];
  absencesData: any[];
  onCongesChange: (data: any[]) => void;
  onAbsencesChange: (data: any[]) => void;
  /** Données maintien issues du bulletin (T4B) — optionnel. */
  detailsMaintien?: BulletinLigneBrut[];
  blocMaintien?: MaintenancePreview | Record<string, unknown>;
  syntheseNet?: PayslipSyntheseNet;
  onOpenMaintienModal?: () => void;
}

function formatMontantSignedEUR(value: number): string {
  const abs = Math.abs(value);
  const fmt = abs.toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  });
  if (value < 0) return `− ${fmt}`;
  return `+ ${fmt}`;
}

export default function CongesAbsencesSection({
  congesData,
  absencesData,
  onCongesChange,
  onAbsencesChange,
  detailsMaintien = [],
  blocMaintien,
  syntheseNet,
  onOpenMaintienModal,
}: CongesAbsencesSectionProps) {
  const handleCongeChange = (index: number, field: string, value: any) => {
    const newData = [...congesData];
    newData[index] = { ...newData[index], [field]: value };
    onCongesChange(newData);
  };

  const handleAbsenceChange = (index: number, field: string, value: any) => {
    const newData = [...absencesData];
    newData[index] = { ...newData[index], [field]: value };
    onAbsencesChange(newData);
  };

  const addConge = () => {
    const newConge = {
      libelle: 'Nouveau congé',
      quantite: 0,
      taux: 0,
      gain: 0,
      perte: 0
    };
    onCongesChange([...congesData, newConge]);
  };

  const addAbsence = () => {
    const newAbsence = {
      libelle: 'Nouvelle absence',
      quantite: 0,
      taux: 0,
      gain: 0,
      perte: 0
    };
    onAbsencesChange([...absencesData, newAbsence]);
  };

  const removeConge = (index: number) => {
    const newData = congesData.filter((_, i) => i !== index);
    onCongesChange(newData);
  };

  const removeAbsence = (index: number) => {
    const newData = absencesData.filter((_, i) => i !== index);
    onAbsencesChange(newData);
  };

  const showMaintienBloc = isPayslipBlocMaintienPresent(blocMaintien);
  const maintienBloc = showMaintienBloc ? blocMaintien : null;

  const sumPerteMaintien = (detailsMaintien ?? []).reduce(
    (s, l) => s + (Number(l?.perte) || 0),
    0
  );
  const sn = syntheseNet ?? {};
  const ijssSub = Number(sn.ijss_subrogees ?? 0);
  const ijssBrut = Number(sn.ijss_brut ?? ijssSub);
  const ijssCsg = Number(sn.ijss_csg_total ?? 0);
  const ijssNet = Number(sn.ijss_net ?? 0);
  const ijssSource = sn.ijss_source as string | undefined;
  const maintienEmp = Number(sn.maintien_employeur ?? 0);
  const complementEmp = Number(sn.complement_employeur ?? 0);
  const subrogationActive = Boolean(sn.subrogation_active);

  type MaintienRow = {
    key: string;
    element: string;
    montant: number;
    commentaire: string;
  };
  const maintienRows: MaintienRow[] = [];
  if (sumPerteMaintien > 0) {
    maintienRows.push({
      key: 'abs-brut',
      element: 'Absence brute',
      montant: -sumPerteMaintien,
      commentaire: 'Déduction pour jours d’arrêt',
    });
  }
  if (subrogationActive && ijssSub !== 0) {
    maintienRows.push({
      key: 'ijss',
      element: 'IJSS subrogées (brut CPAM)',
      montant: ijssBrut,
      commentaire:
        ijssSource === 'cpam_validated'
          ? 'Montant validé Suivi IJSS'
          : 'Montant théorique — valider dans Suivi IJSS',
    });
    if (ijssCsg > 0) {
      maintienRows.push({
        key: 'ijss-csg',
        element: 'CSG/CRDS IJSS',
        montant: -ijssCsg,
        commentaire: 'Calcul automatique',
      });
    }
    if (ijssNet > 0) {
      maintienRows.push({
        key: 'ijss-net',
        element: 'Net IJSS versé',
        montant: ijssNet,
        commentaire: 'Lecture seule',
      });
    }
  }
  if (maintienEmp !== 0) {
    const tauxPct =
      maintienBloc != null
        ? (maintienBloc.maintien.taux_maintien * 100).toFixed(1)
        : '—';
    const nbJours =
      maintienBloc != null ? maintienBloc.maintien.nb_jours_maintien : '—';
    maintienRows.push({
      key: 'maint-emp',
      element: 'Maintien employeur',
      montant: maintienEmp,
      commentaire: `Taux ${tauxPct}% — ${nbJours} jours`,
    });
  }
  if (complementEmp !== 0) {
    maintienRows.push({
      key: 'compl',
      element: 'Complément employeur',
      montant: complementEmp,
      commentaire: 'Part employeur après déduction IJSS',
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Congés & Absences
        </CardTitle>
        <CardDescription>
          Détails des congés payés et absences
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="conges" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="conges">
              Congés Payés ({congesData?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="absences">
              Absences ({absencesData?.length || 0})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="conges" className="mt-4 space-y-3">
            {congesData && congesData.length > 0 ? (
              <div className="space-y-2">
                {congesData.map((conge: any, idx: number) => (
                  <div key={idx} className="p-3 border rounded-lg bg-muted/20">
                    <div className="grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-4">
                        <Input
                          placeholder="Libellé"
                          value={conge.libelle || ''}
                          onChange={(e) => handleCongeChange(idx, 'libelle', e.target.value)}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Qté"
                          value={conge.quantite || 0}
                          onChange={(e) => handleCongeChange(idx, 'quantite', parseFloat(e.target.value) || 0)}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.0001"
                          placeholder="Taux"
                          value={conge.taux || 0}
                          onChange={(e) => handleCongeChange(idx, 'taux', parseFloat(e.target.value) || 0)}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Gain/Perte"
                          value={conge.gain || conge.perte || 0}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value) || 0;
                            if (val >= 0) {
                              handleCongeChange(idx, 'gain', val);
                              handleCongeChange(idx, 'perte', 0);
                            } else {
                              handleCongeChange(idx, 'perte', Math.abs(val));
                              handleCongeChange(idx, 'gain', 0);
                            }
                          }}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2 flex justify-end">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => removeConge(idx)}
                          className="h-8 w-8 p-0"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Aucun congé payé ce mois-ci
              </div>
            )}

            <Button onClick={addConge} variant="outline" className="w-full mt-3">
              <Plus className="h-4 w-4 mr-2" />
              Ajouter un congé
            </Button>
          </TabsContent>

          <TabsContent value="absences" className="mt-4 space-y-3">
            {absencesData && absencesData.length > 0 ? (
              <div className="space-y-2">
                {absencesData.map((absence: any, idx: number) => (
                  <div key={idx} className="p-3 border rounded-lg bg-muted/20">
                    <div className="grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-4">
                        <Input
                          placeholder="Libellé"
                          value={absence.libelle || ''}
                          onChange={(e) => handleAbsenceChange(idx, 'libelle', e.target.value)}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Qté"
                          value={absence.quantite || 0}
                          onChange={(e) => handleAbsenceChange(idx, 'quantite', parseFloat(e.target.value) || 0)}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.0001"
                          placeholder="Taux"
                          value={absence.taux || 0}
                          onChange={(e) => handleAbsenceChange(idx, 'taux', parseFloat(e.target.value) || 0)}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Gain/Perte"
                          value={absence.gain || absence.perte || 0}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value) || 0;
                            if (val >= 0) {
                              handleAbsenceChange(idx, 'gain', val);
                              handleAbsenceChange(idx, 'perte', 0);
                            } else {
                              handleAbsenceChange(idx, 'perte', Math.abs(val));
                              handleAbsenceChange(idx, 'gain', 0);
                            }
                          }}
                          className="h-8"
                        />
                      </div>
                      <div className="col-span-2 flex justify-end">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => removeAbsence(idx)}
                          className="h-8 w-8 p-0"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Aucune absence ce mois-ci
              </div>
            )}

            <Button onClick={addAbsence} variant="outline" className="w-full mt-3">
              <Plus className="h-4 w-4 mr-2" />
              Ajouter une absence
            </Button>
          </TabsContent>
        </Tabs>

        {showMaintienBloc ? (
          <div className="mt-6 space-y-3 border-t pt-6">
            <h3 className="text-sm font-semibold text-foreground">
              Maintien de salaire (impact bulletin)
            </h3>
            {maintienRows.length > 0 ? (
              <div className="overflow-hidden rounded-md border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50 hover:bg-muted/50">
                      <TableHead className="font-medium">Élément</TableHead>
                      <TableHead className="text-right font-medium">Montant</TableHead>
                      <TableHead className="font-medium">Commentaire</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {maintienRows.map((row, idx) => (
                      <TableRow
                        key={row.key}
                        className={cn(idx % 2 === 1 ? 'bg-muted/25' : 'bg-background')}
                      >
                        <TableCell className="align-top">{row.element}</TableCell>
                        <TableCell
                          className={cn(
                            'text-right align-top font-medium tabular-nums',
                            row.montant < 0 ? 'text-red-600' : 'text-green-600'
                          )}
                        >
                          {formatMontantSignedEUR(row.montant)}
                        </TableCell>
                        <TableCell className="text-muted-foreground align-top text-xs">
                          {row.commentaire}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : null}
            {onOpenMaintienModal ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full sm:w-auto"
                onClick={() => onOpenMaintienModal()}
              >
                Voir détail calcul maintien
              </Button>
            ) : null}
            {subrogationActive && ijssSub !== 0 ? (
              <Button variant="link" size="sm" className="px-0 h-auto" asChild>
                <Link to="/suivi-ijss">
                  {ijssSource === 'cpam_validated'
                    ? 'Voir Suivi IJSS (montant validé)'
                    : 'IJSS théoriques — valider dans Suivi IJSS'}
                </Link>
              </Button>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
