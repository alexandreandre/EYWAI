import { brutMensuelPourDuree, formaterEuros } from '@/lib/brutDureeHebdo';

export function BrutPourDureeHint({
  salaire,
  dureeHebdo,
  baseA35h,
}: {
  salaire: unknown;
  dureeHebdo: unknown;
  /** `specificites_paie.salaire_hors_hs_structurelles` du salarié. */
  baseA35h: boolean;
}) {
  const ligne = brutMensuelPourDuree(Number(salaire), Number(dureeHebdo), baseA35h);
  if (!ligne) return null;
  const heures = Number.isInteger(ligne.heures) ? String(ligne.heures) : ligne.heures.toLocaleString('fr-FR');
  return (
    <p className="text-sm text-muted-foreground">
      Brut pour {heures} h :{' '}
      <span className="font-medium text-foreground">{formaterEuros(ligne.brut)} €</span>
      {ligne.baseA35h
        ? '. Le montant saisi est le salaire de base à 35 h. On y ajoute les heures jusqu’à la durée du contrat, majorées de 25 %.'
        : `. Le montant saisi est le brut pour ${heures} h : les heures au-delà de 35 h y sont déjà comprises.`}
    </p>
  );
}
