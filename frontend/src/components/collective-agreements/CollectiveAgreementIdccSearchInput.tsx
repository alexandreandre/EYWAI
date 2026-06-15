import { useEffect, useMemo, useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { formatCatalogConventionName } from '@/lib/collectiveAgreementDisplay';
import { filterCollectiveAgreements } from '@/lib/collectiveAgreementSearch';
import { cn } from '@/lib/utils';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';

type Suggestion = collectiveAgreementsApi.CollectiveAgreementSuggestItem;

type CollectiveAgreementIdccSearchInputProps = {
  value: string;
  onValueChange: (value: string) => void;
  onSelectSuggestion?: (suggestion: Suggestion) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  inputClassName?: string;
  id?: string;
  /** Catalogue local déjà chargé (évite un aller-retour API pour les conventions connues). */
  localCatalog?: collectiveAgreementsApi.CollectiveAgreementCatalog[];
  onKeyDown?: React.ComponentProps<'input'>['onKeyDown'];
};

export function CollectiveAgreementIdccSearchInput({
  value,
  onValueChange,
  onSelectSuggestion,
  placeholder = 'Rechercher (ex. plasturgie, syntec) ou saisir un IDCC…',
  disabled = false,
  className,
  inputClassName,
  id,
  localCatalog = [],
  onKeyDown,
}: CollectiveAgreementIdccSearchInputProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [remoteSuggestions, setRemoteSuggestions] = useState<Suggestion[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const localSuggestions = useMemo(() => {
    if (value.trim().length < 2) return [];
    return filterCollectiveAgreements(localCatalog, value, 8).map((item) => ({
      idcc: item.idcc,
      name: item.name,
      source: 'catalog' as const,
      agreement_id: item.id,
      sector: item.sector ?? null,
    }));
  }, [localCatalog, value]);

  useEffect(() => {
    const query = value.trim();
    if (query.length < 2) {
      setRemoteSuggestions([]);
      setIsSearching(false);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setIsSearching(true);
      void collectiveAgreementsApi
        .suggestCatalog(query, { signal: controller.signal })
        .then((res) => setRemoteSuggestions(res.data?.suggestions ?? []))
        .catch(() => {
          if (!controller.signal.aborted) setRemoteSuggestions([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsSearching(false);
        });
    }, 250);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [value]);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  const suggestions = useMemo(() => {
    const merged = new Map<string, Suggestion>();
    for (const item of [...localSuggestions, ...remoteSuggestions]) {
      if (!item.idcc) continue;
      if (!merged.has(item.idcc) || item.source === 'catalog') {
        merged.set(item.idcc, item);
      }
    }
    return Array.from(merged.values()).slice(0, 10);
  }, [localSuggestions, remoteSuggestions]);

  const showPanel = open && value.trim().length >= 2;

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <Input
        id={id}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        className={inputClassName}
        onChange={(event) => {
          onValueChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        autoComplete="off"
      />

      {showPanel ? (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border bg-popover text-popover-foreground shadow-md">
          {suggestions.length === 0 ? (
            <p className="px-3 py-4 text-sm text-muted-foreground">
              {isSearching ? 'Recherche en cours…' : 'Aucune convention trouvée.'}
            </p>
          ) : (
            <ul className="p-1">
              {suggestions.map((suggestion) => (
                <li key={`${suggestion.source}-${suggestion.idcc}`}>
                  <button
                    type="button"
                    className="w-full rounded-sm px-2 py-2 text-left hover:bg-accent hover:text-accent-foreground"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => {
                      onValueChange(suggestion.idcc);
                      onSelectSuggestion?.(suggestion);
                      setOpen(false);
                    }}
                  >
                    <p className="font-medium break-words leading-snug">
                      {formatCatalogConventionName(suggestion.name)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      IDCC {suggestion.idcc}
                      {suggestion.sector ? ` · ${suggestion.sector}` : ''}
                      {suggestion.source === 'kali' ? ' · Légifrance' : ''}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
