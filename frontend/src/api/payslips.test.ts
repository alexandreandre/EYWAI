import { AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const del = vi.fn();

vi.mock('./apiClient', () => ({
  default: {
    delete: (...a: unknown[]) => del(...a),
  },
}));

import { deletePayslip, estDejaSupprime } from './payslips';

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

  it('un refus reste une erreur', async () => {
    const refus = Object.assign(new Error('Request failed with status code 409'), {
      response: { status: 409, data: { detail: { code: 'bulletin_valide' } } },
    });
    del.mockRejectedValue(refus);

    await expect(deletePayslip('ps-1', 'co-ecran')).rejects.toBe(refus);
  });
});
