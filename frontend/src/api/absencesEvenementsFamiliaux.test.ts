import { describe, expect, it, vi, beforeEach } from 'vitest';

const get = vi.fn();

vi.mock('./apiClient', () => ({
  default: { get: (...a: unknown[]) => get(...a) },
}));

import { getEvenementsFamiliaux } from './absences';

// Défaut vu le 03/11 : la fenêtre « Nouveau congé » de la RH lisait la liste
// du compte connecté (/me), vide pour une RH sans fiche de salarié.
describe('événements familiaux', () => {
  beforeEach(() => get.mockReset());

  it('lit la liste du salarié choisi par la RH', () => {
    getEvenementsFamiliaux('emp-1');
    expect(get).toHaveBeenCalledWith('/api/absences/employees/emp-1/evenements-familiaux');
  });

  it('lit sa propre liste sans salarié choisi', () => {
    getEvenementsFamiliaux();
    expect(get).toHaveBeenCalledWith('/api/absences/employees/me/evenements-familiaux');
  });
});
