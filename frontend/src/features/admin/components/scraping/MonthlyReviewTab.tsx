import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
  AlertTriangle,
  Pencil,
  ShieldCheck,
  Radar,
} from 'lucide-react';
import {
  listPendingChanges,
  approvePendingChange,
  rejectPendingChange,
  runTripwire,
  ScrapingPendingChange,
} from '@/api/scraping';
import { log } from '@/lib/logger';

type ScalarDiff = { key: string; before: unknown; after: unknown };

const DECISION_LABELS: Record<string, string> = {
  A: 'Sources déterministes concordantes',
  B: 'Une source déterministe en échec',
  C: 'Désaccord déterministe non résolu',
};

function isScalar(v: unknown): boolean {
  return v === null || ['string', 'number', 'boolean'].includes(typeof v);
}

/** Diff des clés scalaires de premier niveau entre ancienne et nouvelle config. */
function computeScalarDiff(before: any, after: any): ScalarDiff[] {
  const diffs: ScalarDiff[] = [];
  const a = before && typeof before === 'object' ? before : {};
  const b = after && typeof after === 'object' ? after : {};
  const keys = Array.from(new Set([...Object.keys(a), ...Object.keys(b)]));
  for (const key of keys) {
    const bv = a[key];
    const av = b[key];
    if (!isScalar(bv) && !isScalar(av)) continue;
    if (JSON.stringify(bv) !== JSON.stringify(av)) {
      diffs.push({ key, before: bv, after: av });
    }
  }
  return diffs;
}

