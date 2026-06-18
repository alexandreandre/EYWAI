import { Link } from 'react-router-dom';
import { ExternalLink, UserPlus } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { WorkforceGap, WorkforceResolution } from '@/api/dsnImport';

type Props = {
  gap: WorkforceGap;
  resolution?: WorkforceResolution;
  onResolutionChange: (resolution: WorkforceResolution) => void;
};

function formatDateFr(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso.slice(0, 10));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('fr-FR');
}

export function WorkforceNewHireGapRow({ gap, resolution, onResolutionChange }: Props) {
  const hireLabel = formatDateFr(gap.hire_date);
  const periodLabel = gap.period ?? '—';

  const confirmNewHire = () => {
    onResolutionChange({
      gap_id: gap.gap_id,
      employee_id: gap.employee_id,
      action: 'acknowledge_new_hire',
      hire_date: gap.hire_date ?? null,
    });
  };

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/30 p-4 space-y-4">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">{gap.employee_name}</p>
          <Badge variant="outline" className="text-xs border-blue-300 text-blue-800">
            Embauche récente
          </Badge>
          {resolution && (
            <Badge variant="secondary" className="text-xs">
              Décision enregistrée
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          NIR {gap.nir_masked}
          {hireLabel && <> · Embauche : {hireLabel}</>}
          {' · '}
          DSN : {periodLabel}
        </p>
        <p className="text-sm text-blue-900/80">
          Normal si la première paie n&apos;est pas encore dans ce fichier DSN.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={confirmNewHire}>
          <UserPlus className="mr-2 h-3.5 w-3.5" />
          Confirmer — embauche récente
        </Button>
        <Button type="button" size="sm" variant="outline" asChild>
          <Link to={`/employees/${gap.employee_id}`} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="mr-2 h-3.5 w-3.5" />
            Voir la fiche salarié
          </Link>
        </Button>
      </div>
    </div>
  );
}
