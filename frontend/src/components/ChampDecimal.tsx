/**
 * Champ de montant qui accepte le point et la virgule (retour B12 du 10/11).
 *
 * Un `<input type="number">` refuse « 12,5 » selon la langue du navigateur et
 * rend une valeur vide sans rien dire. Ce champ garde le texte tapé (« 12, »,
 * « - ») et émet le nombre lu, ou "" tant qu'il n'est pas lisible.
 */
import { useEffect, useRef, useState, type ComponentProps } from 'react';

import { Input } from '@/components/ui/input';
import { lireNombre } from '@/lib/nombreSaisi';

type Props = Omit<ComponentProps<typeof Input>, 'value' | 'onChange' | 'type'> & {
  value: number | '';
  onValeur: (valeur: number | '') => void;
};

function texteDe(valeur: number | ''): string {
  return valeur === '' ? '' : String(valeur).replace('.', ',');
}

export function ChampDecimal({ value, onValeur, ...props }: Props) {
  const [texte, setTexte] = useState(texteDe(value));
  const dernierEmis = useRef<number | ''>(value);
  useEffect(() => {
    // Ne resynchronise que sur une valeur venue d'ailleurs (calcul du brut, prime choisie).
    if (value !== dernierEmis.current) {
      dernierEmis.current = value;
      setTexte(texteDe(value));
    }
  }, [value]);
  return (
    <Input
      {...props}
      type="text"
      inputMode="decimal"
      value={texte}
      onChange={(e) => {
        setTexte(e.target.value);
        const lu = lireNombre(e.target.value);
        const emis = lu === null ? '' : lu;
        dernierEmis.current = emis;
        onValeur(emis);
      }}
    />
  );
}
