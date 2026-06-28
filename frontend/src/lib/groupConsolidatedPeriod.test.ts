import { describe, expect, it } from "vitest";

import { parsePeriodFromSearchParams } from "@/lib/groupConsolidatedPeriod";

describe("groupConsolidatedPeriod", () => {
  it("démarre sur le mois précédent sans période explicite", () => {
    const parsed = parsePeriodFromSearchParams(
      new URLSearchParams(),
      new Date("2026-06-28T12:00:00"),
    );

    expect(parsed.period.preset).toBe("previous_month");
    expect(parsed.period.year).toBe(2026);
    expect(parsed.period.month).toBe(5);
  });

  it("respecte le mois courant quand il est explicite dans l'URL", () => {
    const parsed = parsePeriodFromSearchParams(
      new URLSearchParams("preset=current_month&year=2026&month=6"),
      new Date("2026-06-28T12:00:00"),
    );

    expect(parsed.period.preset).toBe("current_month");
    expect(parsed.period.year).toBe(2026);
    expect(parsed.period.month).toBe(6);
  });
});
