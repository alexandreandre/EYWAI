import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, UserRound } from "lucide-react";
import {
  getBadgeusePunchCandidates,
  scanBadgeQr,
  type PunchCandidate,
  type ScanPunchResult,
} from "@/api/badgeuse";
import {
  getTerminalPunchCandidates,
  scanBadgeQrTerminal,
} from "@/api/badgeuseTerminal";
import type { BadgeuseTerminalAuthMode } from "@/hooks/useBadgeuseTerminalAuth";
import { eventTypeLabel } from "@/lib/badgeuseFormat";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

type Props = {
  companyId: string;
  authMode?: BadgeuseTerminalAuthMode;
  onSuccess?: () => void;
};

type Feedback =
  | { kind: "success"; result: ScanPunchResult }
  | { kind: "error"; message: string };

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

function CandidateRow({
  candidate,
  disabled,
  onPunch,
}: {
  candidate: PunchCandidate;
  disabled: boolean;
  onPunch: (c: PunchCandidate) => void;
}) {
  const actionLabel =
    candidate.next_action === "ENTREE" ? "Marquer comme entré" : "Sortie";

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onPunch(candidate)}
      className={cn(
        "flex w-full items-center gap-3 rounded-lg border bg-background px-3 py-2.5 text-left transition-colors",
        "hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        disabled && "pointer-events-none opacity-60"
      )}
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <UserRound className="h-4 w-4" aria-hidden />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium leading-tight">
          {candidate.display_name}
        </p>
        {candidate.username && (
          <p className="truncate text-xs text-muted-foreground">
            {candidate.username}
          </p>
        )}
      </div>
      <span className="shrink-0 rounded-md border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium text-foreground">
        {actionLabel}
      </span>
    </button>
  );
}

export function BadgeuseFallbackPanel({
  companyId,
  authMode = "rh",
  onSuccess,
}: Props) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), 280);

  const showSearchResults = debouncedSearch.length >= 2;

  const { data: searchResults = [], isFetching: searchLoading } = useQuery({
    queryKey: ["badgeuse", "punch-candidates", companyId, debouncedSearch, authMode],
    queryFn: () =>
      authMode === "terminal"
        ? getTerminalPunchCandidates({ q: debouncedSearch, limit: 12 })
        : getBadgeusePunchCandidates(companyId, { q: debouncedSearch, limit: 12 }),
    enabled: showSearchResults,
  });

  const { data: notBadgedToday = [], isFetching: notBadgedLoading } = useQuery({
    queryKey: ["badgeuse", "punch-candidates", companyId, "not-badged", authMode],
    queryFn: () =>
      authMode === "terminal"
        ? getTerminalPunchCandidates({ onlyNotBadged: true, limit: 16 })
        : getBadgeusePunchCandidates(companyId, { onlyNotBadged: true, limit: 16 }),
    enabled: !showSearchResults,
  });

  const punchMutation = useMutation({
    mutationFn: (payload: { employee_id?: string; username?: string }) =>
      authMode === "terminal"
        ? scanBadgeQrTerminal(payload)
        : scanBadgeQr(companyId, payload),
    onSuccess: (result) => {
      setFeedback({ kind: "success", result });
      setSearch("");
      setIdentifier("");
      void queryClient.invalidateQueries({
        queryKey: ["badgeuse", "punch-candidates", companyId],
      });
      onSuccess?.();
      window.setTimeout(() => setFeedback(null), 2400);
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Pointage impossible";
      setFeedback({ kind: "error", message: String(message) });
      window.setTimeout(() => setFeedback(null), 3200);
    },
  });

  const punchCandidate = useCallback(
    (candidate: PunchCandidate) => {
      punchMutation.mutate({ employee_id: candidate.employee_id });
    },
    [punchMutation]
  );

  const punchByIdentifier = () => {
    const id = identifier.trim();
    if (!id) return;
    punchMutation.mutate({ username: id });
  };

  const busy = punchMutation.isPending;

  return (
    <div className="relative space-y-4">
      <div className="flex items-start gap-2">
        <UserRound
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden
        />
        <div>
          <p className="text-sm font-medium">Sans QR</p>
          <p className="text-xs text-muted-foreground">
            Téléphone oublié, batterie vide ou QR illisible — recherchez
            l&apos;employé et validez en un clic.
          </p>
        </div>
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Nom, prénom ou identifiant…"
          className="h-11 pl-9 text-base"
          autoComplete="off"
          aria-label="Rechercher un employé"
        />
      </div>

      {showSearchResults && (
        <div className="space-y-2">
          {searchLoading && (
            <p className="text-sm text-muted-foreground">Recherche…</p>
          )}
          {!searchLoading && searchResults.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Aucun employé trouvé pour « {debouncedSearch} ».
            </p>
          )}
          {searchResults.map((c) => (
            <CandidateRow
              key={c.employee_id}
              candidate={c}
              disabled={busy}
              onPunch={punchCandidate}
            />
          ))}
        </div>
      )}

      {!showSearchResults && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Pas encore badgés aujourd&apos;hui
          </p>
          {notBadgedLoading && (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          )}
          {!notBadgedLoading && notBadgedToday.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Tous les employés éligibles ont déjà badgé, ou saisissez un nom
              ci-dessus.
            </p>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            {notBadgedToday.map((c) => (
              <CandidateRow
                key={c.employee_id}
                candidate={c}
                disabled={busy}
                onPunch={punchCandidate}
              />
            ))}
          </div>
        </div>
      )}

      <details className="group rounded-lg border bg-muted/20 px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium text-muted-foreground marker:content-none">
          <span className="group-open:hidden">Identifiant de connexion uniquement</span>
          <span className="hidden group-open:inline">Identifiant de connexion</span>
        </summary>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="badge-fallback-username" className="text-xs">
              ex. jean.dupont
            </Label>
            <Input
              id="badge-fallback-username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Identifiant employé"
              className="h-9"
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === "Enter") punchByIdentifier();
              }}
            />
          </div>
          <Button
            type="button"
            variant="secondary"
            className="shrink-0"
            disabled={!identifier.trim() || busy}
            onClick={punchByIdentifier}
          >
            Badger
          </Button>
        </div>
      </details>

      {feedback && (
        <div
          className={cn(
            "rounded-lg px-4 py-3 text-sm",
            feedback.kind === "success"
              ? "bg-emerald-600 text-white"
              : "bg-destructive text-destructive-foreground"
          )}
          role="status"
          aria-live="polite"
        >
          {feedback.kind === "success" ? (
            <>
              <p className="font-semibold">{feedback.result.status_label}</p>
              <p>
                {feedback.result.employee_name} —{" "}
                {eventTypeLabel(feedback.result.event_type)}
              </p>
            </>
          ) : (
            <p>{feedback.message}</p>
          )}
        </div>
      )}
    </div>
  );
}
