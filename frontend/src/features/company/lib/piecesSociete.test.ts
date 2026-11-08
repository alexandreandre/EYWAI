import { describe, expect, it } from "vitest";
import { resumePieces } from "./piecesSociete";

describe("resumePieces", () => {
  it("dit quand tout est déposé", () => {
    expect(resumePieces(0)).toBe("Toutes les pièces attendues sont déposées.");
  });
  it("accorde au singulier", () => {
    expect(resumePieces(1)).toBe("1 pièce attendue n'est pas encore déposée.");
  });
  it("accorde au pluriel", () => {
    expect(resumePieces(4)).toBe("4 pièces attendues ne sont pas encore déposées.");
  });
});
