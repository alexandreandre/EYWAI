import { AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const del = vi.fn();
const get = vi.fn();
const post = vi.fn();

vi.mock('./apiClient', () => ({
  default: {
    delete: (...a: unknown[]) => del(...a),
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
  },
}));

import {
  deletePayslip,
  editPayslip,
  estDejaSupprime,
  generatePayslip,
  getPayslipDetails,
  restorePayslipVersion,
  validatePayslip,
} from './payslips';

describe('estDejaSupprime', () => {
  it('lit l’en-tête d’une réponse axios', () => {
    expect(estDejaSupprime(new AxiosHeaders({ 'X-Deja-Supprime': 'true' }))).toBe(true);
  });

  it('lit aussi des en-têtes en objet simple, quelle que soit la casse', () => {
    expect(estDejaSupprime({ 'x-deja-supprime': 'true' })).toBe(true);
    expect(estDejaSupprime({ 'X-Deja-Supprime': 'true' })).toBe(true);
  });

  it('une vraie suppression n’a pas l’en-tête', () => {
    expect(estDejaSupprime(new AxiosHeaders({ 'content-length': '0' }))).toBe(false);
    expect(estDejaSupprime({})).toBe(false);
    expect(estDejaSupprime(undefined)).toBe(false);
  });

  it('seul « true » vaut « déjà supprimé »', () => {
    expect(estDejaSupprime({ 'x-deja-supprime': 'false' })).toBe(false);
    expect(estDejaSupprime({ 'x-deja-supprime': '' })).toBe(false);
  });
});

describe('deletePayslip', () => {
  beforeEach(() => {
    del.mockReset();
  });

  it('supprime dans la société affichée par l’écran, pas celle d’un autre onglet', async () => {
    del.mockResolvedValue({ status: 204, headers: new AxiosHeaders() });

    await deletePayslip('ps-1', 'co-ecran');

    expect(del).toHaveBeenCalledWith('/api/payslips/ps-1', {
      headers: { 'X-Active-Company': 'co-ecran' },
    });
  });

  it('sans société connue, laisse l’intercepteur choisir', async () => {
    del.mockResolvedValue({ status: 204, headers: new AxiosHeaders() });

    await deletePayslip('ps-1', null);

    expect(del).toHaveBeenCalledWith('/api/payslips/ps-1', undefined);
  });

  it('dit si le bulletin avait déjà été supprimé', async () => {
    del.mockResolvedValue({ status: 204, headers: new AxiosHeaders({ 'X-Deja-Supprime': 'true' }) });
    await expect(deletePayslip('ps-1', 'co-ecran')).resolves.toEqual({ dejaSupprime: true });

    del.mockResolvedValue({ status: 204, headers: new AxiosHeaders() });
    await expect(deletePayslip('ps-1', 'co-ecran')).resolves.toEqual({ dejaSupprime: false });
  });

  it('un refus de suppression reste une erreur', async () => {
    const refus = Object.assign(new Error('Request failed with status code 409'), {
      response: { status: 409, data: { detail: { code: 'bulletin_valide' } } },
    });
    del.mockRejectedValue(refus);

    await expect(deletePayslip('ps-1', 'co-ecran')).rejects.toBe(refus);
  });
});

describe('écran de correction : la société du bulletin, pas celle d’un autre onglet', () => {
  const SOCIETE = { headers: { 'X-Active-Company': 'co-bulletin' } };

  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: { id: 'ps-1' } });
    post.mockReset().mockResolvedValue({ data: {} });
  });

  it('relire le bulletin', async () => {
    await getPayslipDetails('ps-1', 'co-bulletin');
    expect(get).toHaveBeenCalledWith('/api/payslips/ps-1', SOCIETE);
  });

  it('enregistrer les corrections', async () => {
    const requete = { pdf_notes: 'note' } as Parameters<typeof editPayslip>[1];
    await editPayslip('ps-1', requete, 'co-bulletin');
    expect(post).toHaveBeenCalledWith('/api/payslips/ps-1/edit', requete, SOCIETE);
  });

  it('valider', async () => {
    await validatePayslip('ps-1', 'co-bulletin');
    expect(post).toHaveBeenCalledWith('/api/payslips/ps-1/validate', undefined, SOCIETE);
  });

  it('restaurer une version', async () => {
    await restorePayslipVersion('ps-1', 3, 'co-bulletin');
    expect(post).toHaveBeenCalledWith('/api/payslips/ps-1/restore', { version: 3 }, SOCIETE);
  });

  it('régénérer', async () => {
    const demande = { employee_id: 'emp-1', year: 2026, month: 9 };
    await generatePayslip(demande, undefined, 'co-bulletin');
    expect(post).toHaveBeenCalledWith('/api/actions/generate-payslip', demande, {
      signal: undefined,
      ...SOCIETE,
    });
  });

  it('sans société connue, les appels restent ceux d’avant', async () => {
    await getPayslipDetails('ps-1');
    expect(get).toHaveBeenCalledWith('/api/payslips/ps-1', undefined);

    const controleur = new AbortController();
    await generatePayslip({ employee_id: 'emp-1', year: 2026, month: 9 }, controleur.signal);
    expect(post).toHaveBeenCalledWith(
      '/api/actions/generate-payslip',
      { employee_id: 'emp-1', year: 2026, month: 9 },
      { signal: controleur.signal }
    );
  });
});
