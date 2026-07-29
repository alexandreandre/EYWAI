import { useEffect, useState } from 'react';
import apiClient from '@/api/apiClient';

type Statut = { is_test: boolean; last_refresh_at: string | null };

/**
 * Bandeau permanent de l'environnement de test.
 *
 * Le rendu dépend de VITE_APP_ENV, figé au build : le composant est éliminé du
 * bundle de production plutôt que masqué à l'exécution. Le bandeau ne peut donc
 * pas apparaître en production, ni disparaître par accident en test.
 */
export function TestEnvBanner() {
  const estTest = import.meta.env.VITE_APP_ENV === 'test';
  const [statut, setStatut] = useState<Statut | null>(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    if (!estTest) return;
    apiClient
      .get<Statut>('/api/test-env/status')
      .then((r) => setStatut(r.data))
      .catch(() => setStatut(null));
  }, [estTest]);

  if (!estTest) return null;

  const resynchroniser = async () => {
    const ok = window.confirm(
      "Resynchroniser depuis la production ?\n\n" +
        "Toutes les manipulations faites dans l'environnement de test seront " +
        'définitivement perdues et remplacées par les données de production.',
    );
    if (!ok) return;
    setEnCours(true);
    try {
      await apiClient.post('/api/test-env/refresh');
      window.alert(
        'Resynchro lancée. Elle prend quelques minutes ; rechargez la page ensuite ' +
          'pour voir la nouvelle date de dernière resynchro.',
      );
    } catch {
      window.alert("Échec du déclenchement de la resynchro.");
    } finally {
      setEnCours(false);
    }
  };

  const derniere = statut?.last_refresh_at
    ? new Date(statut.last_refresh_at).toLocaleString('fr-FR')
    : 'jamais';

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-3 bg-amber-600 px-4 py-1.5 text-sm font-semibold text-white"
    >
      <span>ENVIRONNEMENT DE TEST — les données sont une copie de la production</span>
      <span className="font-normal opacity-90">dernière resynchro : {derniere}</span>
      <button
        type="button"
        onClick={resynchroniser}
        disabled={enCours}
        className="ml-auto rounded border border-white/40 px-2 py-0.5 font-medium hover:bg-white/10 disabled:opacity-60"
      >
        {enCours ? 'Resynchro en cours…' : 'Resynchroniser depuis la prod'}
      </button>
    </div>
  );
}
