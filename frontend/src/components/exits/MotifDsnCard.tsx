// Le motif de fin de contrat déclaré en DSN, sur le dossier de sortie.
import { useState } from 'react';
import { updateEmployeeExit, type MotifDsnDossier } from '@/api/employeeExits';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { MOTIF_PROPOSE, phraseMotifDsn, valeurMotifDsn } from './motifDsn';

export function MotifDsnCard({
  exitId,
  motif,
  disabled,
  onSaved,
}: {
  exitId: string;
  motif: MotifDsnDossier;
  disabled: boolean;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  if (motif.options.length === 0) return null;

  const choisir = async (valeur: string) => {
    setSaving(true);
    try {
      await updateEmployeeExit(exitId, { motif_dsn: valeur === MOTIF_PROPOSE ? null : valeur });
      toast({ title: 'Motif DSN enregistré' });
      onSaved();
    } catch (error: unknown) {
      toast({
        title: 'Motif non enregistré',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Le motif DSN n'a pas pu être enregistré : réessayez.",
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card data-testid="motif-dsn">
      <CardHeader>
        <CardTitle>Motif de fin de contrat en DSN</CardTitle>
        <CardDescription>
          Ce motif part à France Travail : il pèse sur les droits au chômage du salarié.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Select value={valeurMotifDsn(motif)} disabled={disabled || saving} onValueChange={(v) => void choisir(v)}>
          <SelectTrigger aria-label="Motif DSN">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={MOTIF_PROPOSE}>
              {motif.propose ? `Motif proposé par Martine (${motif.propose})` : 'À choisir'}
            </SelectItem>
            {motif.options.map((option) => (
              <SelectItem key={option.code} value={option.code}>
                {option.code} : {option.libelle}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className={motif.alerte ? 'text-sm text-amber-700 dark:text-amber-400' : 'text-sm text-muted-foreground'}>
          {phraseMotifDsn(motif)}
        </p>
      </CardContent>
    </Card>
  );
}
