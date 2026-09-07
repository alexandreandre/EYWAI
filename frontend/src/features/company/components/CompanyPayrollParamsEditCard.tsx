import { useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import type { CompanyDetails } from '@/api/company';
import { patchCompanyDetails } from '@/api/company';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import {
  DESCRIPTIONS_REGIME_PERIODE_PAIE,
  LIBELLES_REGIME_PERIODE_PAIE,
  PAIRE_AVANT_DERNIER_VENDREDI,
  PAIRE_MOIS_CIVIL,
  formatJourDeFin,
  formatOccurrence,
  regimePeriodePaie,
  type RegimePeriodePaie,
} from '@/features/company/lib/periodePaie';

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
  const regimeInitial = regimePeriodePaie(
    company.paie_jour_de_fin,
    company.paie_occurrence,
  );
  const [regime, setRegime] = useState<RegimePeriodePaie>(regimeInitial);

  if (!canEdit) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await patchCompanyDetails({
        taux_at_mp: tauxAtMp === '' ? undefined : Number(tauxAtMp.replace(',', '.')),
        // Un régime « personnalisé » ou non choisi n'écrase jamais le couple
        // (jour_de_fin, occurrence) existant.
        ...(regime === 'avant_dernier_vendredi' ? PAIRE_AVANT_DERNIER_VENDREDI : {}),
        ...(regime === 'mois_civil' ? PAIRE_MOIS_CIVIL : {}),
      });
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
      <div className="grid gap-3 sm:grid-cols-2">
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
          <Label>Arrêté de la période de paie</Label>
          <Select
            value={regime === 'non_defini' ? '' : regime}
            onValueChange={(v) => setRegime(v as RegimePeriodePaie)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choisir un régime…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="avant_dernier_vendredi">
                {LIBELLES_REGIME_PERIODE_PAIE.avant_dernier_vendredi}
              </SelectItem>
              <SelectItem value="mois_civil">
                {LIBELLES_REGIME_PERIODE_PAIE.mois_civil}
              </SelectItem>
              {regimeInitial === 'personnalise' ? (
                <SelectItem value="personnalise">
                  {LIBELLES_REGIME_PERIODE_PAIE.personnalise} —{' '}
                  {formatJourDeFin(company.paie_jour_de_fin)},{' '}
                  {formatOccurrence(company.paie_occurrence).toLowerCase()}
                </SelectItem>
              ) : null}
            </SelectContent>
          </Select>
          {regime !== 'non_defini' ? (
            <p className="text-xs text-muted-foreground">
              {DESCRIPTIONS_REGIME_PERIODE_PAIE[regime]}
            </p>
          ) : null}
        </div>
      </div>
      <Button type="button" size="sm" onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Enregistrer
      </Button>
    </div>
  );
}
