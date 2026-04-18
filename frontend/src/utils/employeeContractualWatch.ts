/**
 * Détection des changements contractuels (salaire, poste, temps de travail, lieu)
 * pour proposer un avenant après sauvegarde — ne bloque jamais la sauvegarde.
 */

export type WatchedKey = 'salaire_de_base' | 'job_title' | 'duree_hebdomadaire' | 'lieu_travail';

export const WATCHED_FIELD_LABELS: Record<WatchedKey, string> = {
  salaire_de_base: 'Salaire de base',
  job_title: 'Poste / intitulé',
  duree_hebdomadaire: 'Durée hebdomadaire',
  lieu_travail: 'Lieu de travail',
};

export const AVENANT_TYPE_BY_FIELD: Record<WatchedKey, string> = {
  salaire_de_base: 'avenant_salaire',
  job_title: 'avenant_poste',
  duree_hebdomadaire: 'avenant_temps',
  lieu_travail: 'avenant_lieu',
};

export type ContractualFieldDiff = {
  key: WatchedKey;
  label: string;
  before: string;
  after: string;
};

function _serializeSalaire(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'object' && v !== null && 'valeur' in (v as object)) {
    return String((v as { valeur?: unknown }).valeur ?? '');
  }
  if (typeof v === 'object' && v !== null && 'amount' in (v as object)) {
    return String((v as { amount?: unknown }).amount ?? '');
  }
  return JSON.stringify(v);
}

function _serializeLieu(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'object' && v !== null) {
    const o = v as Record<string, unknown>;
    return String(o.libelle ?? o.label ?? o.name ?? JSON.stringify(v));
  }
  return String(v);
}

/** Extrait une vue comparable des champs surveillés depuis l’objet employé API. */
export function extractWatchedSnapshot(emp: Record<string, unknown> | null | undefined): Record<WatchedKey, string> {
  if (!emp) {
    return {
      salaire_de_base: '',
      job_title: '',
      duree_hebdomadaire: '',
      lieu_travail: '',
    };
  }
  const salaire = emp.salaire_de_base ?? (emp as { remuneration?: { salaire_de_base?: unknown } }).remuneration?.salaire_de_base;
  const job = emp.job_title ?? emp.poste ?? '';
  const duree = emp.duree_hebdomadaire ?? emp.weekly_hours ?? '';
  const lieu = emp.lieu_travail ?? emp.workplace ?? '';
  return {
    salaire_de_base: _serializeSalaire(salaire),
    job_title: String(job ?? '').trim(),
    duree_hebdomadaire: String(duree ?? '').trim(),
    lieu_travail: _serializeLieu(lieu),
  };
}

export function diffWatchedSnapshots(
  initial: Record<WatchedKey, string>,
  current: Record<WatchedKey, string>
): ContractualFieldDiff[] {
  const keys: WatchedKey[] = ['salaire_de_base', 'job_title', 'duree_hebdomadaire', 'lieu_travail'];
  const out: ContractualFieldDiff[] = [];
  for (const key of keys) {
    const before = initial[key] ?? '';
    const after = current[key] ?? '';
    if (before !== after) {
      out.push({
        key,
        label: WATCHED_FIELD_LABELS[key],
        before: before || '—',
        after: after || '—',
      });
    }
  }
  return out;
}

export function resolveAvenantTypeFromDiffs(diffs: ContractualFieldDiff[]): string {
  if (diffs.length === 0) return 'avenant_general';
  if (diffs.length > 1) return 'avenant_general';
  return AVENANT_TYPE_BY_FIELD[diffs[0].key];
}
