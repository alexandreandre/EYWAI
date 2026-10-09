import { RotateCcw } from 'lucide-react';
import type { ReimportInfo } from '@/api/calendar';
import {
  cleJour,
  libelleBilan,
  libelleCorrection,
  libelleLotPrecedent,
  libelleValeur,
  type BilanReimport,
} from './reimport';

interface ReimportBannerProps {
  reimport: ReimportInfo;
  bilan: BilanReimport;
  libelleSalarie: (employeeId: string) => string;
}

/**
 * En tête de la revue d'un fichier relu : le lot précédent, ce que
 * l'enregistrement écrira, et chaque jour corrigé à la main depuis l'import,
 * que l'enregistrement ne réécrit pas.
 */
export function ReimportBanner({ reimport, bilan, libelleSalarie }: ReimportBannerProps) {
  const corrections = reimport.corrections_a_la_main;
  return (
    <div
      className="shrink-0 rounded-md border border-sky-300 bg-sky-50 px-3 py-2 text-xs text-sky-950"
      data-testid="bandeau-reimport"
    >
      <p className="flex items-center gap-1.5 text-sm font-medium">
        <RotateCcw className="h-4 w-4 shrink-0" />
        Refaire l&apos;import : {libelleBilan(bilan)}.
      </p>
      <ul className="mt-1 space-y-0.5">
        {reimport.lots_precedents.map((lot) => (
          <li key={`${lot.batch_id}-${lot.fichier ?? ''}`}>
            « {lot.fichier ?? lot.filename ?? 'fichier'} » — {libelleLotPrecedent(lot)}.
          </li>
        ))}
      </ul>
      {(reimport.associations_reprises?.length ?? 0) > 0 && (
        <p className="mt-1">
          Association reprise de l&apos;import précédent :{' '}
          {reimport.associations_reprises?.map((n) => `« ${n} »`).join(', ')}.
        </p>
      )}
      {corrections.length === 0 ? (
        <p className="mt-1">
          Aucun jour n&apos;a été corrigé à la main depuis cet import : le fichier relu
          remplace ce qu&apos;il avait écrit.
        </p>
      ) : (
        <>
          <p className="mt-1 font-medium text-amber-900">
            {corrections.length > 1
              ? `${corrections.length} jours corrigés à la main depuis l’import ne seront pas réécrits`
              : '1 jour corrigé à la main depuis l’import ne sera pas réécrit'}{' '}
            : la valeur du calendrier reste. Pour prendre celle du fichier, saisissez-la
            ensuite dans le calendrier.
          </p>
          <ul className="mt-1 max-h-40 space-y-0.5 overflow-y-auto pr-1">
            {corrections.map((c) => (
              <li key={cleJour(c)} className="flex flex-wrap gap-x-2">
                <span className="font-medium">{libelleSalarie(c.employee_id)}</span>
                <span className="tabular-nums">
                  {String(c.jour).padStart(2, '0')}/{String(c.mois).padStart(2, '0')}
                </span>
                <span className="text-amber-900">{libelleCorrection(c)}</span>
                <span className="text-muted-foreground">
                  · le fichier lit {libelleValeur(c.fichier)} · gardé : {libelleValeur(c.calendrier)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
