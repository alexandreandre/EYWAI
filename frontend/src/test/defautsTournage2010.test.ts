import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/** Gardes des textes d'écran relevés au tournage des vidéos (20/10/2026), par lecture du source. */
const SRC = path.resolve(__dirname, '..');
const lire = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8').replace(/\s+/g, ' ');

describe('fiche, onglet « Soldes de congés »', () => {
  const texte = lire('components/employee-detail/EmployeeDetailLeaveBalancesTab.tsx');

  it('la phrase d’aide cite tous les compteurs que le crayon corrige, repos compensateur compris', () => {
    expect(texte).toMatch(/Le crayon d’une ligne corrige son solde : congés payés \(N-1 et N à la fin d’un mois\), RTT, JTC, repos compensateur\./);
  });
});

describe('« Mise à jour complète » grisé (tournage B.2)', () => {
  // Un bouton désactivé ne reçoit pas le survol : son `title` ne s'affichait
  // jamais. Le bouton est enveloppé, et l'infobulle tient à l'enveloppe.
  it.each(['components/rates/RatesPageToolbar.tsx', 'pages/rh/Rates.tsx'])('%s : l’infobulle tient à une enveloppe', (fichier) => {
    const texte = lire(fichier);
    expect(texte).not.toMatch(/title=\{(updatesLocked|RATES_UPDATES_LOCKED) \? RATES_UPDATES_LOCK_REASON/);
    expect(texte).toMatch(/<TooltipTrigger asChild> <span tabIndex=\{0\}[^>]*>/);
    expect(texte).toMatch(/<TooltipContent[^>]*>\{RATES_UPDATES_LOCK_REASON\}<\/TooltipContent>/);
  });
});
