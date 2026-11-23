import { Eye } from 'lucide-react';

import { useAuth } from '@/contexts/AuthContext';

/**
 * Accès en consultation (expert-comptable) : le compte voit tout ce que voit le
 * service RH, et le serveur lui refuse toute modification. Le bandeau le dit
 * en haut de chaque page, pour qu'un bouton refusé ne surprenne pas.
 */
export function BandeauConsultation() {
  const { user } = useAuth();
  if (!user?.consultation) return null;
  return (
    <div
      role="status"
      className="mb-4 flex items-start gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-100"
    >
      <Eye className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p>
        <span className="font-medium">Accès en consultation.</span> Vous voyez les
        bulletins, les exports et les réglages de paie, sans pouvoir les modifier.
        Les fichiers que vous téléchargez ne changent rien pour la société.
      </p>
    </div>
  );
}
