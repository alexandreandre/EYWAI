/**
 * Primes saisies éditées depuis le bulletin (spec 2026-09-23).
 *
 * Une prime ajoutée, corrigée ou retirée sur le bulletin devient une variable
 * du mois et le serveur fait recalculer tout le bulletin. Seules comptent les
 * lignes qui portent `saisie_id` (imprimées depuis une saisie) ou
 * `nouvelle_saisie` (ajoutées ici) — même règle que
 * `backend/app/modules/payslips/domain/primes_editees.py`, avec laquelle
 * cette fonction doit rester d'accord.
 */
import type { MonthlyInputCreate } from '@/api/saisies';

const SECTIONS = ['calcul_du_brut', 'primes_non_soumises'] as const;

export interface NouvelleSaisie {
  name: string;
  amount: number;
  is_socially_taxed: boolean;
  is_taxable: boolean;
  catalog_prime_id: string | null;
}

export interface LignePrime {
  libelle: string;
  quantite: null;
  taux: null;
  gain: number;
  perte: null;
  is_sous_total: false;
  nouvelle_saisie: NouvelleSaisie;
}

export function ligneDepuisSaisie(saisie: MonthlyInputCreate): LignePrime {
  const montant = Number(saisie.amount) || 0;
  return {
    libelle: saisie.name,
    quantite: null,
    taux: null,
    gain: montant,
    perte: null,
    is_sous_total: false,
    nouvelle_saisie: {
      name: saisie.name,
      amount: montant,
      is_socially_taxed: saisie.is_socially_taxed ?? true,
      is_taxable: saisie.is_taxable ?? true,
      catalog_prime_id: saisie.catalog_prime_id ?? null,
    },
  };
}

type Ligne = Record<string, unknown>;

function lignes(data: unknown): Ligne[] {
  const d = (data ?? {}) as Record<string, unknown>;
  return SECTIONS.flatMap((s) => (Array.isArray(d[s]) ? (d[s] as Ligne[]) : [])).filter(
    (l) => l && typeof l === 'object' && !l.is_sous_total
  );
}

function montant(l: Ligne): number {
  const v = typeof l.gain === 'number' ? l.gain : l.montant;
  return typeof v === 'number' ? Math.round(v * 100) / 100 : 0;
}

function parSaisie(data: unknown): Map<string, number> {
  return new Map(
    lignes(data)
      .filter((l) => l.saisie_id)
      .map((l) => [String(l.saisie_id), montant(l)])
  );
}

export function primesEditees(avant: unknown, apres: unknown): boolean {
  if (lignes(apres).some((l) => l.nouvelle_saisie && typeof l.nouvelle_saisie === 'object')) return true;
  const a = parSaisie(avant);
  const b = parSaisie(apres);
  for (const [id, m] of a) {
    if (!b.has(id) || Math.abs((b.get(id) ?? 0) - m) > 0.005) return true;
  }
  return false;
}
