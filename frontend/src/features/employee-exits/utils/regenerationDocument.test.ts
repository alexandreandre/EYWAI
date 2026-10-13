import { describe, expect, it } from 'vitest';

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { MESSAGE_AJOUTS_PERDUS, regenerationEffaceDesAjouts } from './documentsSortie';

/**
 * Régénérer un document de sortie remplace la version générée et jamais envoyée
 * au collaborateur : les ajouts faits avec « Modifier le document » (lignes du
 * certificat, données corrigées) disparaissaient sans prévenir (relevé H, 12/10).
 */
const modifie = {
  document_type: 'certificat_travail',
  document_category: 'generated',
  published_to_employee: false,
  generation_data: { additional_info: [{ label: 'Poste', value: 'Cariste' }], _edit_history: [{ version: 2 }] },
};

describe('régénérer un document de sortie qui porte des ajouts', () => {
  it('avertit quand la version remplacée a été modifiée à la main', () => {
    expect(regenerationEffaceDesAjouts([modifie], 'certificat_travail')).toBe(true);
    expect(MESSAGE_AJOUTS_PERDUS).toBe('Vos ajouts au document seront perdus');
  });

  it('ne dit rien pour un document jamais modifié, d’un autre type, téléversé ou déjà envoyé (gardé)', () => {
    expect(regenerationEffaceDesAjouts([{ ...modifie, generation_data: null }], 'certificat_travail')).toBe(false);
    expect(
      regenerationEffaceDesAjouts([{ ...modifie, generation_data: { _edit_history: [] } }], 'certificat_travail')
    ).toBe(false);
    expect(regenerationEffaceDesAjouts([modifie], 'solde_tout_compte')).toBe(false);
    expect(regenerationEffaceDesAjouts([{ ...modifie, document_category: 'uploaded' }], 'certificat_travail')).toBe(
      false
    );
    expect(regenerationEffaceDesAjouts([{ ...modifie, published_to_employee: true }], 'certificat_travail')).toBe(
      false
    );
    expect(regenerationEffaceDesAjouts([], 'certificat_travail')).toBe(false);
  });

  it('l’onglet Documents demande confirmation avant de régénérer', () => {
    const t = readFileSync(path.resolve(__dirname, '../../../components/exits/ExitDetailsPanel.tsx'), 'utf8').replace(
      /\s+/g,
      ' '
    );
    expect(t).toContain('regenerationEffaceDesAjouts(documents, type)');
    expect(t).toContain('{MESSAGE_AJOUTS_PERDUS}');
    expect(t).toContain('Régénérer quand même');
    expect(t).toContain('<AlertDialogCancel>Annuler</AlertDialogCancel>');
  });
});
