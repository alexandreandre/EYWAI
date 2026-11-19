import * as React from 'react';
import { Input } from '@/components/ui/input';
import { ecrireDecimal, lireDecimal } from '@/lib/champDecimal';

type Props = Omit<React.ComponentProps<'input'>, 'value' | 'onChange' | 'type' | 'step' | 'min'> & {
  value: number | null | undefined;
  /** Appelé à chaque frappe lisible ; `null` quand le champ est vidé. */
  onValueChange: (valeur: number | null) => void;
};

/** Champ de nombre qui accepte la virgule (« 7,60 »). Voir `lib/champDecimal`.
 *
 * Pendant la frappe, le texte n'est jamais réécrit : l'appelant peut ramener la
 * valeur à un repli (`v || 1`, `v ?? 0`) sans casser « 0,5 » ni « 7,60 ». À la
 * sortie du champ, le texte montre la valeur retenue si elle diffère de ce qui
 * est tapé (champ vidé → le repli, texte illisible → la dernière valeur). */
export function ChampDecimal({ value, onValueChange, onFocus, onBlur, ...props }: Props) {
  const [texte, setTexte] = React.useState(() => ecrireDecimal(value));
  const enFrappe = React.useRef(false);

  // Valeur changée de l'extérieur (autre règle ouverte) : reprise, sauf pendant la frappe.
  React.useEffect(() => {
    if (enFrappe.current) return;
    setTexte((courant) => (lireDecimal(courant) === (value ?? null) ? courant : ecrireDecimal(value)));
  }, [value]);

  const lu = lireDecimal(texte);
  return (
    <Input
      {...props}
      type="text"
      inputMode="decimal"
      value={texte}
      aria-invalid={Number.isNaN(lu) || undefined}
      onFocus={(e) => {
        enFrappe.current = true;
        onFocus?.(e);
      }}
      onChange={(e) => {
        setTexte(e.target.value);
        const v = lireDecimal(e.target.value);
        if (!Number.isNaN(v)) onValueChange(v);
      }}
      onBlur={(e) => {
        enFrappe.current = false;
        if (lireDecimal(texte) !== (value ?? null)) setTexte(ecrireDecimal(value));
        onBlur?.(e);
      }}
    />
  );
}
