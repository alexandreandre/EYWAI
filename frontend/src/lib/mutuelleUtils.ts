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

/** Cadre / assimilé cadre (ex. « Cadre au forfait jour »), aligné sur la logique backend. */
export function isEmployeeCadre(statut?: string | null): boolean {
  const compact = (statut ?? '').trim().toLowerCase().replace(/\s+/g, '').replace(/-/g, '');
  return compact.includes('cadre') && !compact.includes('noncadre');
}

export function normalizeEmployeeStatut(statut?: string | null): 'cadre' | 'non_cadre' {
  return isEmployeeCadre(statut) ? 'cadre' : 'non_cadre';
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

export function formatMutuelleOptionLabel(m: MutuelleType): string {
  const parts = [m.libelle];
  if (m.pack_couverture && PACK_COUVERTURE_LABELS[m.pack_couverture]) {
    parts.push(`· ${PACK_COUVERTURE_LABELS[m.pack_couverture]}`);
  }
  if (m.statut_categoriel && m.statut_categoriel !== 'tous') {
    parts.push(`· ${STATUT_CATEGORIEL_LABELS[m.statut_categoriel]}`);
  }
  return parts.join(' ');
}
