import { Loader2 } from 'lucide-react';
import type { Control } from 'react-hook-form';
import { useWatch } from 'react-hook-form';

import type { CompanyCollectiveAgreementWithDetails, ClassificationConventionnelle } from '@/api/collectiveAgreements';
import type { MutuelleType } from '@/api/mutuelleTypes';
import type { Team } from '@/api/teams';
import { Checkbox } from '@/components/ui/checkbox';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { isCddOrStage, normalizeNir } from '@/features/employee-detail/components/employeeProfileFormUtils';
import type { EmployeeProfileEditFormValues } from '@/features/employee-detail/components/employeeProfileEditSchema';
import { getCollectiveAgreementLabel } from '@/lib/employeeDisplayUtils';

interface EmployeeProfileEditFormProps {
  control: Control<EmployeeProfileEditFormValues>;
  companyAgreements: CompanyCollectiveAgreementWithDetails[];
  classificationsCc: ClassificationConventionnelle[];
  activeTeams: Team[];
  availableMutuelles: MutuelleType[];
  loadingMutuelles: boolean;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="border-b pb-2 text-sm font-semibold text-foreground">{children}</h3>
  );
}

export function EmployeeProfileEditForm({
  control,
  companyAgreements,
  classificationsCc,
  activeTeams,
  availableMutuelles,
  loadingMutuelles,
}: EmployeeProfileEditFormProps) {
  const contractType = useWatch({ control, name: 'contract_type' });
  const statut = useWatch({ control, name: 'statut' });
  const selectedCcId = useWatch({ control, name: 'collective_agreement_id' });
  const isPasPerso = useWatch({ control, name: 'specificites_paie.prelevement_a_la_source.is_personnalise' });
  const isResidencePermit = useWatch({ control, name: 'is_subject_to_residence_permit' });
  const isCadre = statut?.toLowerCase() === 'cadre';
  const showContractEnd = isCddOrStage(contractType);

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <SectionTitle>Identité</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={control}
            name="first_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Prénom</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="last_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Nom</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl><Input {...field} type="email" /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="phone_number"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Téléphone</FormLabel>
                <FormControl><Input {...field} type="tel" /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="nir"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>N° de sécurité sociale</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    inputMode="numeric"
                    maxLength={15}
                    onChange={(e) => field.onChange(normalizeNir(e.target.value))}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="date_naissance"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date de naissance</FormLabel>
                <FormControl><Input {...field} type="date" /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="lieu_naissance"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Lieu de naissance</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="nationalite"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Nationalité</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle>Adresse &amp; RIB</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={control}
            name="adresse.rue"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Rue</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="adresse.code_postal"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Code postal</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="adresse.ville"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Ville</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="coordonnees_bancaires.iban"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>IBAN</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="coordonnees_bancaires.bic"
            render={({ field }) => (
              <FormItem>
                <FormLabel>BIC</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle>Contrat</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={control}
            name="hire_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date d&apos;entrée</FormLabel>
                <FormControl><Input {...field} type="date" /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="contract_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Type de contrat</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {['CDI', 'CDD', 'Contrat d\'alternance', 'Convention de stage'].map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="job_title"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Intitulé du poste</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="statut"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Statut</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="Non-Cadre">Non-Cadre</SelectItem>
                    <SelectItem value="Cadre">Cadre</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="duree_hebdomadaire"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Durée hebdomadaire (h)</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    type="number"
                    min={0}
                    step="0.5"
                    onChange={(e) => field.onChange(e.target.valueAsNumber || '')}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="is_temps_partiel"
            render={({ field }) => (
              <FormItem className="flex items-center gap-2 space-y-0 sm:col-span-2">
                <FormControl>
                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
                <FormLabel className="font-normal">Temps partiel</FormLabel>
              </FormItem>
            )}
          />
          {showContractEnd && (
            <FormField
              control={control}
              name="contract_end_date"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Date de fin de contrat</FormLabel>
                  <FormControl><Input {...field} type="date" /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle>Rémunération</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={control}
            name="salaire_de_base.valeur"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Salaire de base mensuel brut (€)</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    type="number"
                    min={0}
                    step="0.01"
                    onChange={(e) => field.onChange(e.target.valueAsNumber || '')}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={control}
            name="collective_agreement_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Convention collective</FormLabel>
                <Select
                  onValueChange={(v) => field.onChange(v === '__none__' ? null : v)}
                  value={field.value ?? '__none__'}
                >
                  <FormControl>
                    <SelectTrigger><SelectValue placeholder="Aucune" /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="__none__">Aucune</SelectItem>
                    {companyAgreements.map((a) => (
                      <SelectItem key={a.collective_agreement_id} value={a.collective_agreement_id}>
                        {getCollectiveAgreementLabel(a)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          {selectedCcId && classificationsCc.length > 0 && (
            <FormField
              control={control}
              name="classification_conventionnelle"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Classification conventionnelle</FormLabel>
                  <Select
                    onValueChange={(key) => {
                      const c = classificationsCc.find(
                        (item) => `${item.groupe_emploi}-${item.classe_emploi}-${item.coefficient}` === key,
                      );
                      if (c) field.onChange({
                        groupe_emploi: c.groupe_emploi,
                        classe_emploi: c.classe_emploi,
                        coefficient: c.coefficient,
                      });
                    }}
                    value={
                      field.value
                        ? `${field.value.groupe_emploi}-${field.value.classe_emploi}-${field.value.coefficient}`
                        : undefined
                    }
                  >
                    <FormControl>
                      <SelectTrigger><SelectValue placeholder="Choisir une classification" /></SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {classificationsCc.map((c) => {
                        const key = `${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}`;
                        return (
                          <SelectItem key={key} value={key}>
                            {c.groupe_emploi} / Classe {c.classe_emploi} / Coef. {c.coefficient}
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle>Organisation</SectionTitle>
        <FormField
          control={control}
          name="team_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Équipe</FormLabel>
              <Select
                onValueChange={(v) => field.onChange(v === '__none__' ? '' : v)}
                value={field.value || '__none__'}
              >
                <FormControl>
                  <SelectTrigger><SelectValue placeholder="Aucune équipe" /></SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="__none__">Aucune équipe</SelectItem>
                  {activeTeams.map((t) => (
                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
      </section>

      <section className="space-y-3">
        <SectionTitle>Paie sociale</SectionTitle>
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium">Mutuelle</p>
            {loadingMutuelles ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : availableMutuelles.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucune formule configurée dans Mon Entreprise.
              </p>
            ) : (
              <FormField
                control={control}
                name="specificites_paie.mutuelle.mutuelle_type_ids"
                render={({ field }) => (
                  <FormItem>
                    <div className="space-y-2">
                      {availableMutuelles.map((m) => (
                        <div key={m.id} className="flex items-center gap-2 rounded-md border p-2">
                          <Checkbox
                            checked={field.value?.includes(m.id) ?? false}
                            onCheckedChange={(checked) => {
                              const ids = field.value ?? [];
                              field.onChange(
                                checked ? [...ids, m.id] : ids.filter((id) => id !== m.id),
                              );
                            }}
                          />
                          <span className="text-sm">{m.libelle}</span>
                        </div>
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
          </div>

          {isCadre && (
            <FormField
              control={control}
              name="specificites_paie.prevoyance.adhesion"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2 space-y-0">
                  <FormControl>
                    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                  <FormLabel className="font-normal">Adhésion prévoyance (cadre)</FormLabel>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <FormField
              control={control}
              name="specificites_paie.titres_restaurant.nombre_par_mois"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Titres-restaurant / mois</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="number"
                      min={0}
                      onChange={(e) => field.onChange(Number.parseInt(e.target.value, 10) || 0)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="specificites_paie.transport.abonnement_mensuel_total"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Abonnement transport (€/mois)</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="number"
                      min={0}
                      step="0.01"
                      onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={control}
            name="specificites_paie.prelevement_a_la_source.is_personnalise"
            render={({ field }) => (
              <FormItem className="flex items-center gap-2 space-y-0">
                <FormControl>
                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
                <FormLabel className="font-normal">Prélèvement à la source personnalisé</FormLabel>
              </FormItem>
            )}
          />
          {isPasPerso && (
            <FormField
              control={control}
              name="specificites_paie.prelevement_a_la_source.taux"
              render={({ field }) => (
                <FormItem className="max-w-xs">
                  <FormLabel>Taux PAS (%)</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="number"
                      min={0}
                      max={100}
                      step="0.01"
                      onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle>Titre de séjour</SectionTitle>
        <FormField
          control={control}
          name="is_subject_to_residence_permit"
          render={({ field }) => (
            <FormItem className="flex items-center gap-2 space-y-0">
              <FormControl>
                <Checkbox checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
              <FormLabel className="font-normal">Soumis à titre de séjour</FormLabel>
            </FormItem>
          )}
        />
        {isResidencePermit && (
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField
              control={control}
              name="residence_permit_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="residence_permit_number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Numéro</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="residence_permit_expiry_date"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Date d&apos;expiration</FormLabel>
                  <FormControl><Input {...field} type="date" /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}
      </section>
    </div>
  );
}
