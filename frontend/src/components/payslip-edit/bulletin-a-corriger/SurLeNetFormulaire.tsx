/** Un remboursement ou une retenue sur le net à payer : ne touche ni le brut ni les cotisations. */
import { useState } from 'react';
import type { PrimeAjoutee } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { lireNombre } from '@/lib/nombreSaisi';
import { cn } from '@/lib/utils';

export default function SurLeNetFormulaire({ onAjout }: { onAjout: (prime: PrimeAjoutee) => void }) {
  const [sens, setSens] = useState<'versement' | 'retenue'>('versement');
  const [libelle, setLibelle] = useState('');
  const [texte, setTexte] = useState('');
  const montant = lireNombre(texte);
  const pret = libelle.trim().length >= 3 && montant !== null && montant > 0;
  return (
    <div className="space-y-3" data-testid="formulaire-sur-le-net">
      <div className="inline-flex overflow-hidden rounded-md border">
        {(['versement', 'retenue'] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSens(s)}
            className={cn('px-3 py-1 text-sm', sens === s ? 'bg-primary text-primary-foreground' : 'bg-background')}
          >
            {s === 'versement' ? 'On lui verse' : 'On lui retient'}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="net-libelle">Libellé sur le bulletin</Label>
          <Input id="net-libelle" placeholder="Remboursement de frais" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="net-montant">Montant (€)</Label>
          <Input id="net-montant" inputMode="decimal" value={texte} onChange={(e) => setTexte(e.target.value)} />
        </div>
      </div>
      <Button
        disabled={!pret}
        data-testid="ajouter-sur-le-net"
        onClick={() => {
          if (!pret || montant === null) return;
          onAjout({
            name: libelle.trim(),
            amount: sens === 'retenue' ? -montant : montant,
            is_socially_taxed: false,
            is_taxable: false,
            sur_le_net: true,
            catalog_prime_id: null,
          });
          setLibelle('');
          setTexte('');
        }}
      >
        Ajouter au bulletin
      </Button>
    </div>
  );
}
