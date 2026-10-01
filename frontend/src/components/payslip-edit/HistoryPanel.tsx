// frontend/src/components/payslip-edit/HistoryPanel.tsx

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { History, RotateCcw, Loader2, User, Clock } from 'lucide-react';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { getPayslipHistory, restorePayslipVersion, HistoryEntry } from '@/api/payslips';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  choixApresCorrection,
  type RefusApresCorrection,
} from '@/features/payroll/utils/heuresSurArret';

interface HistoryPanelProps {
  payslipId: string;
  /** Société du bulletin : celle de l'onglet, pas celle qu'un autre onglet a choisie. */
  companyId?: string | null;
  onRestore?: () => void;
  /** Le recalcul d'après la restauration a été refusé pour des heures sur un arrêt : l'écran propose le choix. */
  onRecalculRefuse?: (refus: RefusApresCorrection) => void;
  canRestore?: boolean;
  /** Garde des corrections non enregistrées : faux si la RH préfère les garder. */
  avantRestauration?: () => boolean;
}

export default function HistoryPanel({
  payslipId,
  companyId,
  onRestore,
  onRecalculRefuse,
  canRestore = true,
  avantRestauration,
}: HistoryPanelProps) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRestoring, setIsRestoring] = useState<number | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const data = await getPayslipHistory(payslipId);
        setHistory(data);
      } catch (error: any) {
        toast({
          title: 'Erreur',
          description: error.response?.data?.detail || 'Impossible de charger l\'historique',
          variant: 'destructive',
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, [payslipId, toast]);

  const handleRestore = async (version: number) => {
    if (avantRestauration && !avantRestauration()) return;
    if (
      !confirm(
        `Revenir aux heures sup et aux primes de la version ${version} ? Le bulletin sera recalculé.`
      )
    ) {
      return;
    }

    setIsRestoring(version);
    try {
      const reponse = await restorePayslipVersion(payslipId, version, companyId);
      const suite = choixApresCorrection(reponse);
      if (suite.kind === 'choix') {
        toast({
          title: 'Variables rétablies, bulletin non recalculé',
          description: `${suite.refus.message} Choisissez quoi faire de ces heures.`,
          variant: 'destructive',
        });
        onRecalculRefuse?.(suite.refus);
      } else if (suite.kind === 'regenerer') {
        toast({
          title: 'Variables rétablies, bulletin non recalculé',
          description: `${suite.message} — utilisez « Régénérer ».`,
          variant: 'destructive',
        });
      } else {
        toast({ title: 'Version rétablie', description: reponse.message });
      }
      onRestore?.();
    } catch (error: any) {
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de restaurer cette version',
        variant: 'destructive',
      });
    } finally {
      setIsRestoring(null);
    }
  };

  if (isLoading) {
    return <SharkFinLoader label="Chargement de l'historique…" className="p-12" />;
  }

  if (history.length === 0) {
    return (
      <Card>
        <CardContent className="p-12">
          <div className="text-center text-muted-foreground">
            <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Aucune modification n'a encore été effectuée sur ce bulletin</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Alert>
        <AlertDescription>
          {canRestore
            ? 'Restaurer une version revient à ses heures sup et à ses primes saisies, puis recalcule le bulletin. La version actuelle reste dans l\'historique.'
            : 'La restauration est désactivée : la période de ce bulletin est verrouillée pour l\'édition manuelle.'}
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Versions précédentes
          </CardTitle>
          <CardDescription>
            {history.length} version{history.length > 1 ? 's' : ''} enregistrée{history.length > 1 ? 's' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {history.map((entry) => (
              <div
                key={entry.version}
                className="border rounded-lg p-4 space-y-3 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-lg">Version {entry.version}</span>
                      <span className="text-xs bg-muted px-2 py-1 rounded">
                        {new Date(entry.edited_at).toLocaleDateString('fr-FR')}
                      </span>
                    </div>
                    <p className="text-sm text-foreground">{entry.changes_summary}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRestore(entry.version)}
                    disabled={isRestoring !== null || !canRestore}
                  >
                    {isRestoring === entry.version ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Restaurer
                      </>
                    )}
                  </Button>
                </div>

                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <User className="h-3 w-3" />
                    {entry.edited_by_name ?? 'Système'}
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {new Date(entry.edited_at).toLocaleTimeString('fr-FR')}
                  </div>
                </div>

                {entry.previous_pdf_url && (
                  <div className="pt-2 border-t">
                    <a
                      href={entry.previous_pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline"
                    >
                      Télécharger le PDF de cette version →
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
