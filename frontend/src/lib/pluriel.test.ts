import { describe, expect, it } from "vitest";
import { accord, pluriel } from "@/lib/pluriel";

describe("pluriel", () => {
  it("accorde le mot au nombre : singulier à 0 et 1, pluriel dès 2", () => {
    expect(pluriel(0, "jour")).toBe("0 jour");
    expect(pluriel(1, "jour")).toBe("1 jour");
    expect(pluriel(2, "jour")).toBe("2 jours");
    expect(pluriel(1.5, "jour")).toBe("1,5 jour");
    expect(pluriel(3, "écart effectif", "écarts effectifs")).toBe("3 écarts effectifs");
  });

  it("n'écrit que le mot pour accorder un adjectif ou un participe", () => {
    expect(accord(1, "conservé")).toBe("conservé");
    expect(accord(4, "conservé")).toBe("conservés");
    expect(accord(2, "mis à jour", "mis à jour")).toBe("mis à jour");
  });
});
