import { log } from '@/lib/logger';
import { useNavigate } from 'react-router-dom';
import * as ribAlertsApi from '@/api/ribAlerts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Landmark, Loader2 } from 'lucide-react';

interface RibAlertsCardProps {
  alerts: ribAlertsApi.RibAlert[];
  loading: boolean;
  onRefresh: () => void;
}

export function RibAlertsCard({ alerts, loading, onRefresh }: RibAlertsCardProps) {
  const navigate = useNavigate();

  const handleMarkRead = async (id: string) => {
    try {
      await ribAlertsApi.markRibAlertRead(id);
      onRefresh();
    } catch (e) {
      log.error(e);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Landmark className="h-5 w-5" />
            Alertes RIB
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Landmark className="h-5 w-5" />
          Alertes RIB
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Modification ou doublon de RIB</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground py-2">Aucune alerte RIB.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3 rounded-lg border text-sm ${alert.is_read ? 'bg-muted/50 border-muted' : 'bg-amber-50/50 border-amber-200'}`}
            >
              <div className="font-medium text-foreground">{alert.title}</div>
              <p className="text-muted-foreground mt-1 line-clamp-2">{alert.message}</p>
              <div className="flex items-center justify-between mt-2 gap-2">
                <span className="text-xs text-muted-foreground">
                  {new Date(alert.created_at).toLocaleDateString('fr-FR')}
                </span>
                <div className="flex gap-1">
                  {alert.employee_id && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => navigate(`/employees/${alert.employee_id}`)}
                    >
                      Fiche
                    </Button>
                  )}
                  {!alert.is_read && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => handleMarkRead(alert.id)}
                    >
                      Marquer lu
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
