// frontend/src/components/exit-document-edit/SoldeToutCompteSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import DynamicLineList, { LineField } from './DynamicLineList';

interface SoldeToutCompteSectionProps {
  data: any;
  onChange: (newData: any) => void;
}

export default function SoldeToutCompteSection({ data, onChange }: SoldeToutCompteSectionProps) {
  const updateField = (section: string, field: string, value: string | number) => {
    const newData = { ...data };
    if (!newData[section]) {
      newData[section] = {};
    }
    newData[section][field] = value;
    onChange(newData);
  };

  const updateIndemnityField = (indemnityType: string, field: string, value: number) => {
    const newData = { ...data };
    if (!newData.indemnities) {
      newData.indemnities = {};
    }
    if (!newData.indemnities[indemnityType]) {
      newData.indemnities[indemnityType] = {};
    }
    newData.indemnities[indemnityType][field] = value;
    onChange(newData);
  };

  const employee = data.employee || {};
  const company = data.company || {};
  const exit = data.exit || {};
  const indemnities = data.indemnities || {};

  return (
    <div className="space-y-6">
      {/* Section Entreprise */}
      <Card>
        <CardHeader>
          <CardTitle>Informations de l'entreprise</CardTitle>
          <CardDescription>
            En-tête du solde de tout compte
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
        </CardContent>
      </Card>

      {/* Section Collaborateur */}
      <Card>
        <CardHeader>
          <CardTitle>Informations du collaborateur</CardTitle>
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

      {/* Section Indemnités */}
      <Card>
        <CardHeader>
          <CardTitle>Indemnités et sommes dues</CardTitle>
          <CardDescription>
            Montants en euros (€)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Indemnité de préavis */}
          {indemnities.indemnite_preavis && (
            <div className="space-y-2">
              <h4 className="font-medium text-sm">Indemnité de préavis</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="preavis-montant">Montant (€)</Label>
                  <Input
                    id="preavis-montant"
                    type="number"
                    step="0.01"
                    value={indemnities.indemnite_preavis.montant || 0}
                    onChange={(e) => updateIndemnityField('indemnite_preavis', 'montant', parseFloat(e.target.value))}
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label htmlFor="preavis-description">Description</Label>
                  <Input
                    id="preavis-description"
                    value={indemnities.indemnite_preavis.description || ''}
                    onChange={(e) => updateField('indemnities', 'indemnite_preavis', { ...indemnities.indemnite_preavis, description: e.target.value })}
                    className="mt-2"
                  />
                </div>
              </div>
            </div>
          )}

          <Separator />

          {/* Indemnité de congés */}
          {indemnities.indemnite_conges && (
            <div className="space-y-2">
              <h4 className="font-medium text-sm">Indemnité compensatrice de congés payés</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="conges-montant">Montant (€)</Label>
                  <Input
                    id="conges-montant"
                    type="number"
                    step="0.01"
                    value={indemnities.indemnite_conges.montant || 0}
                    onChange={(e) => updateIndemnityField('indemnite_conges', 'montant', parseFloat(e.target.value))}
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label htmlFor="conges-description">Description</Label>
                  <Input
                    id="conges-description"
                    value={indemnities.indemnite_conges.description || ''}
                    onChange={(e) => updateField('indemnities', 'indemnite_conges', { ...indemnities.indemnite_conges, description: e.target.value })}
                    className="mt-2"
                  />
                </div>
              </div>
            </div>
          )}

          <Separator />

          {/* Indemnité de licenciement */}
          {indemnities.indemnite_licenciement && (
            <div className="space-y-2">
              <h4 className="font-medium text-sm">Indemnité légale de licenciement</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="licenciement-montant">Montant (€)</Label>
                  <Input
                    id="licenciement-montant"
                    type="number"
                    step="0.01"
                    value={indemnities.indemnite_licenciement.montant || 0}
                    onChange={(e) => updateIndemnityField('indemnite_licenciement', 'montant', parseFloat(e.target.value))}
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label htmlFor="licenciement-description">Description</Label>
                  <Input
                    id="licenciement-description"
                    value={indemnities.indemnite_licenciement.description || ''}
                    onChange={(e) => updateField('indemnities', 'indemnite_licenciement', { ...indemnities.indemnite_licenciement, description: e.target.value })}
                    className="mt-2"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Indemnité de rupture conventionnelle */}
          {indemnities.indemnite_rupture_conventionnelle && (
            <div className="space-y-2">
              <h4 className="font-medium text-sm">Indemnité de rupture conventionnelle</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="rupture-montant">Montant négocié (€)</Label>
                  <Input
                    id="rupture-montant"
                    type="number"
                    step="0.01"
                    value={indemnities.indemnite_rupture_conventionnelle.montant_negocie || 0}
                    onChange={(e) => updateIndemnityField('indemnite_rupture_conventionnelle', 'montant_negocie', parseFloat(e.target.value))}
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label htmlFor="rupture-description">Description</Label>
                  <Input
                    id="rupture-description"
                    value={indemnities.indemnite_rupture_conventionnelle.description || ''}
                    onChange={(e) => updateField('indemnities', 'indemnite_rupture_conventionnelle', { ...indemnities.indemnite_rupture_conventionnelle, description: e.target.value })}
                    className="mt-2"
                  />
                </div>
              </div>
            </div>
          )}

          <Separator />

          {/* Lignes personnalisées d'indemnités */}
          <DynamicLineList
            title="Indemnités et sommes personnalisées"
            description="Ajoutez des lignes supplémentaires d'indemnités ou de sommes dues"
            category="indemnities.custom_lines"
            fields={[
              {
                key: 'label',
                label: 'Libellé',
                type: 'text',
                placeholder: 'Ex: Prime exceptionnelle, Remboursement frais...',
                required: true,
              },
              {
                key: 'amount',
                label: 'Montant (€)',
                type: 'number',
                placeholder: '0.00',
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
            emptyMessage="Aucune indemnité personnalisée ajoutée"
          />

          <Separator />

          {/* Cotisations et prélèvements personnalisés */}
          <DynamicLineList
            title="Cotisations et prélèvements personnalisés"
            description="Ajoutez des lignes de cotisations ou prélèvements supplémentaires"
            category="deductions.custom_lines"
            fields={[
              {
                key: 'label',
                label: 'Libellé',
                type: 'text',
                placeholder: 'Ex: Cotisation mutuelle, Prélèvement à la source...',
                required: true,
              },
              {
                key: 'amount',
                label: 'Montant (€)',
                type: 'number',
                placeholder: '0.00',
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
            emptyMessage="Aucune cotisation ou prélèvement personnalisé ajouté"
          />

          <Separator />

          {/* Totaux */}
          <div className="bg-slate-50 p-4 rounded-lg space-y-2">
            <div className="flex justify-between items-center">
              <span className="font-medium">Total brut des indemnités</span>
              <Input
                type="number"
                step="0.01"
                value={indemnities.total_gross_indemnities || 0}
                onChange={(e) => updateField('indemnities', 'total_gross_indemnities', parseFloat(e.target.value))}
                className="w-40 text-right font-bold"
              />
            </div>
            <div className="flex justify-between items-center">
              <span className="font-medium text-green-600">Total net estimé</span>
              <Input
                type="number"
                step="0.01"
                value={indemnities.total_net_indemnities || 0}
                onChange={(e) => updateField('indemnities', 'total_net_indemnities', parseFloat(e.target.value))}
                className="w-40 text-right font-bold text-green-600"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Informations d'aide */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <p className="text-sm text-blue-900">
            <strong>Note:</strong> Le solde de tout compte récapitule l'ensemble des sommes versées au collaborateur
            à la rupture du contrat. Le collaborateur dispose d'un délai de dénonciation après signature.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
