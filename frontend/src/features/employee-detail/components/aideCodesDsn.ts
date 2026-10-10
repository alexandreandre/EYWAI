export type ChampCodeDsn =
  | 'specificites_paie.dsn_reprise.motif_recours'
  | 'specificites_paie.dsn_reprise.niveau_diplome_prepare';

/** Phrase d'aide sous une liste à code DSN : dit ce que le choix change vraiment. */
export function aideCodeDsn(champ: ChampCodeDsn): string {
  if (champ === 'specificites_paie.dsn_reprise.motif_recours') {
    return 'Déclaré en DSN. Les motifs saisonnier, vendanges, usage et les cas des articles L1242-3 (codes 09 et 10) suppriment la prime de précarité sur le bulletin.';
  }
  return 'Déclaré en DSN, sans effet sur le bulletin.';
}
