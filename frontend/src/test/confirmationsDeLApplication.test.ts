import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { reponseUnique } from '@/hooks/confirmation';

/**
 * Tournage H.2 (scène 17) et H.6 (scène 7), 20/10/2026 : supprimer un départ ou
 * corriger le dernier jour travaillé passait par la fenêtre native du navigateur
 * (`window.confirm`), absente de l'image, et la notification de succès ne se
 * voyait pas. Toute confirmation passe par une fenêtre de l'application.
 */
const SRC = path.resolve(__dirname, '..');

function fichiers(dossier: string): string[] {
  return readdirSync(dossier).flatMap((nom) => {
    const chemin = path.join(dossier, nom);
    if (statSync(chemin).isDirectory()) return fichiers(chemin);
    return /\.(ts|tsx)$/.test(nom) && !/\.test\.tsx?$/.test(nom) ? [chemin] : [];
  });
}

describe('aucune fenêtre native de confirmation', () => {
  it('ni window.confirm ni confirm( dans le front', () => {
    const fautifs = fichiers(SRC).filter((f) =>
      /window\.confirm\s*\(|(^|[^\w.])confirm\s*\(/m.test(readFileSync(f, 'utf8'))
    );
    expect(fautifs.map((f) => path.relative(SRC, f))).toEqual([]);
  });

  it('les notifications « sonner » ont leur afficheur monté dans l’application', () => {
    const app = readFileSync(path.join(SRC, 'App.tsx'), 'utf8');
    expect(app).toMatch(/import \{ Toaster as Notifications \} from '@\/components\/ui\/sonner'/);
    expect(app).toContain('<Notifications');
  });
});

describe('la réponse d’une fenêtre de confirmation', () => {
  it('rend la première réponse, et une seule', async () => {
    const { promesse, repondre } = reponseUnique();
    repondre(true);
    repondre(false);
    expect(await promesse).toBe(true);
  });

  it('fermer la fenêtre vaut « non »', async () => {
    const { promesse, repondre } = reponseUnique();
    repondre(false);
    expect(await promesse).toBe(false);
  });
});
