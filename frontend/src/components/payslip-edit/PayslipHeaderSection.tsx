// frontend/src/components/payslip-edit/PayslipHeaderSection.tsx

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Building2, User } from 'lucide-react';

interface PayslipHeaderSectionProps {
  data: any;
  onChange: (data: any) => void;
}

export default function PayslipHeaderSection({ data, onChange }: PayslipHeaderSectionProps) {
  const handleChange = (path: string[], value: any) => {
    const newData = JSON.parse(JSON.stringify(data));
    let current = newData;
    for (let i = 0; i < path.length - 1; i++) {
      if (!current[path[i]]) current[path[i]] = {};
      current = current[path[i]];
    }
    current[path[path.length - 1]] = value;
    onChange(newData);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>En-tête du bulletin</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-6">
          {/* Entreprise */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Building2 className="h-4 w-4" />
              Entreprise
            </div>
            <div className="space-y-2">
              <div>
                <Label htmlFor="raison_sociale" className="text-xs">Raison sociale</Label>
                <Input
                  id="raison_sociale"
                  value={data?.entreprise?.raison_sociale || ''}
                  onChange={(e) => handleChange(['entreprise', 'raison_sociale'], e.target.value)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="siret" className="text-xs">SIRET</Label>
                <Input
                  id="siret"
                  value={data?.entreprise?.siret || ''}
                  onChange={(e) => handleChange(['entreprise', 'siret'], e.target.value)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="rue" className="text-xs">Adresse</Label>
                <Input
                  id="rue"
                  value={data?.entreprise?.adresse?.rue || ''}
                  onChange={(e) => handleChange(['entreprise', 'adresse', 'rue'], e.target.value)}
                  className="h-8"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label htmlFor="code_postal" className="text-xs">Code postal</Label>
                  <Input
                    id="code_postal"
                    value={data?.entreprise?.adresse?.code_postal || ''}
                    onChange={(e) => handleChange(['entreprise', 'adresse', 'code_postal'], e.target.value)}
                    className="h-8"
                  />
                </div>
                <div>
                  <Label htmlFor="ville" className="text-xs">Ville</Label>
                  <Input
                    id="ville"
                    value={data?.entreprise?.adresse?.ville || ''}
                    onChange={(e) => handleChange(['entreprise', 'adresse', 'ville'], e.target.value)}
                    className="h-8"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Collaborateur */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <User className="h-4 w-4" />
              Collaborateur
            </div>
            <div className="space-y-2">
              <div>
                <Label htmlFor="nom_complet" className="text-xs">Nom complet</Label>
                <Input
                  id="nom_complet"
                  value={data?.salarie?.nom_complet || ''}
                  onChange={(e) => handleChange(['salarie', 'nom_complet'], e.target.value)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="emploi" className="text-xs">Emploi</Label>
                <Input
                  id="emploi"
                  value={data?.salarie?.emploi || ''}
                  onChange={(e) => handleChange(['salarie', 'emploi'], e.target.value)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="statut" className="text-xs">Statut</Label>
                <Input
                  id="statut"
                  value={data?.salarie?.statut || ''}
                  onChange={(e) => handleChange(['salarie', 'statut'], e.target.value)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="nir" className="text-xs">NIR</Label>
                <Input
                  id="nir"
                  value={data?.salarie?.nir || ''}
                  onChange={(e) => handleChange(['salarie', 'nir'], e.target.value)}
                  className="h-8"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t">
          <Label htmlFor="periode" className="text-xs">Période</Label>
          <Input
            id="periode"
            value={data?.periode || ''}
            onChange={(e) => handleChange(['periode'], e.target.value)}
            className="h-8 mt-1"
          />
        </div>
      </CardContent>
    </Card>
  );
}
