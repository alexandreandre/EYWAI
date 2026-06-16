import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import type { CompanyDetails } from '@/api/company';
import type { DsnCoverage, DsnSyncMode } from '@/api/dsnImport';
import { patchCompanyDetails } from '@/api/company';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { DsnCoverageTimeline, dsnStatusLabel, dsnStatusVariant } from './DsnCoverageTimeline';
import { Badge } from '@/components/ui/badge';

const MODE_LABELS: Record<DsnSyncMode, string> = {
  external: 'Paie hors EYWAI (Cegid, etc.)',
  native: 'Paie calculée dans EYWAI',
  transition: 'Reprise en cours',
};

type Props = {
  company: CompanyDetails;
  coverage?: DsnCoverage | null;
  readOnly?: boolean;
  onUpdated?: () => void;
};

export function DsnSyncModeCard({ company, coverage, readOnly = false, onUpdated }: Props) {
  const { toast } = useToast();
  const initial = (company as CompanyDetails & { dsn_sync_mode?: DsnSyncMode }).dsn_sync_mode ?? 'native';
  const [mode, setMode] = useState<DsnSyncMode>(initial);
  const [saving, setSaving] = useState(false);

  const saveMode = async (next: DsnSyncMode) => {
    setMode(next);
    if (readOnly) return;
    setSaving(true);
    try {
      await patchCompanyDetails({ dsn_sync_mode: next } as Parameters<typeof patchCompanyDetails>[0]);
      toast({ title: 'Mode DSN enregistré' });
      onUpdated?.();
    } catch {
      toast({ title: 'Erreur', description: 'Impossible de mettre à jour le mode DSN.', variant: 'destructive' });
      setMode(initial);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card id="dsn-sync">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <RefreshCw className="h-4 w-4 text-muted-foreground" />
          Synchronisation DSN
        </CardTitle>
        <CardDescription>
          Source de paie et couverture des imports mensuels (lecture seule côté RH).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!readOnly && (
          <div className="space-y-2">
            <Label>Source de paie</Label>
            <Select value={mode} onValueChange={(v) => saveMode(v as DsnSyncMode)} disabled={saving}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(MODE_LABELS) as DsnSyncMode[]).map((k) => (
                  <SelectItem key={k} value={k}>
                    {MODE_LABELS[k]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {readOnly && (
          <p className="text-sm text-muted-foreground">{MODE_LABELS[mode] ?? mode}</p>
        )}

        {coverage && (
          <div className="space-y-3 rounded-lg border bg-muted/20 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={dsnStatusVariant(coverage.status)}>{dsnStatusLabel(coverage.status)}</Badge>
              {coverage.last_period && (
                <span className="text-xs text-muted-foreground">
                  Dernier mois importé : {coverage.last_period}
                </span>
              )}
            </div>
            <DsnCoverageTimeline timeline={coverage.timeline} compact />
            {coverage.gaps.length > 0 && (
              <p className="text-xs text-amber-800">
                Mois manquants : {coverage.gaps.join(', ')}
              </p>
            )}
            {mode === 'native' && (
              <p className="text-xs text-muted-foreground">
                Les cumuls sont maintenus par la paie EYWAI — import DSN optionnel.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
