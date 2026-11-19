// src/components/exports/DsnTab.tsx
// Onglet « DSN » des exports (demande d'Elsa du 17/11/2026) : ce qui sort
// chaque mois autour de la déclaration, au même endroit.

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Calculator, FileSpreadsheet, FileText, History, type LucideIcon } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ExportCommonModel } from "./ExportCommonModel";
import { ExportHistoryModal } from "./ExportHistoryModal";
import DsnTransmissionsPanel from "@/features/net-entreprises/components/DsnTransmissionsPanel";

/** Carte de l'onglet : `id` est celui qu'attend ExportCommonModel, `type` celui de l'historique. */
export const EXPORTS_DSN: { id: string; type: string; name: string; description: string; icon: LucideIcon }[] = [
  {
    id: "dsn_mensuelle",
    type: "dsn_mensuelle",
    name: "Déclaration mensuelle",
    description: "DSN mensuelle à déposer sur Net-entreprises",
    icon: FileText,
  },
  {
    id: "charges-sociales",
    type: "charges_sociales",
    name: "Charges sociales par caisse",
    description: "Cotisations du mois par organisme (URSSAF, retraite, prévoyance, mutuelle…), comme déclarées",
    icon: FileSpreadsheet,
  },
  {
    id: "od_globale",
    type: "od_globale",
    name: "OD globale de paie",
    description: "Écritures comptables du mois : salaires, charges, PAS, acomptes, saisies, prêts",
    icon: Calculator,
  },
  {
    id: "journal_paie",
    type: "journal_paie",
    name: "Journal de paie",
    description: "Journal de paie du mois pour la comptabilité",
    icon: FileText,
  },
];

export function DsnTab({ initialExportId }: { initialExportId?: string | null }) {
  const [selectedExport, setSelectedExport] = useState<string | null>(null);

  // Lien « Ouvrir le journal de paie » des envois : la carte s'ouvre.
  useEffect(() => {
    if (initialExportId && EXPORTS_DSN.some((e) => e.id === initialExportId)) {
      setSelectedExport(initialExportId);
    }
  }, [initialExportId]);
  const [historyModal, setHistoryModal] = useState<{ exportType: string; exportName: string } | null>(null);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>DSN</CardTitle>
          <CardDescription>
            La déclaration du mois et les exports qui l&apos;accompagnent. Ces exports sont en lecture seule et ne
            déposent rien automatiquement.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {EXPORTS_DSN.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.id} className="relative">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 flex-1">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <CardTitle className="text-lg">{item.name}</CardTitle>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-foreground"
                    onClick={() => setHistoryModal({ exportType: item.type, exportName: item.name })}
                    title="Voir l'historique"
                  >
                    <History className="h-4 w-4" />
                  </Button>
                </div>
                <CardDescription className="mt-2">{item.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={() => {
                    setHistoryModal(null);
                    setSelectedExport(item.id);
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

      <DsnTransmissionsPanel />

      {selectedExport && (
        <Dialog open={!!selectedExport} onOpenChange={(open) => !open && setSelectedExport(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <ExportCommonModel
              exportType={selectedExport}
              exportDescription={EXPORTS_DSN.find((e) => e.id === selectedExport)?.description || ""}
              onClose={() => setSelectedExport(null)}
            />
          </DialogContent>
        </Dialog>
      )}

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