function formatValue(v: unknown): string {
  if (v === undefined) return '—';
  if (v === null) return 'null';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function MonthlyReviewTab() {
  const [pending, setPending] = useState<ScrapingPendingChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dialogue d'édition de la valeur proposée avant validation.
  const [editTarget, setEditTarget] = useState<ScrapingPendingChange | null>(null);
  const [editText, setEditText] = useState('');
  const [editError, setEditError] = useState<string | null>(null);

  const [tripwireBusy, setTripwireBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await listPendingChanges({ status: 'pending' });
      setPending(res.pending || []);
      setError(null);
    } catch (e) {
      log.error('Chargement des changements en attente échoué', e);
      setError('Impossible de charger les changements en attente.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const handleApprove = useCallback(
    async (item: ScrapingPendingChange, overrideValue?: any) => {
      setActionId(item.id);
      setError(null);
      try {
        await approvePendingChange(item.id, overrideValue);
        await load();
      } catch (e) {
        log.error('Validation du changement échouée', e);
        setError("La validation a échoué — payroll_config n'a pas été modifié.");
      } finally {
        setActionId(null);
      }
    },
    [load]
  );

  const handleReject = useCallback(
    async (item: ScrapingPendingChange) => {
      setActionId(item.id);
      setError(null);
      try {
        await rejectPendingChange(item.id);
        await load();
      } catch (e) {
        log.error('Rejet du changement échoué', e);
        setError('Le rejet a échoué.');
      } finally {
        setActionId(null);
      }
    },
    [load]
  );

  const handleTripwire = useCallback(async () => {
    setTripwireBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await runTripwire();
      setNotice(
        `Tripwire lancé sur ${res.sources_count} source(s) critique(s). Les changements détectés apparaîtront en alertes.`
      );
    } catch (e) {
      log.error('Lancement du tripwire échoué', e);
      setError('Le lancement du tripwire a échoué.');
    } finally {
      setTripwireBusy(false);
    }
  }, []);

  const openEditor = useCallback((item: ScrapingPendingChange) => {
    setEditTarget(item);
    setEditError(null);
    setEditText(JSON.stringify(item.proposed_config_data, null, 2));
  }, []);

  const confirmEdit = useCallback(async () => {
    if (!editTarget) return;
    let parsed: any;
    try {
      parsed = JSON.parse(editText);
    } catch {
      setEditError('JSON invalide — vérifiez la syntaxe.');
      return;
    }
    const target = editTarget;
    setEditTarget(null);
    await handleApprove(target, parsed);
  }, [editTarget, editText, handleApprove]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Chargement de la revue mensuelle…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Revue mensuelle des taux critiques
              </CardTitle>
              <CardDescription>
                Rien n'est écrit dans la paie sans validation humaine. Vérifiez chaque
                changement (ancienne valeur, nouvelle, concordance des sources) puis
                validez, éditez ou rejetez.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleTripwire}
              disabled={tripwireBusy}
            >
              {tripwireBusy ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Radar className="h-4 w-4 mr-2" />
              )}
              Lancer le tripwire
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {notice && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-primary/30 bg-primary/10 p-3 text-sm">
              <Radar className="h-4 w-4" />
              {notice}
            </div>
          )}
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </div>
          )}

          {pending.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-muted-foreground">
              <CheckCircle2 className="h-8 w-8 text-emerald-500" />
              <p>Aucun changement en attente. Tous les taux critiques sont à jour.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {pending.map((item) => (
                <PendingCard
                  key={item.id}
                  item={item}
                  busy={actionId === item.id}
                  onApprove={() => handleApprove(item)}
                  onReject={() => handleReject(item)}
                  onEdit={() => openEditor(item)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!editTarget} onOpenChange={(o) => !o && setEditTarget(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Éditer la valeur proposée</DialogTitle>
            <DialogDescription>
              Modifiez la configuration au format JSON avant de valider. La valeur éditée
              sera écrite dans payroll_config à la place de la valeur scrapée.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            rows={16}
            className="font-mono text-xs"
          />
          {editError && (
            <p className="text-sm text-destructive">{editError}</p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>
              Annuler
            </Button>
            <Button onClick={confirmEdit}>
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Valider la valeur éditée
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PendingCard({
  item,
  busy,
  onApprove,
  onReject,
  onEdit,
}: {
  item: ScrapingPendingChange;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onEdit: () => void;
}) {
  const diffs = useMemo(
    () => computeScalarDiff(item.current_config_data, item.proposed_config_data),
    [item.current_config_data, item.proposed_config_data]
  );
  const agreement = item.sources_agreement;
  const ai = item.ai_candidate;
  const sourceName =
    item.scraping_sources?.source_name || item.scraper_name || item.config_key;

  return (
    <div className="rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">{sourceName}</span>
            <Badge variant="outline">{item.config_key}</Badge>
            {item.decision_case && (
              <Badge variant="secondary">Cas {item.decision_case}</Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {item.decision_case
              ? DECISION_LABELS[item.decision_case] || 'Décision multi-sources'
              : 'Décision multi-sources'}
            {item.current_version != null && ` · version actuelle v${item.current_version}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {agreement === true ? (
            <Badge className="bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/15">
              Sources concordent : Oui
            </Badge>
          ) : agreement === false ? (
            <Badge className="bg-amber-500/15 text-amber-600 hover:bg-amber-500/15">
              Sources concordent : Non
            </Badge>
          ) : (
            <Badge variant="outline">Concordance inconnue</Badge>
          )}
        </div>
      </div>

      {item.warnings && item.warnings.length > 0 && (
        <ul className="mt-3 space-y-1">
          {item.warnings.map((w, i) => (
            <li
              key={i}
              className="flex items-center gap-2 text-xs text-amber-600"
            >
              <AlertTriangle className="h-3 w-3" />
              {w}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3">
        {diffs.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Champ</TableHead>
                <TableHead>Ancienne valeur</TableHead>
                <TableHead>Nouvelle valeur</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {diffs.map((d) => (
                <TableRow key={d.key}>
                  <TableCell className="font-medium">{d.key}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatValue(d.before)}
                  </TableCell>
                  <TableCell className="font-semibold">
                    {formatValue(d.after)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground">
              Diff non scalaire — voir la configuration proposée (JSON)
            </summary>
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-3">
              {JSON.stringify(item.proposed_config_data, null, 2)}
            </pre>
          </details>
        )}
      </div>

      {item.discrepancies && item.discrepancies.length > 0 && (
        <div className="mt-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Valeurs par source
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Valeur extraite</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {item.discrepancies.map((d, i) => (
                <TableRow key={`${d.label}-${i}`}>
                  <TableCell className="font-medium">{d.label}</TableCell>
                  <TableCell>
                    {d.is_ai ? (
                      <Badge variant="secondary">IA</Badge>
                    ) : (
                      <Badge variant="outline">Déterministe</Badge>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {formatValue(d.signature)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {ai && (ai.value !== undefined || ai.citation_url) && (
        <div className="mt-3 rounded-md bg-muted/50 p-3 text-xs">
          <div className="font-medium">Valeur candidate IA (témoin)</div>
          {ai.value !== undefined && (
            <div className="mt-1">Proposition : {formatValue(ai.value)}</div>
          )}
          {ai.citation_url ? (
            <a
              href={ai.citation_url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex items-center gap-1 text-primary hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              Citation officielle
              {ai.citation_date ? ` (${ai.citation_date})` : ''}
            </a>
          ) : (
            <div className="mt-1 text-amber-600">Aucune citation fournie</div>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={onApprove} disabled={busy}>
          {busy ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4 mr-2" />
          )}
          Valider
        </Button>
        <Button size="sm" variant="outline" onClick={onEdit} disabled={busy}>
          <Pencil className="h-4 w-4 mr-2" />
          Éditer
        </Button>
        <Button size="sm" variant="destructive" onClick={onReject} disabled={busy}>
          <XCircle className="h-4 w-4 mr-2" />
          Rejeter
        </Button>
      </div>
    </div>
  );
}
