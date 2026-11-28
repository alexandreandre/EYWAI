import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { FileSpreadsheet, Loader2 } from 'lucide-react';

import { getRecapConges, telechargerRecapConges, type PeriodeRecap } from '@/api/absences';
import { residencePermitsExportErrorMessage as messageDuServeur } from '@/api/residencePermits';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCompany } from '@/contexts/CompanyContext';
import { useMoisDePaie } from '@/features/payroll/hooks/useMoisDePaie';
import { companyQueryKey } from '@/lib/queryKeys';
import {
  colonnesDuTableau,
  etatDuRecap,
  filtrerSalaries,
  formatJours,
  libellePeriode,
  messagePeriodeRecap,
  periodeDuMoisDePaie,
} from '@/features/absences/lib/recapConges';

const messageDeLErreur = (e: unknown): string | null => {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : null;
};

/**
 * Récapitulatif des congés et absences de la société (lot L21, 28/11/2026) :
 * une ligne par salarié sur la période, sans ouvrir chaque fiche. Les jours
 * viennent du calendrier de paie, JTC et repos seniors des demandes validées,
 * les soldes CP de l'aperçu des soldes (onglet Paie de l'entreprise).
 */
export function RecapCongesSection({ recherche }: { recherche: string }) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;
  const { mois } = useMoisDePaie();
  const periodeDuMois = useMemo(
    () => periodeDuMoisDePaie({ year: mois.year, month: mois.month }),
    [mois.year, mois.month],
  );
  const [periode, setPeriode] = useState<PeriodeRecap>(periodeDuMois);
  useEffect(() => setPeriode(periodeDuMois), [periodeDuMois]);

  const refus = messagePeriodeRecap(periode);
  const query = useQuery({
    queryKey: companyQueryKey(companyId, 'recap-conges', periode.debut, periode.fin),
    queryFn: () => getRecapConges(periode),
    enabled: Boolean(companyId) && !refus,
    staleTime: 30_000,
  });
  const etat = etatDuRecap({
    periodeRefusee: Boolean(refus),
    chargement: query.isLoading,
    erreur: query.isError,
    recap: query.data,
  });

  const [exportEnCours, setExportEnCours] = useState(false);
  const [erreurExport, setErreurExport] = useState<string | null>(null);
  const exporter = async () => {
    if (refus) return;
    setExportEnCours(true);
    setErreurExport(null);
    try {
      await telechargerRecapConges(periode);
    } catch (e) {
      setErreurExport(
        await messageDuServeur(e, 'Le fichier n’a pas pu être préparé. Réessayez dans un instant.'),
      );
    } finally {
      setExportEnCours(false);
    }
  };

  const recap = query.data;
  const colonnes = recap ? colonnesDuTableau(recap) : { affichees: [], masquees: [] };
  const salaries = recap ? filtrerSalaries(recap.salaries, recherche) : [];

  return (
    <Card data-testid="recap-conges">
      <CardHeader>
        <CardTitle>Récapitulatif de la société</CardTitle>
        <CardDescription>
          Les congés et absences de chaque salarié sur la période, et ses soldes de congés payés.
          Par défaut, le mois de paie.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="recap-debut">Du</Label>
            <Input
              id="recap-debut"
              type="date"
              value={periode.debut}
              onChange={(e) => setPeriode((p) => ({ ...p, debut: e.target.value }))}
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="recap-fin">Au</Label>
            <Input
              id="recap-fin"
              type="date"
              value={periode.fin}
              onChange={(e) => setPeriode((p) => ({ ...p, fin: e.target.value }))}
              className="w-40"
            />
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={() => setPeriode(periodeDuMois)}>
            Mois de paie
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => void exporter()}
            disabled={Boolean(refus) || exportEnCours}
          >
            {exportEnCours ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden />
            )}
            Exporter (Excel)
          </Button>
        </div>
        {erreurExport && (
          <p className="text-sm text-destructive" role="alert">
            {erreurExport}
          </p>
        )}

        {etat === 'periode' && (
          <p className="text-sm text-destructive" role="alert">
            {refus}
          </p>
        )}
        {etat === 'chargement' && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Chargement du récapitulatif…
          </p>
        )}
        {etat === 'erreur' && (
          <div className="flex flex-wrap items-center gap-3 text-sm text-destructive" role="alert">
            <span>
              Le récapitulatif n’a pas pu être chargé
              {messageDeLErreur(query.error) ? ` : ${messageDeLErreur(query.error)}` : '.'}
            </span>
            <Button type="button" variant="outline" size="sm" onClick={() => void query.refetch()}>
              Réessayer
            </Button>
          </div>
        )}
        {etat === 'vide' && recap && (
          <p className="rounded-md border bg-muted/30 px-3 py-2 text-sm" data-testid="recap-aucun-conge">
            Aucun congé sur la période {libellePeriode(recap)} : ni congé, ni absence, ni arrêt au
            calendrier. Les soldes de congés payés restent affichés.
          </p>
        )}

        {recap && (etat === 'vide' || etat === 'pret') && (
          <>
            <div className="w-full overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Salarié</TableHead>
                    {colonnes.affichees.map((c) => (
                      <TableHead key={c.cle} className="text-right" title={c.source}>
                        {c.libelle} (j)
                      </TableHead>
                    ))}
                    <TableHead className="text-right">Total (j)</TableHead>
                    <TableHead className="text-right" title={recap.source_soldes}>
                      Solde CP N-1
                    </TableHead>
                    <TableHead className="text-right" title={recap.source_soldes}>
                      Solde CP N
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {salaries.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={colonnes.affichees.length + 4} className="text-muted-foreground">
                        {recherche.trim()
                          ? 'Aucun salarié ne correspond à la recherche.'
                          : 'Aucun salarié à afficher.'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    salaries.map((s) => (
                      <TableRow key={s.employee_id}>
                        <TableCell className="font-medium">
                          <Link
                            to={`/employees/${s.employee_id}`}
                            className="hover:underline underline-offset-4"
                          >
                            {s.prenom} {s.nom}
                          </Link>
                          {s.matricule && (
                            <span className="ml-2 text-xs text-muted-foreground">{s.matricule}</span>
                          )}
                        </TableCell>
                        {colonnes.affichees.map((c) => {
                          const v = s.jours[c.cle] ?? 0;
                          return (
                            <TableCell
                              key={c.cle}
                              className={`text-right tabular-nums ${v > 0 ? '' : 'text-muted-foreground'}`}
                            >
                              {formatJours(v)}
                            </TableCell>
                          );
                        })}
                        <TableCell className="text-right font-medium tabular-nums">
                          {formatJours(s.total_jours)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{formatJours(s.solde_cp_n1)}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatJours(s.solde_cp_n)}</TableCell>
                      </TableRow>
                    ))
                  )}
                  {salaries.length > 0 && !recherche.trim() && (
                    <TableRow className="bg-muted/40 font-medium">
                      <TableCell>Total</TableCell>
                      {colonnes.affichees.map((c) => (
                        <TableCell key={c.cle} className="text-right tabular-nums">
                          {formatJours(recap.totaux[c.cle] ?? 0)}
                        </TableCell>
                      ))}
                      <TableCell className="text-right tabular-nums">
                        {formatJours(Object.values(recap.totaux).reduce((a, b) => a + b, 0))}
                      </TableCell>
                      <TableCell />
                      <TableCell />
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <div className="space-y-1 text-xs text-muted-foreground" data-testid="recap-sources">
              <p className="font-medium text-foreground">D’où viennent les chiffres</p>
              <ul className="list-disc space-y-0.5 pl-5">
                {colonnes.affichees.map((c) => (
                  <li key={c.cle}>
                    {c.libelle} : {c.source}.
                  </li>
                ))}
                <li>
                  Soldes CP au {recap.date_des_soldes.split('-').reverse().join('/')} :{' '}
                  {recap.source_soldes}. « non calculé » : salarié sorti ou sans date d’entrée.
                </li>
                <li>{recap.note_arrets}</li>
                {colonnes.masquees.length > 0 && (
                  <li>
                    Aucun jour sur la période, colonnes masquées ici et gardées dans l’Excel :{' '}
                    {colonnes.masquees.map((c) => c.libelle).join(', ')}.
                  </li>
                )}
              </ul>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
