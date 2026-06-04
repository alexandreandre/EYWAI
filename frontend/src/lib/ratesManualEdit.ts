/**
 * Utilitaires purs pour la saisie manuelle des taux (admin).
 *
 * Aplatit un bloc `config_data` (objets/tableaux imbriqués) en feuilles scalaires
 * éditables (nombre / texte / booléen), et permet de reconstruire l'objet en
 * appliquant des valeurs modifiées par chemin.
 */

export type RateLeafType = 'number' | 'string' | 'boolean';

export type RateLeaf = {
  /** Chemin d'accès (clés d'objet / index de tableau). */
  path: (string | number)[];
  /** Identifiant stable du chemin (sérialisé) — clé React et map d'édition. */
  pathKey: string;
  /** Libellé lisible (chemin formaté). */
  label: string;
  value: number | string | boolean;
  type: RateLeafType;
};

function isScalar(v: unknown): v is number | string | boolean {
  return ['number', 'string', 'boolean'].includes(typeof v);
}

function serializePath(path: (string | number)[]): string {
  return path.map((p) => (typeof p === 'number' ? `[${p}]` : String(p))).join('.');
}

function labelPath(path: (string | number)[]): string {
  return path
    .map((p) => (typeof p === 'number' ? `#${p + 1}` : String(p)))
    .join(' › ');
}

/**
 * Parcourt récursivement `data` et renvoie la liste des feuilles scalaires.
 * Les valeurs `null`/`undefined` sont ignorées (pas de type éditable fiable).
 */
export function flattenScalarLeaves(data: unknown): RateLeaf[] {
  const leaves: RateLeaf[] = [];

  const walk = (node: unknown, path: (string | number)[]) => {
    if (Array.isArray(node)) {
      node.forEach((item, idx) => walk(item, [...path, idx]));
      return;
    }
    if (node && typeof node === 'object') {
      for (const [key, val] of Object.entries(node as Record<string, unknown>)) {
        walk(val, [...path, key]);
      }
      return;
    }
    if (isScalar(node) && path.length > 0) {
      leaves.push({
        path,
        pathKey: serializePath(path),
        label: labelPath(path),
        value: node,
        type: typeof node as RateLeafType,
      });
    }
  };

  walk(data, []);
  return leaves;
}

/** Clone profond + écriture d'une valeur au chemin donné (immutable). */
export function setByPath(
  root: Record<string, unknown>,
  path: (string | number)[],
  value: unknown,
): Record<string, unknown> {
  const clone = structuredClone(root);
  let cursor: Record<PropertyKey, unknown> = clone as Record<PropertyKey, unknown>;
  for (let i = 0; i < path.length - 1; i += 1) {
    const next = cursor[path[i]];
    if (next == null || typeof next !== 'object') {
      // Chemin inattendu — on abandonne silencieusement la modification.
      return clone;
    }
    cursor = next as Record<PropertyKey, unknown>;
  }
  cursor[path[path.length - 1]] = value;
  return clone;
}

/** Normalise une saisie numérique FR/EN ("11,88" → 11.88). Renvoie null si invalide. */
export function parseNumericInput(raw: string): number | null {
  const normalized = raw.trim().replace(/\s/g, '').replace(',', '.');
  if (normalized === '') return null;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}
