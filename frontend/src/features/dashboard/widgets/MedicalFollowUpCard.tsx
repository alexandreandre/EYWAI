import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronRight, Loader2, Stethoscope } from 'lucide-react';
import type { KPIs } from '@/api/medicalFollowUp';

interface MedicalFollowUpCardProps {
  kpis: KPIs | null;
  loading: boolean;
}

export function MedicalFollowUpCard({ kpis, loading }: MedicalFollowUpCardProps) {
  const navigate = useNavigate();
  const overdue = kpis?.overdue_count ?? 0;
  const due30 = kpis?.due_within_30_count ?? 0;
  const totalAVenir = overdue + due30;
  const hasAlert = totalAVenir > 0;

  return (
    <Card className={hasAlert ? 'border-teal-200' : ''}>
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Stethoscope className="h-5 w-5 text-teal-600" />
          Suivi visites médicales
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin inline" />
          ) : (
            <span className={totalAVenir > 0 ? 'font-bold text-teal-700' : ''}>
              {totalAVenir > 0 ? `${totalAVenir} visite${totalAVenir > 1 ? 's' : ''} à venir` : 'À jour'}
            </span>
          )}
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            {overdue > 0 && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 border border-red-200">
                <span className="text-sm font-medium text-red-900">En retard</span>
                <span className="text-lg font-bold text-red-700">{overdue}</span>
              </div>
            )}
            {due30 > 0 && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-200">
                <span className="text-sm font-medium text-orange-900">Échéance &lt; 30 j</span>
                <span className="text-lg font-bold text-orange-700">{due30}</span>
              </div>
            )}
            {!hasAlert && (
              <p className="text-sm text-muted-foreground py-2">Aucune visite à planifier.</p>
            )}
            <Button variant="outline" size="sm" className="w-full mt-2" onClick={() => navigate('/medical-follow-up')}>
              Voir le suivi médical
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
