/**
 * Aperçu maintien de salaire (moteur) pour une absence d'arrêt qualifiée.
 */

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getMaintenancePreview,
  type MaintenancePreview,
} from "@/api/absences";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** Types d'absence pour lesquels le bloc maintien est pertinent (types principaux arrêt). */
export const ABSENCE_TYPES_MAINTIEN_PREVIEW = new Set<string>([
  "arret_maladie",
  "arret_at",
  "arret_maladie_pro",
]);

const eur = (n: number | null | undefined) =>
  new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(Number(n ?? 0));

const pct = (t: number | null | undefined) =>
  `${(Number(t ?? 0) * 100).toFixed(1)} %`;

function alertBannerClass(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("non calculables")) {
    return "rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive";
  }
  if (t.includes("ijss versées directement")) {
    return "rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-950 dark:bg-blue-950/30 dark:text-blue-100";
  }
  if (
    t.includes("insuffisante") ||
    t.includes("plafonné") ||
    t.includes("prévoyance relais") ||
    t.includes("conventionnelle moins favorable")
  ) {
    return "rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-950 dark:bg-orange-950/20 dark:text-orange-100";
  }
  return "rounded-md border border-muted bg-muted/40 px-3 py-2 text-sm";
}

export interface MaintenancePreviewBlockProps {
  absenceId: string;
  arretType: string | null;
  onSubrogationChange?: (value: boolean) => void;
}

export function MaintenancePreviewBlock({
  absenceId,
  arretType,
  onSubrogationChange,
}: MaintenancePreviewBlockProps) {
  const [subrogationOverride, setSubrogationOverride] = useState<
    boolean | undefined
  >(undefined);

  useEffect(() => {
    setSubrogationOverride(undefined);
  }, [absenceId, arretType]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["maintenance-preview", absenceId, subrogationOverride],
    enabled: Boolean(absenceId && arretType),
    queryFn: async () => {
      const res = await getMaintenancePreview(absenceId, subrogationOverride);
      return res.data;
    },
  });

  if (!arretType) {
    return null;
  }

  const errDetail = (() => {
    if (!error) return "";
    const ax = error as { response?: { data?: { detail?: unknown } } };
    const d = ax.response?.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => String(x)).join(", ");
    return "Une erreur est survenue.";
  })();

  return (
    <Card className="border-muted">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">
          Maintien de salaire
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-[85%]" />
            <Skeleton className="h-4 w-[70%]" />
          </div>
        )}

        {isError && (
          <div
            className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-destructive"
            role="alert"
          >
            <p className="font-medium">Chargement impossible</p>
            <p className="text-sm opacity-90">{errDetail}</p>
          </div>
        )}

        {!isLoading && !isError && data && (
          <MaintenancePreviewBody
            data={data}
            subrogationOverride={subrogationOverride}
            onSubrogationSelect={(v) => {
              setSubrogationOverride(v);
              onSubrogationChange?.(v);
            }}
          />
        )}
      </CardContent>
    </Card>
  );
}

function MaintenancePreviewBody({
  data,
  subrogationOverride,
  onSubrogationSelect,
}: {
  data: MaintenancePreview;
  subrogationOverride: boolean | undefined;
  onSubrogationSelect: (v: boolean) => void;
}) {
  const mode = data.subrogation_mode ?? "automatic";
  const carence = data.carence;
  const ijss = data.ijss;
  const maintien = data.maintien;

  const subrogationSelectValue = (subrogationOverride ?? data.subrogation_active)
    ? "oui"
    : "non";

  return (
    <>
      <section className="space-y-1">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Carence
        </h4>
        <p>Carence SS : {carence.carence_ss_jours} jour(s)</p>
        <p>Carence employeur : {carence.carence_employeur_jours} jour(s)</p>
        {carence.est_continuite ? (
          <Badge className="bg-emerald-600 hover:bg-emerald-600">
            Continuité — pas de nouvelle carence
          </Badge>
        ) : null}
      </section>

      <section className="space-y-1">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          IJSS
        </h4>
        <p>IJSS estimées : {eur(ijss.ijss_theorique)}</p>
        <p>Taux appliqué : {pct(ijss.taux_applique)}</p>
        <p>Jours indemnisés : {ijss.nb_jours_indemnises}</p>
        <p>Salaire journalier de base : {eur(ijss.salaire_journalier_base)}</p>
      </section>

      <section className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Maintien
        </h4>
        {!maintien.maintien_applicable && maintien.motif_non_maintien ? (
          <div className="rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-orange-950 dark:bg-orange-950/20 dark:text-orange-100">
            {maintien.motif_non_maintien}
          </div>
        ) : (
          <>
            <p>Taux de maintien : {pct(maintien.taux_maintien)}</p>
            <p>Maintien cible : {eur(maintien.maintien_cible)}</p>
            {data.subrogation_active ? (
              <p>IJSS déduites : {eur(ijss.ijss_theorique)}</p>
            ) : null}
            <p>Maintien versé : {eur(maintien.maintien_verse)}</p>
            <p>
              Complément employeur :{" "}
              {eur(maintien.complement_employeur ?? 0)}
            </p>
          </>
        )}
      </section>

      <section className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Subrogation
        </h4>
        {mode === "per_case" ? (
          <Select
            value={subrogationSelectValue}
            onValueChange={(v) => onSubrogationSelect(v === "oui")}
          >
            <SelectTrigger className="max-w-[220px]">
              <SelectValue placeholder="Subrogation" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="oui">Oui</SelectItem>
              <SelectItem value="non">Non</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <p>Subrogation : {data.subrogation_active ? "Oui" : "Non"}</p>
        )}
      </section>

      {data.alertes?.length ? (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Alertes
          </h4>
          <ul className="space-y-2">
            {data.alertes.map((a, i) => (
              <li key={i} className={alertBannerClass(a)}>
                {a}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
