import {
  messageComparaisonMoisDernier,
  type ComparaisonMoisDernier,
} from '@/features/payroll/utils/comparaisonMoisDernier';

type Props = {
  comparaison: ComparaisonMoisDernier | null | undefined;
};

export function ComparaisonMoisDernier({ comparaison }: Props) {
  const texte = messageComparaisonMoisDernier(comparaison);
  return (
    <div
      data-testid="comparaison-mois-dernier"
      className="rounded-md border bg-muted/30 p-3 text-sm"
    >
      <p className="mb-1 font-medium">Ce qui a changé par rapport au mois dernier</p>
      <p className="text-muted-foreground">{texte}</p>
    </div>
  );
}
