import type { MutuelleType } from '@/api/mutuelleTypes';

export const PACK_COUVERTURE_LABELS: Record<string, string> = {
  isole: 'Isolé (salarié seul)',
  famille: 'Famille',
  duo: 'Duo (couple)',
  autre: 'Autre',
};

export const STATUT_CATEGORIEL_LABELS: Record<string, string> = {
  cadre: 'Cadre',
  non_cadre: 'Non-cadre',
  tous: 'Tous statuts',
};

const PACK_SORT_ORDER: Record<string, number> = {
  isole: 0,
  duo: 1,
  famille: 2,
  autre: 3,
};

/** Cadre / assimilé cadre (ex. « Cadre au forfait jour »), aligné sur la logique backend. */
export function isEmployeeCadre(statut?: string | null): boolean {
  const compact = (statut ?? '').trim().toLowerCase().replace(/\s+/g, '').replace(/-/g, '');
  return compact.includes('cadre') && !compact.includes('noncadre');
}

export function normalizeEmployeeStatut(statut?: string | null): 'cadre' | 'non_cadre' {
  return isEmployeeCadre(statut) ? 'cadre' : 'non_cadre';
}

/** Retire les montants redondants des libellés importés DSN (ex. « Mutuelle (Cadre) 60.02€ / 0.00€ »). */
export function cleanMutuelleLibelle(libelle: string): string {
  return libelle
    .replace(/\s*\d+[.,]\d{2}\s*€\s*\/\s*\d+[.,]\d{2}\s*€/g, '')
    .replace(/^Mutuelle\s*/i, '')
    .replace(/\(\s*\)/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function resolveOrganismeLabel(
  mutuelle: Pick<MutuelleType, 'organisme_label'>,
  companyOrganismeLabel?: string | null,
): string | null {
  const formula = mutuelle.organisme_label?.trim();
  if (formula) return formula;
  const company = companyOrganismeLabel?.trim();
  return company || null;
}

/** Filtre les formules mutuelle applicables à un salarié (statut + pack optionnel). */
export function filterMutuellesForEmployee(
  mutuelles: MutuelleType[],
  statut?: string | null,
  packCouverture?: string | null,
): MutuelleType[] {
  const statutNorm = normalizeEmployeeStatut(statut);
  return mutuelles.filter((m) => {
    if (!m.is_active) return false;
    const cat = m.statut_categoriel ?? 'tous';
    if (cat !== 'tous' && cat !== statutNorm) return false;
    if (packCouverture && m.pack_couverture && m.pack_couverture !== packCouverture) {
      return false;
    }
    return true;
  });
}

export function sortMutuellesForSelection(mutuelles: MutuelleType[]): MutuelleType[] {
  return [...mutuelles].sort((a, b) => {
    const packA = PACK_SORT_ORDER[a.pack_couverture ?? ''] ?? 4;
    const packB = PACK_SORT_ORDER[b.pack_couverture ?? ''] ?? 4;
    if (packA !== packB) return packA - packB;
    if (a.montant_salarial !== b.montant_salarial) {
      return a.montant_salarial - b.montant_salarial;
    }
    return cleanMutuelleLibelle(a.libelle).localeCompare(cleanMutuelleLibelle(b.libelle), 'fr');
  });
}

export function formatMutuelleOptionLabel(m: MutuelleType): string {
  const cleaned = cleanMutuelleLibelle(m.libelle);
  const parts: string[] = [];
  if (cleaned) {
    parts.push(cleaned);
  } else if (m.pack_couverture && PACK_COUVERTURE_LABELS[m.pack_couverture]) {
    parts.push(PACK_COUVERTURE_LABELS[m.pack_couverture]);
  } else {
    parts.push('Formule mutuelle');
  }
  if (m.pack_couverture && PACK_COUVERTURE_LABELS[m.pack_couverture] && !cleaned) {
    parts.push(PACK_COUVERTURE_LABELS[m.pack_couverture]);
  }
  if (m.statut_categoriel && m.statut_categoriel !== 'tous') {
    parts.push(STATUT_CATEGORIEL_LABELS[m.statut_categoriel]);
  }
  return parts.join(' · ');
}

export function formatMutuelleAmountsLine(m: Pick<MutuelleType, 'montant_salarial' | 'montant_patronal'>): string {
  return `Salarial ${m.montant_salarial.toFixed(2)} € · Patronal ${m.montant_patronal.toFixed(2)} €`;
}

export function formatMutuelleOptionTitle(
  m: MutuelleType,
  companyOrganismeLabel?: string | null,
): string {
  const organisme = resolveOrganismeLabel(m, companyOrganismeLabel);
  const label = formatMutuelleOptionLabel(m);
  return organisme ? `${organisme} — ${label}` : label;
}

export function listMutuellePackFilters(
  mutuelles: MutuelleType[],
): Array<{ id: string; label: string }> {
  const packs = new Set(mutuelles.map((m) => m.pack_couverture).filter(Boolean) as string[]);
  const filters = [{ id: 'all', label: 'Toutes' }];
  for (const pack of ['isole', 'duo', 'famille', 'autre'] as const) {
    if (packs.has(pack)) {
      filters.push({ id: pack, label: PACK_COUVERTURE_LABELS[pack] });
    }
  }
  return filters;
}
