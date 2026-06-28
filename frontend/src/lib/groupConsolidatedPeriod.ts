export type PeriodMode = "month" | "year" | "range";
export type PeriodPreset =
  | "current_month"
  | "previous_month"
  | "ytd"
  | "last_12_months"
  | "previous_year"
  | "custom";

export interface PeriodState {
  mode: PeriodMode;
  year: number;
  month: number;
  startYear: number;
  startMonth: number;
  endYear: number;
  endMonth: number;
  preset: PeriodPreset;
}

export function formatMonthLabel(month: number): string {
  const months = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
  ];
  return months[month - 1] ?? String(month);
}

export function getPeriodBounds(state: PeriodState): {
  startYear: number;
  startMonth: number;
  endYear: number;
  endMonth: number;
  label: string;
} {
  const { mode, year, month, startYear, startMonth, endYear, endMonth } = state;
  if (mode === "month") {
    return {
      startYear: year,
      startMonth: month,
      endYear: year,
      endMonth: month,
      label: `${formatMonthLabel(month)} ${year}`,
    };
  }
  if (mode === "year") {
    return {
      startYear: year,
      startMonth: 1,
      endYear: year,
      endMonth: 12,
      label: `Année ${year}`,
    };
  }
  return {
    startYear,
    startMonth,
    endYear,
    endMonth,
    label: `${formatMonthLabel(startMonth)} ${startYear} – ${formatMonthLabel(endMonth)} ${endYear}`,
  };
}

export function applyPreset(preset: PeriodPreset, now = new Date()): PeriodState {
  const y = now.getFullYear();
  const m = now.getMonth() + 1;

  switch (preset) {
    case "current_month":
      return {
        mode: "month",
        year: y,
        month: m,
        startYear: y,
        startMonth: m,
        endYear: y,
        endMonth: m,
        preset,
      };
    case "previous_month": {
      let pm = m - 1;
      let py = y;
      if (pm < 1) {
        pm = 12;
        py -= 1;
      }
      return {
        mode: "month",
        year: py,
        month: pm,
        startYear: py,
        startMonth: pm,
        endYear: py,
        endMonth: pm,
        preset,
      };
    }
    case "ytd":
      return {
        mode: "year",
        year: y,
        month: m,
        startYear: y,
        startMonth: 1,
        endYear: y,
        endMonth: m,
        preset,
      };
    case "last_12_months": {
      let sy = y;
      let sm = m - 11;
      while (sm < 1) {
        sm += 12;
        sy -= 1;
      }
      return {
        mode: "range",
        year: y,
        month: m,
        startYear: sy,
        startMonth: sm,
        endYear: y,
        endMonth: m,
        preset,
      };
    }
    case "previous_year":
      return {
        mode: "year",
        year: y - 1,
        month: m,
        startYear: y - 1,
        startMonth: 1,
        endYear: y - 1,
        endMonth: 12,
        preset,
      };
    default:
      return {
        mode: "month",
        year: y,
        month: m,
        startYear: y,
        startMonth: m,
        endYear: y,
        endMonth: m,
        preset: "custom",
      };
  }
}

export function buildYearOptions(count = 10, now = new Date()): number[] {
  const current = now.getFullYear();
  return Array.from({ length: count }, (_, i) => current - i);
}

export function parsePeriodFromSearchParams(
  params: URLSearchParams,
  now = new Date(),
): {
  period: PeriodState;
  compareTo: import("@/api/companyGroups").CompareToMode;
  selectedCompanyIds: string[] | null;
  searchTerm: string;
} {
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const hasExplicitPeriod =
    params.has("mode") ||
    params.has("preset") ||
    params.has("year") ||
    params.has("month") ||
    params.has("startYear") ||
    params.has("startMonth") ||
    params.has("endYear") ||
    params.has("endMonth");
  if (!hasExplicitPeriod) {
    return {
      period: applyPreset("previous_month", now),
      compareTo: "off",
      selectedCompanyIds: null,
      searchTerm: params.get("q") ?? "",
    };
  }

  const mode = (params.get("mode") as PeriodMode) || "month";
  const preset = (params.get("preset") as PeriodPreset) || "current_month";
  const compareRaw = params.get("compare") as import("@/api/companyGroups").CompareToMode | null;
  const compareTo =
    compareRaw === "previous_month" ||
    compareRaw === "previous_year" ||
    compareRaw === "ytd_previous_year"
      ? compareRaw
      : "off";
  const companies = params.get("companies");
  const selectedCompanyIds = companies ? companies.split(",").filter(Boolean) : null;

  return {
    period: {
      mode: mode === "year" || mode === "range" ? mode : "month",
      year: Number(params.get("year")) || y,
      month: Number(params.get("month")) || m,
      startYear: Number(params.get("startYear")) || y,
      startMonth: Number(params.get("startMonth")) || m,
      endYear: Number(params.get("endYear")) || y,
      endMonth: Number(params.get("endMonth")) || m,
      preset,
    },
    compareTo,
    selectedCompanyIds,
    searchTerm: params.get("q") ?? "",
  };
}

export function periodToSearchParams(
  period: PeriodState,
  compareTo: import("@/api/companyGroups").CompareToMode,
  selectedCompanyIds: Set<string>,
  searchTerm: string,
): URLSearchParams {
  const p = new URLSearchParams();
  p.set("mode", period.mode);
  p.set("preset", period.preset);
  p.set("year", String(period.year));
  p.set("month", String(period.month));
  p.set("startYear", String(period.startYear));
  p.set("startMonth", String(period.startMonth));
  p.set("endYear", String(period.endYear));
  p.set("endMonth", String(period.endMonth));
  if (compareTo !== "off") p.set("compare", compareTo);
  if (selectedCompanyIds.size > 0) {
    p.set("companies", Array.from(selectedCompanyIds).join(","));
  }
  if (searchTerm.trim()) p.set("q", searchTerm.trim());
  return p;
}
