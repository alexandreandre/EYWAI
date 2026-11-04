import type { MutationOptions } from '@tanstack/react-query';
import { AxiosError, AxiosHeaders, CanceledError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const toastMock = vi.fn();
vi.mock('@/hooks/use-toast', () => ({ toast: (...args: unknown[]) => toastMock(...args) }));

import { createAppQueryClient } from './queryClient';

function erreurApi(status: number, detail: unknown) {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError('Request failed with status code ' + status, 'ERR_BAD_RESPONSE', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: { detail },
  });
}

async function executer(options: MutationOptions<unknown, unknown, void>) {
  const client = createAppQueryClient();
  const mutation = client.getMutationCache().build(client, options);
  await mutation.execute(undefined).catch(() => undefined);
}

describe('filet global des mutations', () => {
  beforeEach(() => {
    toastMock.mockReset();
  });

  it('une mutation sans gestion d’erreur qui échoue le dit, en clair', async () => {
    await executer({ mutationFn: () => Promise.reject(erreurApi(400, 'Le mois est clôturé.')) });

    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(toastMock).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: 'destructive',
        title: 'L’action n’a pas abouti',
        description: 'Le mois est clôturé.',
      }),
    );
  });

  it('ne montre jamais le message technique d’axios', async () => {
    await executer({ mutationFn: () => Promise.reject(erreurApi(500, 'Traceback (most recent call last)')) });

    const [{ description }] = toastMock.mock.calls[0] as [{ description: string }];
    expect(description).not.toMatch(/request failed|traceback/i);
    expect(description).toMatch(/Réessayez/);
  });

  it('se tait quand l’écran a son propre onError (pas de doublon)', async () => {
    const local = vi.fn();
    await executer({ mutationFn: () => Promise.reject(erreurApi(400, 'x')), onError: local });

    expect(local).toHaveBeenCalledTimes(1);
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('se tait quand l’écran affiche lui-même l’erreur (meta.erreurAffichee)', async () => {
    await executer({ mutationFn: () => Promise.reject(erreurApi(400, 'x')), meta: { erreurAffichee: true } });

    expect(toastMock).not.toHaveBeenCalled();
  });

  it('se tait pour une requête annulée', async () => {
    await executer({ mutationFn: () => Promise.reject(new CanceledError()) });

    expect(toastMock).not.toHaveBeenCalled();
  });

  it('ne dit rien quand la mutation réussit', async () => {
    await executer({ mutationFn: () => Promise.resolve('ok') });

    expect(toastMock).not.toHaveBeenCalled();
  });
});
