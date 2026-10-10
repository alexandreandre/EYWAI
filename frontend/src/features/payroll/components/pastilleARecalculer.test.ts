import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest tourne sans rendu : on garde l'écran par sa source. La pastille
// « À recalculer » explique son motif dans l'info-bulle de l'application, pas
// dans le `title` natif du navigateur (lent, sans mise en forme, absent au toucher).
describe('pastille « À recalculer » de la liste de paie', () => {
  const source = readFileSync(join(__dirname, 'PayrollPayslipRow.tsx'), 'utf8');
  const debut = source.indexOf('data-testid="badge-a-recalculer"');
  const bloc = source.slice(source.lastIndexOf('<Tooltip', debut) >= 0 ? source.lastIndexOf('<', debut - 200) : debut - 200, debut + 400);

  it('utilise l’info-bulle de l’application', () => {
    expect(debut).toBeGreaterThan(-1);
    expect(source.slice(Math.max(0, debut - 600), debut)).toContain('<TooltipTrigger');
  });

  it('ne passe pas par un title natif', () => {
    const autour = source.slice(debut, debut + 300).split('</Badge>')[0];
    expect(autour).not.toContain('title=');
    expect(bloc).toBeTruthy();
  });
});
