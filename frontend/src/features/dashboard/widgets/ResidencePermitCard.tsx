import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import type { ResidencePermitStats } from '@/features/dashboard/types';

interface ResidencePermitCardProps {
  stats: ResidencePermitStats | null;
  loading: boolean;
}

export function ResidencePermitCard({ stats, loading }: ResidencePermitCardProps) {
  const displayStats = stats || {
    total_expire: 0,
    total_a_renouveler: 0,
    total_a_renseigner: 0,
    total_valide: 0,
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Titres de séjour</CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Suivi des échéances administratives</p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 border border-red-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-red-500"></div>
                <span className="text-sm font-medium text-red-900">Expiré</span>
              </div>
              <span className="text-lg font-bold text-red-700">{displayStats.total_expire}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-orange-500"></div>
                <span className="text-sm font-medium text-orange-900">À renouveler</span>
              </div>
              <span className="text-lg font-bold text-orange-700">{displayStats.total_a_renouveler}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-gray-500"></div>
                <span className="text-sm font-medium text-gray-900">À renseigner</span>
              </div>
              <span className="text-lg font-bold text-gray-700">{displayStats.total_a_renseigner}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 border border-green-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500"></div>
                <span className="text-sm font-medium text-green-900">Valide</span>
              </div>
              <span className="text-lg font-bold text-green-700">{displayStats.total_valide}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
