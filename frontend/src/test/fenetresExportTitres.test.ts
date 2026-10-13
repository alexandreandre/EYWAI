import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '..');
const lire = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8').replace(/\s+/g, ' ');

/**
 * Rejeu final I (13/10) : la fenêtre du FEC s'intitulait « fec ». Le titre de la
 * fenêtre commune des exports vient de `exportTypeLabels`, sinon de l'identifiant
 * technique : chaque carte qui ouvre cette fenêtre y a son nom, celui de la carte.
 */
describe('Exports : chaque fenêtre porte le nom de sa carte, jamais un identifiant technique', () => {
  const fenetre = lire('components/exports/ExportCommonModel.tsx');

  it.each([
    ['fec', 'FEC'],
    ['saisies', 'Saisies sur salaire'],
    ['prets_employeur', 'Prêts employeur'],
    ['"attestations-annexes"', 'Attestations & annexes'],
    ['"provision-cp"', 'Provision congés payés'],
    ['"paiement-organismes"', 'Paiement organismes'],
  ])('%s s’intitule « %s »', (identifiant, titre) => {
    const libelles = fenetre.slice(fenetre.indexOf('const exportTypeLabels'));
    expect(libelles.slice(0, libelles.indexOf('};'))).toContain(`${identifiant}: "${titre}"`);
  });
});
