import { brutMensuelPourDuree, formaterEuros } from '@/lib/brutDureeHebdo';

export function BrutPourDureeHint({
  salaire,
  dureeHebdo,
}: {
  salaire: unknown;
  dureeHebdo: unknown;
}) {
  const ligne = brutMensuelPourDuree(Number(salaire), Number(dureeHebdo));
  if (!ligne) return null;
  const heures = Number.isInteger(ligne.heures) ? String(ligne.heures) : ligne.heures.toLocaleString('fr-FR');
  return (
    <p className="text-sm text-muted-foreground">
      Brut pour {heures} h :{' '}
      <span className="font-medium text-foreground">{formaterEuros(ligne.brut)} €</span>
      . Le montant saisi est le salaire de base à 35 h. On y ajoute les heures
      jusqu’à la durée du contrat, majorées de 25 %.
    </p>
  );
}
