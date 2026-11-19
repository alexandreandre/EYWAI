import * as React from 'react';
import { Input } from '@/components/ui/input';
import { ecrireDecimal, lireDecimal } from '@/lib/champDecimal';

type Props = Omit<React.ComponentProps<'input'>, 'value' | 'onChange' | 'type' | 'step' | 'min'> & {
  value: number | null | undefined;
  /** Appelé à chaque frappe lisible ; `null` quand le champ est vidé. */
  onValueChange: (valeur: number | null) => void;
};

/** Champ de nombre qui accepte la virgule (« 7,60 »). Voir `lib/champDecimal`. */
export function ChampDecimal({ value, onValueChange, onBlur, ...props }: Props) {
  const [texte, setTexte] = React.useState(() => ecrireDecimal(value));

  // Valeur changée de l'extérieur (autre règle ouverte, remise à zéro) : on la
  // reprend, sauf si c'est déjà ce que dit le texte en cours de frappe (« 7, »).
  React.useEffect(() => {
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
      onChange={(e) => {
        setTexte(e.target.value);
        const v = lireDecimal(e.target.value);
        if (!Number.isNaN(v)) onValueChange(v);
      }}
      onBlur={(e) => {
        if (Number.isNaN(lireDecimal(texte))) setTexte(ecrireDecimal(value));
        onBlur?.(e);
      }}
    />
  );
}
