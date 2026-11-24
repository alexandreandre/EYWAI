import { getPasswordChecks, getPasswordStrength } from '@/lib/activationUtils';
import { cn } from '@/lib/utils';

const STRENGTH_LABELS = ['', 'Trop faible', 'Faible', 'Presque', 'Correct'];

/** Force du mot de passe choisi : mêmes règles que le serveur (8 caractères, majuscule, minuscule, chiffre). */
export function JaugeMotDePasse({ password }: { password: string }) {
  const strength = getPasswordStrength(password);
  const checks = getPasswordChecks(password);
  return (
    <div className="space-y-2">
      <div className="flex gap-1" aria-hidden>
        {[1, 2, 3, 4].map((step) => (
          <div
            key={step}
            className={cn(
              'h-1.5 flex-1 rounded-full bg-muted',
              strength >= step &&
                (strength === 4 ? 'bg-green-500' : 'bg-amber-500'),
            )}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {password
          ? STRENGTH_LABELS[strength] || 'Trop faible'
          : 'Au moins 8 caractères, avec majuscule, minuscule et chiffre.'}
        {password && !checks.longueur ? ' — 8 caractères minimum' : null}
      </p>
    </div>
  );
}
