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

  const updateRootField = (field: string, value: string | number) => {
    onChange({ ...data, [field]: value });
  };

  const employee = data.employee || {};
  const company = data.company || {};
  const exit = data.exit || {};
  const salaryMonthCount = data.salary_month_count || 25;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Informations de l'employeur</CardTitle>
          <CardDescription>Raison sociale et coordonnées</CardDescription>
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

      <Card>
        <CardHeader>
          <CardTitle>Informations du collaborateur</CardTitle>
          <CardDescription>État civil et coordonnées</CardDescription>
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

      <Card>
        <CardHeader>
          <CardTitle>Informations du contrat</CardTitle>
          <CardDescription>Dates, nature du contrat et convention collective</CardDescription>
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

          <div className="grid grid-cols-2 gap-4">
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
              <Label htmlFor="convention-collective">Convention collective</Label>
              <Input
                id="convention-collective"
                value={data.convention_collective || ''}
                onChange={(e) => updateRootField('convention_collective', e.target.value)}
                className="mt-2"
                placeholder="Ex: Métallurgie — IDCC 3248"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="idcc">Code IDCC</Label>
            <Input
              id="idcc"
              value={data.idcc || ''}
              onChange={(e) => updateRootField('idcc', e.target.value)}
              className="mt-2 max-w-xs"
              placeholder="Ex: 3248"
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

      <DynamicLineList
        title={`Salaires des ${salaryMonthCount} derniers mois`}
        description="Tableau officiel : période de paie, temps de travail, absences non assimilées et salaire brut. Pré-rempli depuis les bulletins de paie."
        category="salary_history"
        fields={[
          {
            key: 'period_label',
            label: 'Période de paie',
            type: 'text',
            placeholder: 'Ex: Janvier 2025',
            required: true,
          },
          {
            key: 'working_time',
            label: 'Temps de travail',
            type: 'text',
            placeholder: 'Ex: 151.67 h ou 22 jours',
          },
          {
            key: 'absences',
            label: 'Absences non assimilées',
            type: 'text',
            placeholder: 'Ex: 3 jours ou Néant',
          },
          {
            key: 'gross_salary',
            label: 'Salaire brut (€)',
            type: 'number',
            placeholder: '0.00',
            required: true,
          },
        ]}
        data={data}
        onChange={onChange}
        emptyMessage="Aucune ligne de salaire — elles seront recalculées à la génération si vides"
      />

      <DynamicLineList
        title="Primes et indemnités perçues"
        description="Primes exceptionnelles ou indemnités perçues sur la période de référence"
        category="primes_lines"
        fields={[
          {
            key: 'nature',
            label: 'Nature',
            type: 'text',
            placeholder: 'Ex: Prime exceptionnelle, 13e mois...',
            required: true,
          },
          {
            key: 'montant',
            label: 'Montant brut (€)',
            type: 'number',
            placeholder: '0.00',
            required: true,
          },
        ]}
        data={data}
        onChange={onChange}
        emptyMessage="Aucune prime renseignée"
      />

      <DynamicLineList
        title="Informations complémentaires"
        description="Informations supplémentaires pour l'attestation employeur"
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
            placeholder: "Valeur de l'information",
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

      <Card className="bg-muted/40 border-muted">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            L&apos;attestation employeur doit être remise au collaborateur dans les 5 jours ouvrés
            suivant la fin du contrat. La version faisant foi auprès de France Travail est transmise
            via la DSN (signalement fin de contrat).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
