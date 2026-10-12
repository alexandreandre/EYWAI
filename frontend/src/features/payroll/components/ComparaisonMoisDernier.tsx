import {
  messageComparaisonMoisDernier,
  titreComparaisonMoisDernier,
  type ComparaisonMoisDernier,
} from '@/features/payroll/utils/comparaisonMoisDernier';

type Props = {
  comparaison: ComparaisonMoisDernier | null | undefined;
  /** Mois du bulletin affiché : la référence est le mois civil qui le précède. */
  annee?: number;
  mois?: number;
};

export function ComparaisonMoisDernier({ comparaison, annee, mois }: Props) {
  const texte = messageComparaisonMoisDernier(comparaison);
  return (
    <div
      data-testid="comparaison-mois-dernier"
      className="rounded-md border bg-muted/30 p-3 text-sm"
    >
      <p className="mb-1 font-medium">{titreComparaisonMoisDernier(annee, mois)}</p>
      <p className="text-muted-foreground">{texte}</p>
    </div>
  );
}
