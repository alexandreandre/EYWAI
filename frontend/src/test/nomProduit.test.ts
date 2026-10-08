import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

/**
 * Garde : le produit visible s'appelle Martine, pas EYWAI.
 * Lit les textes (chaînes, gabarits, texte JSX, JSON, index.html) et ignore
 * les commentaires, les identifiants et les chemins d'import.
 */
const SRC = path.resolve(__dirname, "..");
const INDEX_HTML = path.resolve(SRC, "..", "index.html");

// Chaînes techniques exactes autorisées (clés de stockage, valeurs internes).
const LISTE_BLANCHE = new Set<string>(["__eywai__"]);
const MOTIFS_TECHNIQUES = [/^eywai-/i, /^EYWAI_/];

function fichiers(dir: string): string[] {
  const out: string[] = [];
  for (const nom of readdirSync(dir)) {
    const p = path.join(dir, nom);
    if (statSync(p).isDirectory()) out.push(...fichiers(p));
    else if (/\.(ts|tsx|json)$/.test(nom) && !/\.test\.(ts|tsx)$/.test(nom)) out.push(p);
  }
  return out;
}

function autorise(s: string): boolean {
  if (LISTE_BLANCHE.has(s)) return true;
  return MOTIFS_TECHNIQUES.some((m) => m.test(s)) && !/Martine/.test(s) && s.replace(/eywai[-\w]*/gi, "").trim() === "";
}

function textesTs(fichier: string): string[] {
  const src = readFileSync(fichier, "utf8");
  const sf = ts.createSourceFile(fichier, src, ts.ScriptTarget.Latest, true, fichier.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const out: string[] = [];
  const visite = (n: ts.Node) => {
    if (ts.isImportDeclaration(n) || ts.isExportDeclaration(n)) return;
    if (ts.isCallExpression(n) && n.expression.kind === ts.SyntaxKind.ImportKeyword) return;
    if (ts.isLiteralTypeNode(n)) return;
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) out.push(n.text);
    else if (ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)) out.push(n.text);
    else if (ts.isJsxText(n)) out.push(n.text);
    ts.forEachChild(n, visite);
  };
  visite(sf);
  return out;
}

function chainesJson(v: unknown, out: string[] = []): string[] {
  if (typeof v === "string") out.push(v);
  else if (Array.isArray(v)) v.forEach((x) => chainesJson(x, out));
  else if (v && typeof v === "object") {
    for (const [k, x] of Object.entries(v)) {
      out.push(k);
      chainesJson(x, out);
    }
  }
  return out;
}

describe("nom du produit", () => {
  it("le produit visible s'appelle Martine", () => {
    const fautes: string[] = [];
    for (const f of fichiers(SRC)) {
      const textes = f.endsWith(".json") ? chainesJson(JSON.parse(readFileSync(f, "utf8"))) : textesTs(f);
      for (const t of textes) {
        if (t.includes("EYWAI") && !autorise(t)) fautes.push(`${path.relative(SRC, f)} : ${t.trim().slice(0, 80)}`);
      }
    }
    const html = readFileSync(INDEX_HTML, "utf8").replace(/<!--[\s\S]*?-->/g, "");
    if (html.includes("EYWAI")) fautes.push("index.html");
    expect(fautes, `${fautes.length} textes citent encore EYWAI`).toEqual([]);
  });
});
