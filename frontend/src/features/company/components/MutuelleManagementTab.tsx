import { ShieldCheck } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { CompanyMutuelleSection } from '@/features/company/components/CompanyMutuelleSection';
import { CompanyPrevoyanceFormulesSection } from '@/features/company/components/CompanyPrevoyanceFormulesSection';
import { estRoleRh } from '@/lib/rolesRh';

/**
 * Onglet « Mutuelle et prévoyance » de la page société (27/11/2026) :
 * la prévoyance vient de l'onglet « Paramètres paie », à côté de la mutuelle.
 */
export default function MutuelleManagementTab() {
  const { user } = useAuth();
  const canEdit = Boolean(user?.role && ['admin', 'rh'].includes(user.role));
  // Même droit qu'avant le déplacement (onglet Paramètres paie).
  const canEditPrevoyance = estRoleRh(user?.role) && !user?.consultation;

  return (
    <div className="space-y-6">
      <CompanyMutuelleSection canEdit={canEdit} />
      <Card id="prevoyance">
        <CardHeader>
          <CardTitle className="flex items-center">
            <ShieldCheck className="mr-2 h-5 w-5" />
            Prévoyance
          </CardTitle>
          <CardDescription className="mt-1.5">
            Formules de la société, à choisir sur la fiche du salarié
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CompanyPrevoyanceFormulesSection canEdit={canEditPrevoyance} />
        </CardContent>
      </Card>
    </div>
  );
}
