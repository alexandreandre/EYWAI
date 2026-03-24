// src/components/exports/ExportHistoryModal.tsx
// Modal pour afficher l'historique d'un type d'export spécifique

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ExportHistory } from "./ExportHistory";

interface ExportHistoryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  exportType: string;
  exportName: string;
}

export function ExportHistoryModal({ open, onOpenChange, exportType, exportName }: ExportHistoryModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Historique {exportName}</DialogTitle>
        </DialogHeader>
        <div className="mt-4">
          <ExportHistory exportType={exportType} hideHeader={true} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
