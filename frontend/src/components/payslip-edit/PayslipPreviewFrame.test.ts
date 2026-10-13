import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import PayslipPreviewFrame from './PayslipPreviewFrame';
import { cadreDApercu } from './apercuBulletin';

/**
 * Le cadre d'aperçu ne doit jamais changer de contenu sur place : chaque
 * changement du `srcdoc` d'un cadre déjà chargé ajoute une page à l'historique
 * du navigateur, et le premier « Retour » du bulletin ne faisait alors que
 * vider le cadre (rejeu C2 du 12/10 : deux clics pour revenir à la liste).
 */
describe("l'aperçu du bulletin n'ajoute rien à l'historique", () => {
  it("pas de cadre tant que l'aperçu n'est pas arrivé", () => {
    const html = renderToStaticMarkup(createElement(PayslipPreviewFrame, { payslipId: 'b-1' }));
    expect(html).not.toContain('<iframe');
    expect(html).toContain('Aperçu en cours de chargement');
  });

  it('chaque aperçu naît dans un cadre neuf (clé propre), jamais rechargé sur place', () => {
    expect(cadreDApercu('', 0)).toBeNull();
    const premier = cadreDApercu('<p>bulletin</p>', 1);
    const second = cadreDApercu('<p>bulletin</p>', 2);
    expect(premier?.srcDoc).toBe('<p>bulletin</p>');
    expect(premier?.cle).not.toBe(second?.cle);
  });
});
