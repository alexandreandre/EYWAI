import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Garde : le produit s'appelle Martine, nulle part l'ancien nom.
 * Lit le texte brut (code, commentaires, JSON, index.html, e2e) : aucune
 * liste blanche côté front.
 */
const FRONT = path.resolve(__dirname, "..", "..");
const ANCIEN = "EY" + "WAI";
const ANCIEN_MIN = ANCIEN.toLowerCase();

function fichiers(dir: string): string[] {
  const out: string[] = [];
  for (const nom of readdirSync(dir)) {
    const p = path.join(dir, nom);
    if (statSync(p).isDirectory()) out.push(...fichiers(p));
    else if (/\.(ts|tsx|json|html|md)$/.test(nom) && !p.endsWith("nomProduit.test.ts")) out.push(p);
  }
  return out;
}

describe("nom du produit", () => {
  it("aucun texte du front ne cite l'ancien nom", () => {
    const fautes: string[] = [];
    const cibles = [
      ...fichiers(path.join(FRONT, "src")),
      ...fichiers(path.join(FRONT, "e2e")),
      path.join(FRONT, "index.html"),
    ];
    for (const f of cibles) {
      readFileSync(f, "utf8")
        .split("\n")
        .forEach((ligne, i) => {
          if (ligne.includes(ANCIEN) || ligne.includes(`__${ANCIEN_MIN}__`) || ligne.includes(`${ANCIEN_MIN}-`)) {
            fautes.push(`${path.relative(FRONT, f)}:${i + 1}: ${ligne.trim().slice(0, 80)}`);
          }
        });
    }
    expect(fautes, `${fautes.length} lignes citent encore l'ancien nom`).toEqual([]);
  });
});
