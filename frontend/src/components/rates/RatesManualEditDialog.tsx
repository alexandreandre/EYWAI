import { useMemo, useState } from 'react';
import { Pencil, Loader2, Search } from 'lucide-react';
import { toast } from 'sonner';

import { saveManualRate } from '@/api/rates';
import type { RatesResponse } from '@/api/rates';
import { getCategoryTitle, parseRatesError } from '@/lib/ratesUtils';
import {
  flattenScalarLeaves,
  parseNumericInput,
  setByPath,
  type RateLeaf,
} from '@/lib/ratesManualEdit';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

type Props = {
  data: RatesResponse;
  onSaved?: (configKey: string) => void;
};

export function RatesManualEditDialog({ data, onSaved }: Props) {
  const [open, setOpen] = useState(false);
  const [configKey, setConfigKey] = useState<string>('');
  const [search, setSearch] = useState('');
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);

  const keys = useMemo(() => Object.keys(data).sort(), [data]);

  const leaves = useMemo<RateLeaf[]>(() => {
    if (!configKey || !data[configKey]) return [];
    return flattenScalarLeaves(data[configKey].config_data);
  }, [configKey, data]);

  const filteredLeaves = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return leaves;
    return leaves.filter((l) => l.label.toLowerCase().includes(q));
  }, [leaves, search]);

  const resetForm = () => {
    setConfigKey('');
    setSearch('');
    setEdits({});
    setComment('');
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) resetForm();
  };

  const handleSelectKey = (key: string) => {
    setConfigKey(key);
    setSearch('');
    setEdits({});
  };

  const handleEdit = (pathKey: string, raw: string) => {
    setEdits((prev) => ({ ...prev, [pathKey]: raw }));
  };

  const changedLeaves = useMemo(() => {
    return leaves.filter((l) => {
      const raw = edits[l.pathKey];
      if (raw === undefined) return false;
      return raw !== String(l.value);
    });
  }, [leaves, edits]);

  const handleSave = async () => {
    if (!configKey || !data[configKey]) return;
    if (changedLeaves.length === 0) {
      toast.info('Aucune valeur modifiée.');
      return;
    }

    let nextConfig = data[configKey].config_data as Record<string, unknown>;
    for (const leaf of changedLeaves) {
      const raw = edits[leaf.pathKey];
      let value: unknown = raw;
      if (leaf.type === 'number') {
        const parsed = parseNumericInput(raw);
        if (parsed === null) {
          toast.error(`Valeur numérique invalide pour « ${leaf.label} ».`);
          return;
        }
        value = parsed;
      } else if (leaf.type === 'boolean') {
        value = raw === 'true';
      }
      nextConfig = setByPath(nextConfig, leaf.path, value);
    }

    setSaving(true);
    try {
      const res = await saveManualRate({
        config_key: configKey,
        config_data: nextConfig,
        comment: comment.trim() || undefined,
      });
      if (res.changed) {
        toast.success(
          `${getCategoryTitle(configKey)} enregistré (version ${res.version}).`,
        );
      } else {
        toast.info('Aucun changement détecté — référentiel inchangé.');
      }
      onSaved?.(configKey);
      handleOpenChange(false);
    } catch (error) {
      toast.error(parseRatesError(error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil className="mr-2 h-4 w-4" />
          Modifier un taux à la main
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Saisie manuelle d&apos;un taux</DialogTitle>
          <DialogDescription>
            Modifiez une ou plusieurs valeurs d&apos;un bloc de configuration. L&apos;enregistrement
            crée une nouvelle version du référentiel (l&apos;historique est conservé).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Bloc de configuration</Label>
            <Select value={configKey} onValueChange={handleSelectKey}>
              <SelectTrigger>
                <SelectValue placeholder="Choisir un bloc (SMIC, plafond, cotisations…)" />
              </SelectTrigger>
              <SelectContent>
                {keys.map((key) => (
                  <SelectItem key={key} value={key}>
                    {getCategoryTitle(key)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {configKey && (
            <>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filtrer les champs…"
                  className="pl-8"
                />
              </div>

              {leaves.length === 0 ? (
                <Alert>
                  <AlertDescription>
                    Ce bloc ne contient pas de valeur scalaire éditable directement.
                  </AlertDescription>
                </Alert>
              ) : (
                <ScrollArea className="h-72 rounded-md border">
                  <div className="divide-y">
                    {filteredLeaves.map((leaf) => {
                      const current = edits[leaf.pathKey] ?? String(leaf.value);
                      const isChanged = changedLeaves.some(
                        (c) => c.pathKey === leaf.pathKey,
                      );
                      return (
                        <div
                          key={leaf.pathKey}
                          className="flex items-center gap-3 px-3 py-2"
                        >
                          <span
                            className="min-w-0 flex-1 truncate text-sm text-muted-foreground"
                            title={leaf.label}
                          >
                            {leaf.label}
                          </span>
                          {leaf.type === 'boolean' ? (
                            <Select
                              value={current}
                              onValueChange={(v) => handleEdit(leaf.pathKey, v)}
                            >
                              <SelectTrigger className="w-32">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="true">Vrai</SelectItem>
                                <SelectItem value="false">Faux</SelectItem>
                              </SelectContent>
                            </Select>
                          ) : (
                            <Input
                              value={current}
                              inputMode={leaf.type === 'number' ? 'decimal' : 'text'}
                              onChange={(e) => handleEdit(leaf.pathKey, e.target.value)}
                              className={`w-40 ${isChanged ? 'border-primary ring-1 ring-primary/40' : ''}`}
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              )}

              <div className="space-y-2">
                <Label>Note (optionnelle)</Label>
                <Textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Justification de la saisie manuelle…"
                  rows={2}
                />
              </div>
            </>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <span className="mr-auto self-center text-xs text-muted-foreground">
            {changedLeaves.length > 0
              ? `${changedLeaves.length} valeur(s) modifiée(s)`
              : 'Aucune modification'}
          </span>
          <Button variant="ghost" onClick={() => handleOpenChange(false)} disabled={saving}>
            Annuler
          </Button>
          <Button onClick={handleSave} disabled={saving || changedLeaves.length === 0}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
