import type { UpdateEmployeePayload } from '@/api/employees';
import type { Employee } from '@/features/employee-detail/types';
import type { EmployeeProfileEditFormValues } from '@/features/employee-detail/components/employeeProfileEditSchema';
import { needsContractEndDate, normalizeContractType } from '@/constants/contracts';
import { isEmployeeCadre } from '@/lib/mutuelleUtils';

export function normalizeNir(value: string | null | undefined): string {
  return (value ?? '').replace(/\s/g, '').slice(0, 15);
}

export function readSalaryValue(employee: Employee): number | undefined {
  const raw = employee.salaire_de_base;
  if (!raw || typeof raw !== 'object') return undefined;
  const valeur = (raw as { valeur?: number; montant?: number }).valeur;
  const montant = (raw as { valeur?: number; montant?: number }).montant;
  const n = valeur ?? montant;
  return typeof n === 'number' && n > 0 ? n : undefined;
}

export function readWeeklyHours(employee: Employee): number {
  const raw = employee.duree_hebdomadaire ?? employee.weekly_hours;
  if (typeof raw === 'number' && raw > 0) return raw;
  if (typeof raw === 'string') {
    const n = Number.parseFloat(raw);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return 35;
}

function cleanEmployeeStatut(statut: string | null | undefined): string {
  if (isEmployeeCadre(statut)) return 'Cadre';
  const compact = (statut ?? '').trim().toLowerCase().replace(/\s+/g, '').replace(/-/g, '');
  if (compact.includes('noncadre')) return 'Non-Cadre';
  return statut ?? 'Non-Cadre';
}

export function isProfileIncomplete(employee: Employee): boolean {
  if (employee.profile_complete === false) return true;
  return (employee.missing_payroll_fields?.length ?? 0) > 0;
}

/** Aucune formule mutuelle catalogue (ni lignes legacy) sur la fiche. */
export function isMutuelleMissing(employee: Employee): boolean {
  const mutuelle = employee.specificites_paie?.mutuelle;
  if (!mutuelle || typeof mutuelle !== 'object') return true;
  const ids = mutuelle.mutuelle_type_ids;
  if (Array.isArray(ids) && ids.length > 0) return false;
  const lignes = mutuelle.lignes_specifiques;
  if (Array.isArray(lignes) && lignes.length > 0) return false;
  return true;
}

export function isCddOrStage(contractType: string | null | undefined): boolean {
  return needsContractEndDate(contractType);
}

export function buildDefaultValues(employee: Employee): EmployeeProfileEditFormValues {
  const adresse = employee.adresse ?? {};
  const spec = employee.specificites_paie ?? {};
  const extended = employee as Employee & {
    date_debut_execution?: string | null;
    date_conclusion_contrat?: string | null;
  };
  const mutuelle = spec.mutuelle as { mutuelle_type_ids?: string[] } | undefined;
  const prevoyance = spec.prevoyance as {
    adhesion?: boolean;
    lignes_specifiques?: EmployeeProfileEditFormValues['specificites_paie']['prevoyance']['lignes_specifiques'];
  } | undefined;
  const pas = spec.prelevement_a_la_source as { is_personnalise?: boolean; taux?: number } | undefined;
  const transport = spec.transport as {
    abonnement_mensuel_total?: number;
    indemnite_mensuelle_nette?: number;
  } | undefined;
  const deplacementAstreinte = spec.deplacement_astreinte as {
    enabled?: boolean;
    distance_km_one_way?: number;
    vehicle_cv?: number;
    vehicle_type?: 'voitures' | 'motocyclettes' | 'cyclomoteurs';
  } | undefined;
  const tr = spec.titres_restaurant as { beneficie?: boolean; nombre_par_mois?: number } | undefined;
  const classification = (employee as Employee & { classification_conventionnelle?: EmployeeProfileEditFormValues['classification_conventionnelle'] }).classification_conventionnelle;

  return {
    first_name: employee.first_name ?? '',
    last_name: employee.last_name ?? '',
    email: employee.email ?? '',
    phone_number: employee.phone_number ?? '',
    salary_payment_method:
      (employee.salary_payment_method as 'virement' | 'cheque' | 'especes' | undefined) ??
      'virement',
    nir: normalizeNir(employee.nir),
    date_naissance: employee.date_naissance?.slice(0, 10) ?? '',
    lieu_naissance: employee.lieu_naissance ?? '',
    nationalite: employee.nationalite ?? 'Française',
    adresse: {
      rue: adresse.rue ?? adresse.voie ?? '',
      code_postal: adresse.code_postal ?? '',
      ville: adresse.ville ?? '',
    },
    coordonnees_bancaires: {
      iban: employee.coordonnees_bancaires?.iban ?? '',
      bic: employee.coordonnees_bancaires?.bic ?? '',
    },
    hire_date: employee.hire_date?.slice(0, 10) ?? '',
    job_title: employee.job_title ?? employee.poste ?? '',
    contract_type: normalizeContractType(employee.contract_type),
    statut: cleanEmployeeStatut(employee.statut),
    is_forfait_jour: Boolean(employee.is_forfait_jour) || /forfait jour/i.test(employee.statut ?? ''),
    is_temps_partiel: Boolean((employee as Employee & { is_temps_partiel?: boolean }).is_temps_partiel),
    duree_hebdomadaire: readWeeklyHours(employee),
    contract_end_date: employee.contract_end_date?.slice(0, 10) ?? '',
    date_debut_execution: extended.date_debut_execution?.slice(0, 10) ?? '',
    date_conclusion_contrat: extended.date_conclusion_contrat?.slice(0, 10) ?? '',
    salaire_de_base: {
      valeur: readSalaryValue(employee) ?? ('' as unknown as number),
    },
    collective_agreement_id: employee.collective_agreement_id ?? null,
    classification_conventionnelle: {
      groupe_emploi: classification?.groupe_emploi ?? 'C',
      classe_emploi: classification?.classe_emploi ?? 6,
      coefficient: classification?.coefficient ?? 240,
    },
    team_id: employee.team_id ?? '',
    specificites_paie: {
      prelevement_a_la_source: {
        is_personnalise: pas?.is_personnalise ?? false,
        taux: pas?.taux ?? 0,
      },
      transport: {
        abonnement_mensuel_total: transport?.abonnement_mensuel_total ?? 0,
        indemnite_mensuelle_nette: transport?.indemnite_mensuelle_nette ?? 0,
      },
      titres_restaurant: {
        beneficie: tr?.beneficie ?? true,
        nombre_par_mois: tr?.nombre_par_mois ?? 0,
      },
      mutuelle: {
        mutuelle_type_ids: mutuelle?.mutuelle_type_ids ?? [],
      },
      prevoyance: {
        adhesion: prevoyance?.adhesion ?? false,
        lignes_specifiques: prevoyance?.lignes_specifiques ?? [],
      },
      maintien_regime_apprenti: Boolean(spec.maintien_regime_apprenti),
      personnel_rd_eligible_jei: Boolean(spec.personnel_rd_eligible_jei),
      deplacement_astreinte: {
        enabled: Boolean(deplacementAstreinte?.enabled),
        distance_km_one_way: deplacementAstreinte?.distance_km_one_way ?? undefined,
        vehicle_cv: deplacementAstreinte?.vehicle_cv ?? undefined,
        vehicle_type: deplacementAstreinte?.vehicle_type ?? 'voitures',
      },
    },
    is_subject_to_residence_permit: Boolean(employee.is_subject_to_residence_permit),
    residence_permit_expiry_date: employee.residence_permit_expiry_date?.slice(0, 10) ?? '',
    residence_permit_type: employee.residence_permit_type ?? '',
    residence_permit_number: employee.residence_permit_number ?? '',
  };
}

export function buildUpdatePayload(
  values: EmployeeProfileEditFormValues,
  employee: Employee,
): UpdateEmployeePayload {
  const existingSpec = employee.specificites_paie ?? {};
  const mutuelleIds = values.specificites_paie.mutuelle.mutuelle_type_ids ?? [];

  const payload: UpdateEmployeePayload = {
    first_name: values.first_name.trim(),
    last_name: values.last_name.trim(),
    email: values.email.trim(),
    phone_number: values.phone_number?.trim() || null,
    salary_payment_method: values.salary_payment_method ?? 'virement',
    nir: normalizeNir(values.nir),
    date_naissance: values.date_naissance,
    lieu_naissance: values.lieu_naissance.trim(),
    nationalite: values.nationalite.trim(),
    adresse: {
      rue: values.adresse.rue.trim(),
      code_postal: values.adresse.code_postal.trim(),
      ville: values.adresse.ville.trim(),
    },
    coordonnees_bancaires: {
      iban: values.coordonnees_bancaires.iban.replace(/\s/g, '').toUpperCase(),
      bic: values.coordonnees_bancaires.bic.replace(/\s/g, '').toUpperCase(),
    },
    hire_date: values.hire_date,
    job_title: values.job_title.trim(),
    contract_type: normalizeContractType(values.contract_type),
    statut: values.statut.trim(),
    is_forfait_jour: values.is_forfait_jour,
    is_temps_partiel: values.is_temps_partiel,
    duree_hebdomadaire: values.duree_hebdomadaire,
    contract_end_date: needsContractEndDate(values.contract_type)
      ? values.contract_end_date?.trim() || null
      : null,
    date_debut_execution: values.date_debut_execution?.trim() || null,
    date_conclusion_contrat: values.date_conclusion_contrat?.trim() || null,
    salaire_de_base: { valeur: values.salaire_de_base.valeur },
    collective_agreement_id: values.collective_agreement_id,
    team_id: values.team_id?.trim() && values.team_id !== '__none__' ? values.team_id.trim() : null,
    is_subject_to_residence_permit: values.is_subject_to_residence_permit,
    residence_permit_expiry_date: values.is_subject_to_residence_permit
      ? values.residence_permit_expiry_date?.trim() || null
      : null,
    residence_permit_type: values.is_subject_to_residence_permit
      ? values.residence_permit_type?.trim() || null
      : null,
    residence_permit_number: values.is_subject_to_residence_permit
      ? values.residence_permit_number?.trim() || null
      : null,
    specificites_paie: {
      ...existingSpec,
      prelevement_a_la_source: values.specificites_paie.prelevement_a_la_source,
      transport: values.specificites_paie.transport,
      titres_restaurant: values.specificites_paie.titres_restaurant,
      mutuelle: {
        ...(existingSpec.mutuelle as object),
        adhesion: mutuelleIds.length > 0,
        mutuelle_type_ids: mutuelleIds,
      },
      prevoyance: {
        ...(existingSpec.prevoyance as object),
        adhesion: values.specificites_paie.prevoyance.adhesion,
        lignes_specifiques: values.specificites_paie.prevoyance.adhesion
          ? values.specificites_paie.prevoyance.lignes_specifiques ?? []
          : [],
      },
      maintien_regime_apprenti: Boolean(values.specificites_paie.maintien_regime_apprenti),
      personnel_rd_eligible_jei: Boolean(values.specificites_paie.personnel_rd_eligible_jei),
    },
  };

  const dep = values.specificites_paie.deplacement_astreinte;
  if (dep?.enabled) {
    payload.specificites_paie = {
      ...payload.specificites_paie,
      deplacement_astreinte: {
        enabled: true,
        distance_km_one_way: dep.distance_km_one_way,
        vehicle_cv: dep.vehicle_cv,
        vehicle_type: dep.vehicle_type ?? 'voitures',
      },
    };
  } else if (dep) {
    payload.specificites_paie = {
      ...payload.specificites_paie,
      deplacement_astreinte: { enabled: false },
    };
  }

  if (values.collective_agreement_id) {
    payload.classification_conventionnelle = values.classification_conventionnelle;
  }

  return payload;
}
