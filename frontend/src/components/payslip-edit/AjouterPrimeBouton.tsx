import { useState } from 'react';
import { PlusCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SaisieModal } from '@/components/SaisieModal';
import type { MonthlyInputCreate } from '@/api/saisies';
import { ligneDepuisSaisie, type LignePrime } from '@/features/payroll/utils/primesEditees';

interface Props {
  employeeId: string;
  year: number;
  month: number;
  onAjout: (lignes: LignePrime[]) => void;
}

/**
 * Même sélecteur que l'onglet Primes : une prime du catalogue, ou une prime
 * libre avec ses cases « soumise à cotisations » et « imposable ». Avec un
 * salarié imposé (`employeeScopeId`), le sélecteur masque la liste des
 * salariés : l'identifiant suffit.
 */
export default function AjouterPrimeBouton({ employeeId, year, month, onAjout }: Props) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOuvert(true)} data-testid="ajouter-prime">
        <PlusCircle className="h-4 w-4 mr-2" />
        Ajouter une prime
      </Button>
      <SaisieModal
        isOpen={ouvert}
        onClose={() => setOuvert(false)}
        onSave={(saisies: MonthlyInputCreate[]) => {
          onAjout(saisies.map(ligneDepuisSaisie));
          setOuvert(false);
        }}
        employees={[{ id: employeeId, first_name: '', last_name: '', job_title: '' }]}
        employeeScopeId={employeeId}
        year={year}
        month={month}
      />
    </>
  );
}
