import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';

import {
  lireMoisActivitePartielle,
  poserHeuresActivitePartielle,
  type ResultatActivitePartielle,
} from '@/api/activitePartielle';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ControleIndisponible } from '@/features/payroll/components/ControleIndisponible';
import { moisDePaieRetenu } from '@/features/payroll/utils/moisDePaie';
import { moisDePaieParDefaut } from '@/features/payroll/utils/payrollMonth';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

function eur(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

function nombre(t: string): number | null {
  if (t.trim() === '') return null;
  const v = Number.parseFloat(t.trim().replace(',', '.'));
  return Number.isFinite(v) ? v : Number.NaN;
}

type Saisie = { jours: string; heures: string };

/**
 * Activité partielle du mois (retour d'Elsa du 16/11, LEWIS). Les jours chômés
 * se posent au calendrier (type « Activité partielle ») : le bulletin en tire
 * la retenue et l'indemnité. Cet écran les récapitule ; la saisie d'heures à la
 * main, repliée, reste pour un salarié sans jour au calendrier.
 */
export function ActivitePartielleTab() {
  const companyId = useActiveCompanyId();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const initial = moisDePaieRetenu() ?? moisDePaieParDefaut(new Date());
  const [year, setYear] = useState(initial.year);
  const [month, setMonth] = useState(initial.month);
  const [saisies, setSaisies] = useState<Record<string, Saisie>>({});
  const [resultats, setResultats] = useState<ResultatActivitePartielle[] | null>(null);
  const [aLaMain, setALaMain] = useState(false);

  const query = useQuery({
    queryKey: ['activite-partielle-mois', companyId, year, month],
    queryFn: () => lireMoisActivitePartielle(year, month),
    enabled: Boolean(companyId),
  });
  useEffect(() => {
    setSaisies({});
    setResultats(null);
  }, [year, month]);

  const salaries = query.data?.salaries ?? [];
  const heuresDe = (employeeId: string, heuresParJour: number): number | null => {
    const s = saisies[employeeId];
    if (!s) return null;
    const h = nombre(s.heures);
    if (h !== null) return h;
    const j = nombre(s.jours);
    if (j === null) return null;
    return Number.isNaN(j) ? Number.NaN : Math.round(j * heuresParJour * 100) / 100;
  };
  const aEnvoyer = useMemo(
    () =>
      salaries
        .map((s) => ({ employee_id: s.employee_id, heures: heuresDe(s.employee_id, s.heures_par_jour) }))
        .filter((s): s is { employee_id: string; heures: number } => s.heures !== null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [salaries, saisies],
  );
  // La saisie à la main s'ouvre d'elle-même quand un salarié en a déjà une.
  const montrerMain = aLaMain || salaries.some((s) => s.deja);
  const invalide = aEnvoyer.some((s) => Number.isNaN(s.heures) || s.heures < 0 || s.heures > 250);

  const poser = useMutation({
    mutationFn: () => poserHeuresActivitePartielle(year, month, aEnvoyer),
    onSuccess: (res) => {
      setResultats(res.resultats);
      setSaisies({});
      void queryClient.invalidateQueries({ queryKey: ['activite-partielle-mois', companyId, year, month] });
      const poses = res.resultats.filter((r) => r.statut === 'pose').length;
      const refus = res.resultats.filter((r) => r.statut === 'refuse' || r.statut === 'bulletin_remis').length;
      toast({
        title: `Activité partielle de ${MOIS[month - 1]} : ${poses} salarié${poses > 1 ? 's' : ''}`,
        description:
          (refus ? `${refus} non traité${refus > 1 ? 's' : ''} : voir le détail. ` : '') +
          (res.bulletins_a_recalculer.length
            ? `${res.bulletins_a_recalculer.length} bulletin${res.bulletins_a_recalculer.length > 1 ? 's' : ''} à recalculer.`
            : 'Les lignes iront sur le bulletin au prochain calcul.'),
      });
    },
    onError: (e) =>
      toast({ title: 'Rien n’a été posé', description: getUserErrorMessage(e), variant: 'destructive' }),
  });

  const annees = [initial.year - 1, initial.year, initial.year + 1];
  const refus = query.data?.refus;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground" data-testid="ap-consigne">
        Posez les jours chômés dans le calendrier du salarié : type <strong>Activité partielle</strong>,
        un jour ou plusieurs à la fois. Une demi-journée travaillée : saisissez les heures faites, le reste
        est chômé. Au bulletin, Martine retire les heures chômées et paie l’indemnité (taux du réglage de la
        société). Ce tableau récapitule le mois.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Année</p>
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-[100px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {annees.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Mois</p>
          <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
            <SelectTrigger className="w-[160px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {MOIS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Heures chômées de {MOIS[month - 1]} {year}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {query.isLoading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : query.isError ? (
            <ControleIndisponible
              titre="L'activité partielle de ce mois n'a pas pu être lue"
              description={getUserErrorMessage(query.error)}
              onRetry={() => void query.refetch()}
              isRetrying={query.isFetching}
            />
          ) : refus ? (
            <p className="text-sm text-amber-700" data-testid="ap-refus">
              {refus}{' '}
              <Link to="/company?tab=paie" className="underline">Paramètres de la société</Link>
            </p>
          ) : (
            <>
              <div className="w-full overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Salarié</TableHead>
                      <TableHead className="text-right">Salaire horaire</TableHead>
                      <TableHead>Au calendrier</TableHead>
                      {montrerMain && (
                        <>
                          <TableHead>Jours chômés</TableHead>
                          <TableHead>ou heures</TableHead>
                          <TableHead>Saisi à la main</TableHead>
                        </>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {salaries.map((s) => {
                      const saisie = saisies[s.employee_id] ?? { jours: '', heures: '' };
                      const maj = (champ: keyof Saisie, v: string) =>
                        setSaisies((prev) => ({ ...prev, [s.employee_id]: { ...saisie, [champ]: v } }));
                      return (
                        <TableRow key={s.employee_id}>
                          <TableCell className="font-medium">{s.nom}</TableCell>
                          <TableCell className="text-right tabular-nums">
                            {s.taux_horaire != null ? eur(s.taux_horaire) : 'salaire absent'}
                            {s.forfait_jours && (
                              <span className="block text-xs text-muted-foreground">forfait jours, 7 h par jour</span>
                            )}
                          </TableCell>
                          <TableCell className="text-sm" data-testid="ap-calendrier">
                            {s.calendrier ? (
                              <span>
                                {s.calendrier.jours.length} j · {s.calendrier.heures.toLocaleString('fr-FR')} h
                                <span className="block text-xs text-muted-foreground">
                                  retenue {eur(s.calendrier.retenue)} · indemnité {eur(s.calendrier.indemnite)}
                                </span>
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                            {s.calendrier && s.deja && (
                              <span className="block text-xs text-amber-700">la saisie à la main n’est plus prise en compte</span>
                            )}
                          </TableCell>
                          {montrerMain && (
                            <>
                          <TableCell>
                            <Input
                              aria-label={`Jours chômés de ${s.nom}`}
                              inputMode="decimal"
                              className="h-8 w-20 text-right"
                              placeholder="0"
                              value={saisie.jours}
                              disabled={Boolean(s.calendrier)}
                              onChange={(e) => maj('jours', e.target.value)}
                              title={`${s.heures_par_jour.toLocaleString('fr-FR')} h par jour`}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              aria-label={`Heures chômées de ${s.nom}`}
                              inputMode="decimal"
                              className="h-8 w-20 text-right"
                              placeholder={
                                saisie.jours && nombre(saisie.jours) != null && !Number.isNaN(nombre(saisie.jours)!)
                                  ? String(Math.round(nombre(saisie.jours)! * s.heures_par_jour * 100) / 100).replace('.', ',')
                                  : 'h'
                              }
                              value={saisie.heures}
                              disabled={Boolean(s.calendrier)}
                              onChange={(e) => maj('heures', e.target.value)}
                            />
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {s.deja
                              ? `${s.deja.heures != null ? `${s.deja.heures.toLocaleString('fr-FR')} h · ` : ''}retenue ${eur(s.deja.retenue)} · indemnité ${eur(s.deja.indemnite)}`
                              : '—'}
                          </TableCell>
                            </>
                          )}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
              {invalide && (
                <p className="text-xs text-destructive">Une saisie n’est pas un nombre d’heures ou de jours valable.</p>
              )}
              {!montrerMain ? (
                <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setALaMain(true)} data-testid="ap-a-la-main">
                  Saisir des heures à la main (salarié sans jour au calendrier)
                </Button>
              ) : (
              <>
              <p className="text-xs text-muted-foreground">
                Un salarié qui a des jours au calendrier n’a rien à saisir ici : le calendrier fait foi.
              </p>
              <Button
                data-testid="ap-poser"
                disabled={aEnvoyer.length === 0 || invalide || poser.isPending}
                onClick={() => poser.mutate()}
              >
                {poser.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Calculer et poser ({aEnvoyer.length})
              </Button>
              </>
              )}
            </>
          )}
          {resultats && resultats.length > 0 && (
            <div className="space-y-1 rounded-md border p-3 text-sm" data-testid="ap-resultats">
              {resultats.map((r) => (
                <p key={r.employee_id} className={r.statut === 'refuse' || r.statut === 'bulletin_remis' ? 'text-destructive' : ''}>
                  <span className="font-medium">{r.nom ?? r.employee_id}</span> :{' '}
                  {r.statut === 'pose'
                    ? `${r.heures?.toLocaleString('fr-FR')} h chômées, retenue ${eur(r.retenue)}, indemnité ${eur(r.indemnite)} (${eur(r.indemnite_horaire)} de l’heure, ${r.regle})${r.message ? `. ${r.message}` : ''}`
                    : r.statut === 'retire'
                      ? 'lignes retirées'
                      : r.statut === 'rien'
                        ? 'rien à retirer'
                        : r.message}
                </p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
