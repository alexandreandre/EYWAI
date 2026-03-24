// frontend/src/components/exit-document-edit/AttestationPoleEmploiSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import DynamicLineList from './DynamicLineList';

interface AttestationPoleEmploiSectionProps {
  data: any;
  onChange: (newData: any) => void;
}

export default function AttestationPoleEmploiSection({ data, onChange }: AttestationPoleEmploiSectionProps) {
  const updateField = (section: string, field: string, value: string | number) => {
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
      {/* Section Employeur */}
      <Card>
        <CardHeader>
          <CardTitle>Informations de l'employeur</CardTitle>
          <CardDescription>
            Raison sociale et coordonnées
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="company-name">Raison sociale</Label>
              <Input
                id="company-name"
                value={company.name || company.raison_sociale || ''}
                onChange={(e) => updateField('company', 'name', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="company-siret">Numéro SIRET</Label>
              <Input
                id="company-siret"
                value={company.siret || ''}
                onChange={(e) => updateField('company', 'siret', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="company-address">Adresse complète</Label>
            <Input
              id="company-address"
              value={company.address || ''}
              onChange={(e) => updateField('company', 'address', e.target.value)}
              className="mt-2"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="company-naf">Code NAF/APE</Label>
              <Input
                id="company-naf"
                value={company.naf_code || company.ape_code || ''}
                onChange={(e) => updateField('company', 'naf_code', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="company-urssaf">Numéro URSSAF</Label>
              <Input
                id="company-urssaf"
                value={company.urssaf_number || ''}
                onChange={(e) => updateField('company', 'urssaf_number', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section Collaborateur */}
      <Card>
        <CardHeader>
          <CardTitle>Informations du collaborateur</CardTitle>
          <CardDescription>
            État civil et coordonnées
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

          <div className="grid grid-cols-3 gap-4">
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
              <Label htmlFor="employee-birthplace">Lieu de naissance</Label>
              <Input
                id="employee-birthplace"
                value={employee.birth_place || employee.lieu_naissance || ''}
                onChange={(e) => updateField('employee', 'birth_place', e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="employee-social-security">N° Sécurité Sociale</Label>
              <Input
                id="employee-social-security"
                value={employee.social_security_number || employee.numero_securite_sociale || ''}
                onChange={(e) => updateField('employee', 'social_security_number', e.target.value)}
                className="mt-2"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="employee-address">Adresse du collaborateur</Label>
            <Input
              id="employee-address"
              value={employee.address || ''}
              onChange={(e) => updateField('employee', 'address', e.target.value)}
              className="mt-2"
            />
          </div>
        </CardContent>
      </Card>

      {/* Section Contrat */}
      <Card>
        <CardHeader>
          <CardTitle>Informations du contrat</CardTitle>
          <CardDescription>
            Dates et nature du contrat
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
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
            <div>
              <Label htmlFor="contract-type">Type de contrat</Label>
              <Input
                id="contract-type"
                value={employee.contract_type || 'CDI'}
                onChange={(e) => updateField('employee', 'contract_type', e.target.value)}
                className="mt-2"
                placeholder="CDI, CDD, etc."
              />
            </div>
          </div>

          <div>
            <Label htmlFor="job-title">Emploi occupé</Label>
            <Input
              id="job-title"
              value={employee.job_title || ''}
              onChange={(e) => updateField('employee', 'job_title', e.target.value)}
              className="mt-2"
            />
          </div>

          <div>
            <Label htmlFor="exit-reason">Motif de rupture du contrat</Label>
            <Textarea
              id="exit-reason"
              value={exit.exit_reason || ''}
              onChange={(e) => updateField('exit', 'exit_reason', e.target.value)}
              className="mt-2"
              rows={2}
              placeholder="Ex: Démission, Licenciement pour motif personnel, etc."
            />
          </div>
        </CardContent>
      </Card>

      {/* Informations supplémentaires */}
      <DynamicLineList
        title="Informations complémentaires"
        description="Ajoutez des lignes d'informations supplémentaires pour l'attestation Pôle Emploi"
        category="additional_info"
        fields={[
          {
            key: 'label',
            label: 'Libellé',
            type: 'text',
            placeholder: 'Ex: Période de chômage partiel, Arrêt maladie...',
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
        emptyMessage="Aucune information complémentaire ajoutée"
      />

      {/* Informations d'aide */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <p className="text-sm text-blue-900">
            <strong>Note:</strong> L'attestation Pôle Emploi doit être transmise au collaborateur dans les 48h suivant la fin du contrat.
            Ce document permet au collaborateur de faire valoir ses droits à l'assurance chômage.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
