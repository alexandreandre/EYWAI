// frontend/src/components/saisies-avances/SalarySeizureDetail.tsx

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { updateSalarySeizure } from '@/api/saisiesAvances';
import type { SalarySeizure } from '@/api/saisiesAvances';
import { eurosFr } from '@/lib/paliersAffichage';
import {
  libellePersonnesACharge,
  libelleStatutSaisie,
  modificationDesMontants,
} from './seizureFormat';

const SEIZURE_TYPE_LABELS: Record<string, string> = {
  'saisie_arret': 'Saisie-arrêt',
  'pension_alimentaire': 'Pension alimentaire',
  'atd': 'Avis à tiers détenteur',
  'satd': 'Saisie administrative',
};

function texteDuMontant(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined || String(valeur) === '') return '';
  const n = Number(valeur);
  return Number.isFinite(n) ? String(n) : '';
}

interface SaisieMontantsEditablesProps {
  seizure: SalarySeizure;
  onUpdated?: (seizure: SalarySeizure) => void;
}

/**
 * Mensualité et montant total de la dette, modifiables ; ce qui a déjà été
 * retenu et le reste dû, calculés par le serveur. La retenue s'arrête seule
 * quand le reste dû atteint zéro (demande d'Elsa du 24/11/2026).
 */
export function SaisieMontantsEditables({ seizure, onUpdated }: SaisieMontantsEditablesProps) {
  const [mensualite, setMensualite] = useState(texteDuMontant(seizure.amount));
  const [total, setTotal] = useState(texteDuMontant(seizure.montant_total));
  const [erreur, setErreur] = useState<string | null>(null);
  const [enregistre, setEnregistre] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const avecMensualite = seizure.calculation_mode !== 'pourcentage';
  const aUnTotal = seizure.montant_total !== null && seizure.montant_total !== undefined;

  const enregistrer = async () => {
    setEnregistre(null);
    const modification = modificationDesMontants(seizure, { mensualite, total });
    if (typeof modification === 'string') {
      setErreur(modification);
      return;
    }
    if (Object.keys(modification).length === 0) {
      setErreur(null);
      setEnregistre('Rien à enregistrer : les montants n’ont pas changé.');
      return;
    }
    setEnCours(true);
    try {
      const misAJour = await updateSalarySeizure(seizure.id, modification);
      setErreur(null);
      setEnregistre('Montants enregistrés : ils s’appliquent aux prochains bulletins calculés.');
      onUpdated?.(misAJour);
    } catch (error: any) {
      setErreur(error?.response?.data?.detail || 'Impossible d’enregistrer les montants.');
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="space-y-3 rounded-md border p-4">
      <div className="grid grid-cols-2 gap-4">
        {avecMensualite && (
          <div>
            <Label htmlFor="seizure-amount-edit">Mensualité (€)</Label>
            <Input
              id="seizure-amount-edit"
              inputMode="decimal"
              value={mensualite}
              onChange={(e) => setMensualite(e.target.value)}
            />
            {seizure.calculation_mode === 'barème_legal' && (
              <p className="text-xs text-muted-foreground mt-1">
                Vide : la quotité saisissable du mois.
              </p>
            )}
          </div>
        )}
        <div>
          <Label htmlFor="seizure-total-edit">Montant total de la dette (€)</Label>
          <Input
            id="seizure-total-edit"
            inputMode="decimal"
            value={total}
            onChange={(e) => setTotal(e.target.value)}
          />
          <p className="text-xs text-muted-foreground mt-1">
            Vide : la saisie court sans fin.
          </p>
        </div>
      </div>
      {aUnTotal && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Déjà retenu</p>
            <p>{eurosFr(Number(seizure.total_retenu ?? 0))}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Reste dû</p>
            <p className="font-semibold">{eurosFr(Number(seizure.reste_du ?? 0))}</p>
          </div>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        La retenue du mois ne dépasse ni la quotité saisissable (barème légal) ni le reste dû ;
        à zéro, la saisie se termine.
      </p>
      {erreur && <p className="text-sm text-destructive">{erreur}</p>}
      {enregistre && <p className="text-sm text-muted-foreground">{enregistre}</p>}
      <div className="flex justify-end">
        <Button type="button" size="sm" onClick={enregistrer} disabled={enCours}>
          {enCours && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          Enregistrer
        </Button>
      </div>
    </div>
  );
}

interface SalarySeizureDetailProps {
  seizure: SalarySeizure;
  onClose: () => void;
  onUpdated?: (seizure: SalarySeizure) => void;
}

export function SalarySeizureDetail({ seizure, onClose, onUpdated }: SalarySeizureDetailProps) {
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
              <Badge>{libelleStatutSaisie(seizure)}</Badge>
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

          <SaisieMontantsEditables key={seizure.id} seizure={seizure} onUpdated={onUpdated} />

          <div>
            <p className="text-sm font-medium text-muted-foreground">Personnes à charge</p>
            <p>{libellePersonnesACharge(seizure.dependents_count)}</p>
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
