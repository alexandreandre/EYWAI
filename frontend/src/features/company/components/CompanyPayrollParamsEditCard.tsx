import { useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import type { CompanyDetails } from '@/api/company';
import { patchCompanyDetails } from '@/api/company';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';

export function CompanyPayrollParamsEditCard({
  company,
  canEdit,
  onSaved,
}: {
  company: CompanyDetails;
  canEdit: boolean;
  onSaved?: () => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [tauxAtMp, setTauxAtMp] = useState(
    company.taux_at_mp != null ? String(company.taux_at_mp) : '',
  );
  const [jourFin, setJourFin] = useState(
    company.paie_jour_de_fin != null ? String(company.paie_jour_de_fin) : '',
  );
  const [occurrence, setOccurrence] = useState(
    company.paie_occurrence != null ? String(company.paie_occurrence) : '',
  );

  if (!canEdit) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await patchCompanyDetails({
        taux_at_mp: tauxAtMp === '' ? undefined : Number(tauxAtMp.replace(',', '.')),
        paie_jour_de_fin: jourFin === '' ? undefined : Number(jourFin),
        paie_occurrence: occurrence === '' ? undefined : Number(occurrence),
      } as Parameters<typeof patchCompanyDetails>[0]);
      toast({ title: 'Paramètres paie enregistrés' });
      onSaved?.();
    } catch {
      toast({ title: 'Erreur', description: 'Enregistrement impossible.', variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-dashed bg-muted/20 p-4 space-y-3">
      <p className="text-sm font-medium">Compléter les paramètres paie</p>
      <p className="text-xs text-muted-foreground">
        Ces champs peuvent aussi être préremplis par un import DSN. Saisie manuelle en filet de
        sécurité.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="taux-at-mp">Taux AT/MP (%)</Label>
          <Input
            id="taux-at-mp"
            inputMode="decimal"
            value={tauxAtMp}
            onChange={(e) => setTauxAtMp(e.target.value)}
            placeholder="ex. 3.66"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="paie-jour-fin">Jour fin période</Label>
          <Input
            id="paie-jour-fin"
            inputMode="numeric"
            value={jourFin}
            onChange={(e) => setJourFin(e.target.value)}
            placeholder="ex. 31"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="paie-occurrence">Occurrence (-1 = dernier du mois)</Label>
          <Input
            id="paie-occurrence"
            inputMode="numeric"
            value={occurrence}
            onChange={(e) => setOccurrence(e.target.value)}
            placeholder="ex. -1"
          />
        </div>
      </div>
      <Button type="button" size="sm" onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Enregistrer
      </Button>
    </div>
  );
}
