import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  enregistrerReglageActivitePartielle,
  lireReglageActivitePartielle,
  type ReglageActivitePartielle,
} from '@/api/activitePartielle';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';

function nombre(t: string): number | null {
  const v = Number.parseFloat(t.trim().replace(',', '.'));
  return Number.isFinite(v) ? v : null;
}

/**
 * Activité partielle de la société (retour d'Elsa du 16/11 : « mets-la dans
 * les paramètres ») : activée ou non, période, taux. Valeurs légales par
 * défaut (service-public F23503, vérifiée le 13/08/2026).
 */
export default function ActivitePartielleSettingsCard() {
  const companyId = useActiveCompanyId();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ['activite-partielle-reglage', companyId],
    queryFn: lireReglageActivitePartielle,
    enabled: Boolean(companyId),
  });
  const [r, setR] = useState<ReglageActivitePartielle | null>(null);
  const [taux, setTaux] = useState('60');
  const [plancher, setPlancher] = useState('9,74');
  const [plafond, setPlafond] = useState('33,24');
  const [heuresJour, setHeuresJour] = useState('');
  useEffect(() => {
    if (!data) return;
    setR(data);
    setTaux(String(data.taux_indemnite).replace('.', ','));
    setPlancher(data.plancher_horaire.toFixed(2).replace('.', ','));
    setPlafond(data.plafond_horaire.toFixed(2).replace('.', ','));
    setHeuresJour(data.heures_par_jour != null ? String(data.heures_par_jour).replace('.', ',') : '');
  }, [data]);

  const tauxN = nombre(taux);
  const plancherN = nombre(plancher);
  const plafondN = nombre(plafond);
  const heuresJourN = heuresJour.trim() === '' ? null : nombre(heuresJour);
  const invalide =
    !r ||
    tauxN == null || tauxN <= 0 || tauxN > 100 ||
    plancherN == null || plancherN < 0 ||
    plafondN == null || plafondN <= 0 ||
    (heuresJour.trim() !== '' && (heuresJourN == null || heuresJourN <= 0 || heuresJourN > 24)) ||
    Boolean(r.date_debut && r.date_fin && r.date_fin < r.date_debut);

  const enregistrer = useMutation({
    mutationFn: () =>
      enregistrerReglageActivitePartielle({
        ...r!,
        taux_indemnite: tauxN!,
        plancher_horaire: plancherN!,
        plafond_horaire: plafondN!,
        heures_par_jour: heuresJourN,
        date_debut: r!.date_debut || null,
        date_fin: r!.date_fin || null,
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(['activite-partielle-reglage', companyId], saved);
      void queryClient.invalidateQueries({ queryKey: ['activite-partielle-mois', companyId] });
      toast({
        title: 'Enregistré',
        description: saved.active
          ? 'Les heures chômées se saisissent dans Temps de travail & HS, onglet « Activité partielle ».'
          : 'L’activité partielle est coupée pour cette société.',
      });
    },
    onError: (e) =>
      toast({ title: 'Rien n’a été changé', description: getUserErrorMessage(e), variant: 'destructive' }),
  });

  if (!r) return null;
  return (
    <Card data-testid="reglage-activite-partielle">
      <CardHeader>
        <CardTitle className="text-base">Activité partielle</CardTitle>
        <CardDescription>
          Chômage partiel autorisé par la DDETS : Martine calcule la retenue des heures chômées et
          l’indemnité, sur le bulletin du mois.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex items-center gap-2">
          <Switch
            id="ap-active"
            checked={r.active}
            onCheckedChange={(v) => setR({ ...r, active: v })}
          />
          <Label htmlFor="ap-active">Activité partielle en cours dans cette société</Label>
        </div>
        {r.active && (
          <div className="space-y-3 rounded-md border p-3">
            <div className="flex flex-wrap items-end gap-3">
              <div className="grid gap-1">
                <Label htmlFor="ap-debut">Début</Label>
                <Input
                  id="ap-debut"
                  type="date"
                  className="h-8 w-40"
                  value={r.date_debut ?? ''}
                  onChange={(e) => setR({ ...r, date_debut: e.target.value || null })}
                />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="ap-fin">Fin (facultatif)</Label>
                <Input
                  id="ap-fin"
                  type="date"
                  className="h-8 w-40"
                  value={r.date_fin ?? ''}
                  onChange={(e) => setR({ ...r, date_fin: e.target.value || null })}
                />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="ap-decision">Décision d’autorisation (facultatif)</Label>
                <Input
                  id="ap-decision"
                  className="h-8 w-56"
                  placeholder="n° ou date de la décision"
                  value={r.reference_decision ?? ''}
                  onChange={(e) => setR({ ...r, reference_decision: e.target.value || null })}
                />
              </div>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div className="grid gap-1">
                <Label htmlFor="ap-taux">Indemnité (% du salaire horaire brut)</Label>
                <Input id="ap-taux" inputMode="decimal" className="h-8 w-24 text-right" value={taux} onChange={(e) => setTaux(e.target.value)} />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="ap-plancher">Plancher (€ / heure)</Label>
                <Input id="ap-plancher" inputMode="decimal" className="h-8 w-24 text-right" value={plancher} onChange={(e) => setPlancher(e.target.value)} />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="ap-plafond">Plafond (€ / heure)</Label>
                <Input id="ap-plafond" inputMode="decimal" className="h-8 w-24 text-right" value={plafond} onChange={(e) => setPlafond(e.target.value)} />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="ap-jour">Heures par jour chômé</Label>
                <Input
                  id="ap-jour"
                  inputMode="decimal"
                  className="h-8 w-24 text-right"
                  placeholder="contrat ÷ 5"
                  value={heuresJour}
                  onChange={(e) => setHeuresJour(e.target.value)}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              La loi : 60 % du salaire brut par heure chômée, entre 9,74 € et 33,24 € de l’heure
              (service-public, vérifié le 13/08/2026). Un accord ou une décision de l’employeur peut
              prévoir plus : changez le pourcentage. L’indemnité ne dépasse jamais le salaire horaire.
            </p>
            <div className="grid gap-1">
              <Label htmlFor="ap-note">Note (facultatif)</Label>
              <Textarea
                id="ap-note"
                rows={2}
                value={r.note ?? ''}
                onChange={(e) => setR({ ...r, note: e.target.value || null })}
              />
            </div>
          </div>
        )}
        <Button size="sm" disabled={invalide || enregistrer.isPending} onClick={() => enregistrer.mutate()}>
          Enregistrer
        </Button>
      </CardContent>
    </Card>
  );
}
