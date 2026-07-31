import { describe, expect, it } from "vitest";

import { parseContentDispositionFilename } from "./downloadBlob";

describe("parseContentDispositionFilename", () => {
  it("lit un nom entre guillemets", () => {
    expect(
      parseContentDispositionFilename(
        'attachment; filename="titres-de-sejour_mbc_2026-07-31.xlsx"',
        "repli.xlsx",
      ),
    ).toBe("titres-de-sejour_mbc_2026-07-31.xlsx");
  });

  it("lit un nom sans guillemets", () => {
    expect(
      parseContentDispositionFilename("attachment; filename=export.xlsx", "repli.xlsx"),
    ).toBe("export.xlsx");
  });

  it("décode la forme UTF-8 encodée", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename*=UTF-8''titres-de-s%C3%A9jour.xlsx",
        "repli.xlsx",
      ),
    ).toBe("titres-de-séjour.xlsx");
  });

  it("rend le repli quand l'en-tête est absent", () => {
    expect(parseContentDispositionFilename(undefined, "repli.xlsx")).toBe("repli.xlsx");
  });

  it("rend le repli quand l'en-tête ne porte pas de nom", () => {
    expect(parseContentDispositionFilename("attachment", "repli.xlsx")).toBe("repli.xlsx");
  });
});
