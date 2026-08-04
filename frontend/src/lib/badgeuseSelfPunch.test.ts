import { describe, expect, it } from "vitest";
import {
  resolveSelfPunchState,
  shouldShowSelfPunchButton,
} from "@/lib/badgeuseSelfPunch";

describe("resolveSelfPunchState", () => {
  it("propose une entrée quand la journée n'a pas commencé", () => {
    const state = resolveSelfPunchState("ENTREE", []);
    expect(state.isEntry).toBe(true);
    expect(state.label).toBe("Je pointe mon entrée");
    expect(state.lastPunchLabel).toBeNull();
  });

  it("propose une sortie quand le salarié est en présence", () => {
    const state = resolveSelfPunchState("SORTIE", [
      { timestamp: "2026-08-04T06:48:00", event_type: "ENTREE" },
    ]);
    expect(state.isEntry).toBe(false);
    expect(state.label).toBe("Je pointe ma sortie");
  });

  it("affiche l'heure du dernier pointage, pas du premier", () => {
    const state = resolveSelfPunchState("ENTREE", [
      { timestamp: "2026-08-04T06:48:00", event_type: "ENTREE" },
      { timestamp: "2026-08-04T12:00:00", event_type: "SORTIE" },
    ]);
    expect(state.lastPunchLabel).toBe("12:00");
  });

  it("suppose une entrée quand le serveur ne dit rien", () => {
    expect(resolveSelfPunchState(undefined, undefined).isEntry).toBe(true);
    expect(resolveSelfPunchState(undefined, undefined).lastPunchLabel).toBeNull();
  });
});

describe("shouldShowSelfPunchButton", () => {
  const base = { isToday: true, allowSelfToggle: true, isEligible: true };

  it("s'affiche sur la journée du jour pour un salarié éligible", () => {
    expect(shouldShowSelfPunchButton(base)).toBe(true);
  });

  it("reste masqué sur une date passée", () => {
    expect(shouldShowSelfPunchButton({ ...base, isToday: false })).toBe(false);
  });

  it("reste masqué si la société impose le scan à l'accueil", () => {
    expect(shouldShowSelfPunchButton({ ...base, allowSelfToggle: false })).toBe(
      false
    );
  });

  it("s'affiche quand le réglage est absent : autorisé par défaut", () => {
    expect(
      shouldShowSelfPunchButton({ ...base, allowSelfToggle: undefined })
    ).toBe(true);
  });

  it("reste masqué pour un salarié non éligible, par exemple au forfait jours", () => {
    expect(shouldShowSelfPunchButton({ ...base, isEligible: false })).toBe(
      false
    );
  });
});
