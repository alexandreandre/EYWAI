// src/components/exports/ExportsRhTab.tsx
// Sous-onglet Exports RH - ÉTAPE 1

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Calendar, Receipt, FileSpreadsheet, History } from "lucide-react";
import { ExportCommonModel } from "./ExportCommonModel";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ExportHistoryModal } from "./ExportHistoryModal";

export function ExportsRhTab() {
  const [selectedExport, setSelectedExport] = useState<string | null>(null);
  const [historyModal, setHistoryModal] = useState<{ exportType: string; exportName: string } | null>(null);

  // Mapping entre les IDs des cartes et les types d'export de l'API
  const exportTypeMapping: Record<string, string> = {
    "charges-sociales": "charges_sociales",
    "conges-absences": "conges_absences",
    "notes-frais": "notes_frais",
  };

  const exports = [
    {
      id: "charges-sociales",
      name: "Charges sociales par caisse",
      description: "Tableau détaillé des charges sociales par organisme (URSSAF, Retraite, etc.)",
      icon: FileSpreadsheet,
    },
    {
      id: "conges-absences",
      name: "Congés payés / Absences",
      description: "Export des congés payés et absences pour analyse RH",
      icon: Calendar,
    },
    {
      id: "notes-frais",
      name: "Notes de frais",
      description: "Export des notes de frais pour traitement comptable",
      icon: Receipt,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Description */}
      <Card>
        <CardHeader>
          <CardTitle>Exports RH</CardTitle>
          <CardDescription>
            Extractions RH complètes et auditables pour analyse, reporting et transmission externe.
            Ces exports sont en lecture seule et ne modifient aucune donnée RH.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Liste des exports */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {exports.map((exportItem) => {
          const Icon = exportItem.icon;
          const exportType = exportTypeMapping[exportItem.id];
          return (
            <Card key={exportItem.id} className="relative">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <CardTitle className="text-lg">{exportItem.name}</CardTitle>
                  </div>
                  {exportType && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-foreground"
                      onClick={() => setHistoryModal({ exportType, exportName: exportItem.name })}
                      title="Voir l'historique"
                    >
                      <History className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <CardDescription className="mt-2">{exportItem.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={() => {
                    // Fermer le modal d'historique si ouvert
                    if (historyModal) {
                      setHistoryModal(null);
                    }
                    setSelectedExport(exportItem.id);
                  }}
                  className="w-full"
                >
                  Configurer
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Modal d'export */}
      {selectedExport && (
        <Dialog open={!!selectedExport} onOpenChange={(open) => !open && setSelectedExport(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <ExportCommonModel
              exportType={exports.find(e => e.id === selectedExport)?.name || ""}
              exportDescription={exports.find(e => e.id === selectedExport)?.description || ""}
              onClose={() => setSelectedExport(null)}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Modal d'historique */}
      {historyModal && (
        <ExportHistoryModal
          open={!!historyModal}
          onOpenChange={(open) => !open && setHistoryModal(null)}
          exportType={historyModal.exportType}
          exportName={historyModal.exportName}
        />
      )}
    </div>
  );
}

