import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  buildPeriodBounds,
  defaultPeriodSelection,
  type PeriodSelection,
} from "@/lib/analyticsPeriod";

export function useCompanyPeriod(): {
  period: PeriodSelection;
  setPeriod: (next: PeriodSelection) => void;
  periodBounds: ReturnType<typeof buildPeriodBounds>;
} {
  const [searchParams, setSearchParams] = useSearchParams();

  const period = useMemo((): PeriodSelection => {
    const g = searchParams.get("granularity");
    const year = Number(searchParams.get("year"));
    const month = Number(searchParams.get("month"));
    const def = defaultPeriodSelection();
    if (g === "monthly" && year >= 2000 && month >= 1 && month <= 12) {
      return { granularity: "monthly", year, month, week: def.week };
    }
    if (g === "annual" && year >= 2000) {
      return { granularity: "annual", year, month: def.month, week: def.week };
    }
    return def;
  }, [searchParams]);

  const setPeriod = useCallback(
    (next: PeriodSelection) => {
      const params = new URLSearchParams(searchParams);
      params.set("granularity", next.granularity);
      params.set("year", String(next.year));
      if (next.granularity === "monthly") {
        params.set("month", String(next.month));
      } else {
        params.delete("month");
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const periodBounds = useMemo(() => buildPeriodBounds(period), [period]);

  return { period, setPeriod, periodBounds };
}
