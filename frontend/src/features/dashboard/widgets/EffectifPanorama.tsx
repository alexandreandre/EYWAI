import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Briefcase,
  CalendarCheck,
  HeartPulse,
  PartyPopper,
  Plane,
} from 'lucide-react';
import type { KpiData, TeamPulseEmployee, TeamPulseEvent } from '@/features/dashboard/types';

const CONTRACT_LABELS: Record<string, string> = {
  CDI: 'CDI',
  CDD: 'CDD',
  Alternance: 'Alternant',
  Stage: 'Stagiaire',
  Intérim: 'Intérim',
  Freelance: 'Freelance',
  Autre: 'Autre',
};

interface EffectifPanoramaProps {
  kpis: KpiData;
  absentsToday: TeamPulseEmployee[];
  upcomingEvents: TeamPulseEvent[];
}

export function EffectifPanorama({
  kpis,
  absentsToday,
  upcomingEvents,
}: EffectifPanoramaProps) {
  const hommes = kpis.hommesCount ?? null;
  const femmes = kpis.femmesCount ?? null;
  const hasGenderData = hommes != null && femmes != null;
  const dist = kpis.contractDistribution || {};
  const handicap = kpis.handicapesCount ?? 0;
  const contractTypes = ['CDI', 'CDD', 'Alternance', 'Stage'].filter((t) => (dist[t] ?? 0) > 0);
  const otherContractKeys = Object.keys(dist).filter(
    (k) => !['CDI', 'CDD', 'Alternance', 'Stage'].includes(k),
  );
  const hasContractData =
    contractTypes.length > 0 || otherContractKeys.length > 0 || handicap > 0;

  const getAbsenceIcon = (status: string) => {
    if (status.includes('Maladie')) return <HeartPulse className="h-3 w-3 text-red-500" />;
    if (status.includes('Congé')) return <Plane className="h-3 w-3 text-blue-500" />;
    if (status.includes('RTT')) return <CalendarCheck className="h-3 w-3 text-purple-500" />;
    return <CalendarCheck className="h-3 w-3 text-muted-foreground" />;
  };

  const getEventIcon = (type: TeamPulseEvent['type']) => {
    if (type === 'birthday') return <PartyPopper className="h-4 w-4 text-pink-500" />;
    return <Briefcase className="h-4 w-4 text-primary" />;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Effectif &amp; absentéisme</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border bg-muted/20 p-4 text-center">
            <p className="text-xs font-medium text-muted-foreground mb-1">Effectif actif</p>
            <p className="text-3xl font-bold tabular-nums">{kpis.effectifActif}</p>
            <div className="mt-2 flex justify-center gap-4 text-xs text-muted-foreground border-t pt-2">
              <span>
                CDI <span className="font-bold text-foreground">{kpis.cdiCount}</span>
              </span>
              <span>
                CDD <span className="font-bold text-foreground">{kpis.cddCount}</span>
              </span>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/20 p-4">
            <p className="text-xs font-medium text-muted-foreground mb-2 text-center">
              Répartition H / F
            </p>
            {!hasGenderData ? (
              <p className="text-sm text-muted-foreground text-center">Non renseigné</p>
            ) : (
              <div className="flex flex-col gap-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-blue-500" />
                    Hommes
                  </span>
                  <span className="font-bold tabular-nums">{hommes}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-pink-500" />
                    Femmes
                  </span>
                  <span className="font-bold tabular-nums">{femmes}</span>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border bg-muted/20 p-4">
            <p className="text-xs font-medium text-muted-foreground mb-2 text-center">Contrats</p>
            {!hasContractData ? (
              <p className="text-sm text-muted-foreground text-center">Aucune donnée</p>
            ) : (
              <div className="space-y-1 text-xs">
                {contractTypes.map((t) => (
                  <div key={t} className="flex justify-between">
                    <span className="text-muted-foreground">{CONTRACT_LABELS[t] ?? t}</span>
                    <span className="font-bold tabular-nums">{dist[t] ?? 0}</span>
                  </div>
                ))}
                {otherContractKeys.map((t) => (
                  <div key={t} className="flex justify-between">
                    <span className="text-muted-foreground">{CONTRACT_LABELS[t] ?? t}</span>
                    <span className="font-bold tabular-nums">{dist[t] ?? 0}</span>
                  </div>
                ))}
                {handicap > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">RQTH</span>
                    <span className="font-bold tabular-nums">{handicap}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="rounded-lg border bg-muted/20 p-4 text-center">
            <p className="text-xs font-medium text-muted-foreground mb-1">Absentéisme (30j)</p>
            <p
              className={`text-3xl font-bold tabular-nums ${
                kpis.tauxAbsenteisme > 5 ? 'text-amber-600' : 'text-foreground'
              }`}
            >
              {kpis.tauxAbsenteisme.toFixed(1)}%
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">Seuil d&apos;alerte : 5 %</p>
            <p className="text-xs font-medium text-muted-foreground mt-3 mb-1">
              Absents aujourd&apos;hui
            </p>
            <p
              className={`text-xl font-bold tabular-nums ${
                absentsToday.length > 0 ? 'text-red-600' : 'text-emerald-600'
              }`}
            >
              {absentsToday.length}
            </p>
            {absentsToday.length > 0 && absentsToday.length <= 2 && (
              <div className="mt-2 space-y-1 border-t pt-2">
                {absentsToday.map((emp) => (
                  <div
                    key={emp.id}
                    className="flex items-center justify-center gap-1 text-[10px] text-muted-foreground"
                  >
                    {getAbsenceIcon(emp.status)}
                    <span>
                      {emp.first_name} {emp.last_name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {upcomingEvents.length > 0 && (
          <div className="rounded-lg border border-dashed p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
              Cette semaine
            </p>
            <ul className="space-y-2">
              {upcomingEvents.slice(0, 3).map((event) => (
                <li key={event.id} className="flex items-center gap-2 text-sm">
                  {getEventIcon(event.type)}
                  <span className="font-medium">{event.employee_name}</span>
                  <span className="text-muted-foreground text-xs">— {event.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
