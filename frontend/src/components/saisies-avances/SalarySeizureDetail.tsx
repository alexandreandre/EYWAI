// frontend/src/components/saisies-avances/SalarySeizureDetail.tsx

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { SalarySeizure } from '@/api/saisiesAvances';

const SEIZURE_TYPE_LABELS: Record<string, string> = {
  'saisie_arret': 'Saisie-arrêt',
  'pension_alimentaire': 'Pension alimentaire',
  'atd': 'Avis à tiers détenteur',
  'satd': 'Saisie administrative',
};

const STATUS_LABELS: Record<string, string> = {
  'active': 'Active',
  'suspended': 'Suspendue',
  'closed': 'Clôturée',
};

interface SalarySeizureDetailProps {
  seizure: SalarySeizure;
  onClose: () => void;
}

export function SalarySeizureDetail({ seizure, onClose }: SalarySeizureDetailProps) {
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Détails de la saisie</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Type</p>
              <p>{SEIZURE_TYPE_LABELS[seizure.type] || seizure.type}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Statut</p>
              <Badge>{STATUS_LABELS[seizure.status]}</Badge>
            </div>
          </div>

          <div>
            <p className="text-sm font-medium text-muted-foreground">Créancier</p>
            <p>{seizure.creditor_name}</p>
          </div>

          {seizure.creditor_iban && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">IBAN</p>
              <p>{seizure.creditor_iban}</p>
            </div>
          )}

          {seizure.reference_legale && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">Référence légale</p>
              <p>{seizure.reference_legale}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Mode de calcul</p>
              <p>
                {seizure.calculation_mode === 'fixe' && seizure.amount
                  ? `Montant fixe: ${Number(seizure.amount || 0).toFixed(2)}€`
                  : seizure.calculation_mode === 'pourcentage' && seizure.percentage
                  ? `Pourcentage: ${seizure.percentage}%`
                  : 'Barème légal'}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Priorité</p>
              <p>{seizure.priority}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Date de début</p>
              <p>{new Date(seizure.start_date).toLocaleDateString('fr-FR')}</p>
            </div>
            {seizure.end_date && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Date de fin</p>
                <p>{new Date(seizure.end_date).toLocaleDateString('fr-FR')}</p>
              </div>
            )}
          </div>

          {seizure.notes && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">Notes</p>
              <p className="text-sm">{seizure.notes}</p>
            </div>
          )}

          <div>
            <p className="text-sm font-medium text-muted-foreground">Créée le</p>
            <p>{new Date(seizure.created_at).toLocaleString('fr-FR')}</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
