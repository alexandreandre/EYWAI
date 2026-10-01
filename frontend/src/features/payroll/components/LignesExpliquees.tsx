import type { PayslipBulletinData } from '@/api/payslips';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  afficherAsterisque,
  lignesAvecExplication,
} from '@/features/payroll/utils/explicationsLignes';

type Props = {
  payslipData: PayslipBulletinData | null | undefined;
};

export function LignesExpliquees({ payslipData }: Props) {
  const lignes = lignesAvecExplication(payslipData ?? null);
  if (lignes.length === 0) return null;

  return (
    <div
      data-testid="lignes-expliquees"
      className="rounded-md border bg-muted/30 p-3 text-sm"
    >
      <p className="mb-2 font-medium">D’où viennent ces lignes</p>
      <ul className="space-y-1">
        {lignes.map((ligne) => (
          <li
            key={`${ligne.libelle}|${ligne.explication}`}
            className="flex items-start gap-1"
          >
            <span>{ligne.libelle}</span>
            {afficherAsterisque(ligne) ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="shrink-0 font-semibold text-sky-700"
                    aria-label={ligne.explication}
                  >
                    *
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  {ligne.explication}
                </TooltipContent>
              </Tooltip>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
