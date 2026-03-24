// src/components/exports/PaieComptabiliteTab.tsx
// Sous-onglet Paie & Comptabilité - ÉTAPE 1

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, Calculator, Database, History } from "lucide-react";
import { ExportCommonModel } from "./ExportCommonModel";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ExportHistoryModal } from "./ExportHistoryModal";

export function PaieComptabiliteTab() {
  const [selectedExport, setSelectedExport] = useState<string | null>(null);
  const [historyModal, setHistoryModal] = useState<{ exportType: string; exportName: string } | null>(null);

  // Mapping entre les IDs des cartes et les types d'export de l'API
  const exportTypeMapping: Record<string, string> = {
    journal_paie: "journal_paie",
    od_salaires: "od_salaires",
    od_charges_sociales: "od_charges_sociales",
    od_pas: "od_pas",
    od_globale: "od_globale",
    export_cabinet_generique: "export_cabinet_generique",
    export_cabinet_quadra: "export_cabinet_quadra",
    export_cabinet_sage: "export_cabinet_sage",
  };

  const exports = [
    {
      id: "journal_paie",
      name: "Journal de paie",
      description: "Export du journal de paie pour la comptabilité générale",
      icon: FileText,
    },
    {
      id: "od_salaires",
      name: "OD Salaires",
      description: "Écritures comptables pour les salaires bruts et nets à payer",
      icon: Calculator,
    },
    {
      id: "od_charges_sociales",
      name: "OD Charges sociales",
      description: "Écritures comptables pour les charges sociales par caisse",
      icon: Calculator,
    },
    {
      id: "od_pas",
      name: "OD PAS",
      description: "Écritures comptables pour le prélèvement à la source",
      icon: Calculator,
    },
    {
      id: "od_globale",
      name: "OD Globale de paie",
      description: "Écritures comptables complètes de paie (salaires + charges + PAS)",
      icon: Calculator,
    },
    {
      id: "export_cabinet_generique",
      name: "Export format cabinet générique",
      description: "Export structuré pour intégration dans les logiciels comptables",
      icon: Database,
    },
    {
      id: "export_cabinet_quadra",
      name: "Export format Quadra",
      description: "Export au format Quadra (structure standardisée)",
      icon: Database,
    },
    {
      id: "export_cabinet_sage",
      name: "Export format Sage",
      description: "Export au format Sage (structure standardisée)",
      icon: Database,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Description */}
      <Card>
        <CardHeader>
          <CardTitle>Paie & Comptabilité</CardTitle>
          <CardDescription>
            Exports destinés à la transmission des données de paie à la comptabilité.
            Ces exports sont en lecture seule et ne modifient aucune donnée.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Liste des exports */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {exports.map((exportItem) => {
          const Icon = exportItem.icon;
          const exportType = exportTypeMapping[exportItem.id];
          return (
            <Card key={exportItem.id} className={exportItem.disabled ? "opacity-50" : "relative"}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <CardTitle className="text-lg">{exportItem.name}</CardTitle>
                  </div>
                  {exportType && !exportItem.disabled && (
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
                  disabled={exportItem.disabled}
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
              exportType={selectedExport}
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

