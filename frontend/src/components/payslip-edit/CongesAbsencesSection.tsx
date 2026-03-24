// frontend/src/components/payslip-edit/CongesAbsencesSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Calendar, Plus, Trash2 } from 'lucide-react';

interface CongesAbsencesSectionProps {
  congesData: any[];
  absencesData: any[];
  onCongesChange: (data: any[]) => void;
  onAbsencesChange: (data: any[]) => void;
}

export default function CongesAbsencesSection({
  congesData,
  absencesData,
  onCongesChange,
  onAbsencesChange
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
      </CardContent>
    </Card>
  );
}
