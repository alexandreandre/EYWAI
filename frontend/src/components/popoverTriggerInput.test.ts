import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function fichiers(dir: string): string[] {
  return readdirSync(dir).flatMap((nom) => {
    const chemin = join(dir, nom);
    if (statSync(chemin).isDirectory()) return fichiers(chemin);
    return chemin.endsWith(".tsx") ? [chemin] : [];
  });
}

describe("PopoverTrigger asChild", () => {
  it("n'enveloppe jamais un champ de saisie (Radix lui impose type=button : on ne peut plus y taper)", () => {
    const fautifs = fichiers(join(__dirname, "..")).filter((f) =>
      /<PopoverTrigger\s+asChild>\s*<(Input|input|Textarea|textarea)\b/.test(readFileSync(f, "utf8")),
    );
    expect(fautifs).toEqual([]);
  });
});
