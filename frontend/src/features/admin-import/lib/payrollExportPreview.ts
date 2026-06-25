export type PayrollExportPreviewField = {
  key: string;
  label: string;
  source_header?: string | null;
};

function paymentLabel(method: unknown): string {
  const m = String(method ?? '').toLowerCase();
  if (m === 'cheque') return 'Chèque';
  if (m === 'especes') return 'Espèces';
  if (m === 'virement') return 'Virement';
  return '—';
}

export function formatPayrollPreviewCell(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';

  if (key === 'payment_method') return paymentLabel(value);

  if (key === 'duree_hebdomadaire') {
    const n = Number(value);
    return Number.isFinite(n) ? `${n} h/sem` : String(value);
  }

  if (key === 'base_salary') {
    const n = Number(value);
    return Number.isFinite(n) ? `${n.toLocaleString('fr-FR')} €` : String(value);
  }

  if (key === 'activity_pct') {
    const n = Number(value);
    return Number.isFinite(n) ? `${n} %` : String(value);
  }

  if (typeof value === 'boolean') return value ? 'Oui' : 'Non';

  return String(value);
}

export function buildPayrollPreviewFieldsFromRows(
  columnMapping: Record<string, string>,
  rows: Array<{ preview_columns?: Record<string, unknown> }>,
): PayrollExportPreviewField[] {
  const specs: Array<[string, string, string]> = [
    ['identifiant', 'Matricule', 'identifiant'],
    ['last_name', 'Nom', 'last_name'],
    ['first_name', 'Prénom', 'first_name'],
    ['nom_usage', 'Nom marital', 'nom_usage'],
    ['nir', 'NIR', 'nir'],
    ['email', 'E-mail', 'email'],
    ['phone', 'Tél.', 'phone'],
    ['sexe', 'Sexe', 'sexe'],
    ['nationality', 'Nationalité', 'nationality'],
    ['birth_date', 'Date naissance', 'birth_date'],
    ['birth_dept', 'Dept naissance', 'birth_dept'],
    ['birth_city', 'Commune naissance', 'birth_city'],
    ['street_num', 'N° voie', 'street_num'],
    ['btq', 'BTQ', 'btq'],
    ['street', 'Voie', 'street'],
    ['address_extra', 'Complément', 'address_extra'],
    ['postal_code', 'CP', 'postal_code'],
    ['city', 'Ville', 'city'],
    ['hire_date', 'Date entrée', 'hire_date'],
    ['exit_date', 'Date sortie', 'exit_date'],
    ['cdd', 'CDD (fichier)', 'cdd'],
    ['contract_type', 'Contrat', 'cdd'],
    ['statut', 'Statut cadre', 'statut_cadre'],
    ['base_salary', 'Salaire base', 'base_salary'],
    ['activity_pct', '% activité', 'activity_pct'],
    ['monthly_hours', 'Heures/mois', 'monthly_hours'],
    ['is_temps_partiel', 'Temps partiel', 'activity_pct'],
    ['duree_hebdomadaire', 'Heures/sem', 'activity_pct'],
    ['payment_method', 'Paiement', 'payment_method'],
    ['iban_masked', 'RIB/IBAN', 'rib'],
    ['service', 'Service', 'service'],
    ['team_name', 'Équipe', 'service'],
    ['handicap', 'Handicapé', 'handicap'],
    ['prior_service_days', 'Jours anc.', 'prior_service_days'],
    ['residence_permit_number', 'N° carte séjour', 'residence_permit_number'],
    ['residence_permit_from', 'Carte obt.', 'residence_permit_from'],
    ['residence_permit_to', 'Carte expir.', 'residence_permit_to'],
  ];

  const seen = new Set<string>();
  const fields: PayrollExportPreviewField[] = [];

  for (const [key, label, mapKey] of specs) {
    if (seen.has(key)) continue;
    const mapped = mapKey in columnMapping;
    const hasData = rows.some((row) => {
      const value = row.preview_columns?.[key];
      return value !== null && value !== undefined && value !== '';
    });
    if (!mapped && !hasData) continue;
    seen.add(key);
    fields.push({
      key,
      label,
      source_header: mapped ? columnMapping[mapKey] : null,
    });
  }

  return fields;
}
