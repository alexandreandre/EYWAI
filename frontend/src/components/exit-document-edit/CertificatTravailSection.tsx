// frontend/src/components/exit-document-edit/CertificatTravailSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import DynamicLineList from './DynamicLineList';

interface CertificatTravailSectionProps {
  data: any;
  onChange: (newData: any) => void;
}

export default function CertificatTravailSection({ data, onChange }: CertificatTravailSectionProps) {
  const updateField = (section: string, field: string, value: string) => {
    const newData = { ...data };
    if (!newData[section]) {
      newData[section] = {};
    }
    newData[section][field] = value;
    onChange(newData);
  };

  const employee = data.employee || {};
  const company = data.company || {};
  const exit = data.exit || {};

  return (
    <div className="space-y-6">
      {/* Section Entreprise */}
      <Card>
        <CardHeader>
          <CardTitle>Informations de l'entreprise</CardTitle>
          <CardDescription>
            Ces informations apparaissent en en-tête du certificat de travail
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="company-name">Nom de l'entreprise</Label>
              <Input
                id="company-name"
                value={company.name || company.raison_sociale || ''}
                onChange={(e) => updateField('company', 'name', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="company-siret">SIRET</Label>
              <Input
                id="company-siret"
                value={company.siret || ''}
                onChange={(e) => updateField('company', 'siret', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="company-address">Adresse</Label>
            <Input
              id="company-address"
              value={company.address || ''}
              onChange={(e) => updateField('company', 'address', e.target.value)}
              className="mt-2"
            />
          </div>

          <div>
            <Label htmlFor="company-city">Ville</Label>
            <Input
              id="company-city"
              value={company.city || ''}
              onChange={(e) => updateField('company', 'city', e.target.value)}
              className="mt-2"
            />
          </div>
        </CardContent>
      </Card>

      {/* Section Collaborateur */}
      <Card>
        <CardHeader>
          <CardTitle>Informations du collaborateur</CardTitle>
          <CardDescription>
            Identité et poste du collaborateur
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="employee-first-name">Prénom</Label>
              <Input
                id="employee-first-name"
                value={employee.first_name || ''}
                onChange={(e) => updateField('employee', 'first_name', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="employee-last-name">Nom</Label>
              <Input
                id="employee-last-name"
                value={employee.last_name || ''}
                onChange={(e) => updateField('employee', 'last_name', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="employee-birthdate">Date de naissance</Label>
              <Input
                id="employee-birthdate"
                type="date"
                value={employee.date_naissance || employee.birthdate || ''}
                onChange={(e) => updateField('employee', 'date_naissance', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="employee-job-title">Poste occupé</Label>
              <Input
                id="employee-job-title"
                value={employee.job_title || ''}
                onChange={(e) => updateField('employee', 'job_title', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section Dates */}
      <Card>
        <CardHeader>
          <CardTitle>Dates du contrat</CardTitle>
          <CardDescription>
            Dates d'entrée et de sortie
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="hire-date">Date d'embauche</Label>
              <Input
                id="hire-date"
                type="date"
                value={employee.hire_date || ''}
                onChange={(e) => updateField('employee', 'hire_date', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="last-working-day">Dernier jour travaillé</Label>
              <Input
                id="last-working-day"
                type="date"
                value={exit.last_working_day || ''}
                onChange={(e) => updateField('exit', 'last_working_day', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Informations supplémentaires */}
      <DynamicLineList
        title="Informations supplémentaires"
        description="Ajoutez des lignes d'informations complémentaires pour le certificat de travail"
        category="additional_info"
        fields={[
          {
            key: 'label',
            label: 'Libellé',
            type: 'text',
            placeholder: 'Ex: Période de stage, Formation suivie...',
            required: true,
          },
          {
            key: 'value',
            label: 'Valeur',
            type: 'text',
            placeholder: 'Valeur de l\'information',
            required: true,
          },
          {
            key: 'description',
            label: 'Description',
            type: 'textarea',
            placeholder: 'Description détaillée (optionnel)',
          },
        ]}
        data={data}
        onChange={onChange}
        emptyMessage="Aucune information supplémentaire ajoutée"
      />

      {/* Informations d'aide */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <p className="text-sm text-blue-900">
            <strong>Note:</strong> Le certificat de travail est un document légal obligatoire.
            Assurez-vous que toutes les informations sont exactes avant de l'envoyer au collaborateur.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
