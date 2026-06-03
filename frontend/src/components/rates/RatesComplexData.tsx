import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AVANTAGES_EN_NATURE_FORFAIT_ROWS,
  formatAvantagesEnNatureAmount,
  formatEurAmount,
  formatFraisProArrayItemTitle,
  formatPasZone,
  formatRateDisplayValue,
  formatRateKey,
  isRateKeyUnitless,
  isRepasForfaitRecord,
  pickAvantagesEnNatureValue,
  REPAS_FORFAIT_SITUATION_KEYS,
} from '@/lib/ratesUtils';
import { RatesRateValue } from '@/components/rates/RatesRateValue';
import { cn } from '@/lib/utils';

const MAX_DEPTH = 4;
const ACCORDION_MIN_KEYS = 2;

const nestedAccordionClass = 'border-0 bg-muted/20 rounded-md px-2 mb-1';
const nestedAccordionTriggerClass = 'hover:no-underline py-2 text-sm font-medium';

function RatesLabeledValueTable({
  rows,
}: {
  rows: { key: string; value: unknown }[];
}) {
  if (rows.length === 0) return null;
  return (
    <Table>
      <TableHeader>
        <TableRow className="border-border/40 hover:bg-transparent">
          <TableHead className="h-9 text-xs font-medium text-muted-foreground">
            Paramètre
          </TableHead>
          <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
            Valeur
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(({ key, value }) => (
          <TableRow key={key} className="border-border/40">
            <TableCell className="py-2 text-sm text-muted-foreground">
              {formatRateKey(key)}
            </TableCell>
            <TableCell className="py-2 text-right text-sm font-medium tabular-nums">
              {formatRateDisplayValue(value, key)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function RatesRepasForfaitView({ data }: { data: Record<string, number> }) {
  return (
    <div className="space-y-2">
      <p className="text-xs leading-relaxed text-muted-foreground">
        Forfaits URSSAF par repas (indemnités repas / base d&apos;évaluation des avantages en
        nature).
      </p>
      <RatesLabeledValueTable
        rows={REPAS_FORFAIT_SITUATION_KEYS.filter((key) => data[key] != null).map((key) => ({
          key,
          value: data[key],
        }))}
      />
    </div>
  );
}

function shouldUseAccordion(depth: number, entryCount: number): boolean {
  if (entryCount < ACCORDION_MIN_KEYS) return false;
  return depth <= 1;
}

export function RatesSimpleTable({
  obj,
  unit,
}: {
  obj: Record<string, unknown>;
  unit?: string;
}) {
  return (
    <Table>
      <TableBody>
        {Object.entries(obj).map(([k, v]) => {
          if (isRateKeyUnitless(k)) {
            return (
              <TableRow key={k} className="border-border/40">
                <TableCell className="h-auto py-2.5 text-sm text-muted-foreground">
                  {formatRateKey(k)}
                </TableCell>
                <TableCell className="h-auto py-2.5 text-right text-lg font-semibold tabular-nums text-foreground">
                  {formatRateDisplayValue(v, k)}
                </TableCell>
              </TableRow>
            );
          }
          const rowUnit = unit?.includes('€') && k.toLowerCase().includes('mensuel') ? '€' : unit;
          return (
            <TableRow key={k} className="border-border/40">
              <TableCell className="h-auto py-2.5 text-sm text-muted-foreground">
                {formatRateKey(k)}
              </TableCell>
              <TableCell className="h-auto py-2.5 text-right text-lg font-semibold tabular-nums text-foreground">
                {formatRateDisplayValue(v, k)}
                {rowUnit ? ` ${rowUnit}` : ''}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function RatesObjectAccordion({
  entries,
  depth,
  itemPrefix = '',
}: {
  entries: [string, unknown][];
  depth: number;
  itemPrefix?: string;
}) {
  return (
    <Accordion type="multiple" defaultValue={[]} className="w-full">
      {entries.map(([k, v]) => {
        const value = `${itemPrefix}${k}`;
        if (k === 'repas' && isRepasForfaitRecord(v)) {
          return (
            <AccordionItem key={value} value={value} className={nestedAccordionClass}>
              <AccordionTrigger className={nestedAccordionTriggerClass}>
                <span className="flex min-w-0 flex-col items-start text-left">
                  <span>{formatRateKey(k)}</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    Forfaits URSSAF — € / repas
                  </span>
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-2 pb-3">
                <RatesRepasForfaitView data={v} />
              </AccordionContent>
            </AccordionItem>
          );
        }
        return (
          <AccordionItem key={value} value={value} className={nestedAccordionClass}>
            <AccordionTrigger className={nestedAccordionTriggerClass}>
              {formatRateKey(k)}
            </AccordionTrigger>
            <AccordionContent className="pb-2">
              <RatesComplexObject obj={v} depth={depth + 1} />
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}

export function RatesComplexObject({
  obj,
  title = '',
  depth = 0,
}: {
  obj: unknown;
  title?: string;
  depth?: number;
}) {
  if (obj === null || obj === undefined) return null;

  if (Array.isArray(obj)) {
    if (obj.length === 0) return null;
    if (shouldUseAccordion(depth, obj.length)) {
      return (
        <div className="space-y-1">
          {title && (
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {title}
            </div>
          )}
          <Accordion type="multiple" defaultValue={[]} className="w-full">
            {obj.map((item, index) => {
              const record =
                item && typeof item === 'object' && !Array.isArray(item)
                  ? (item as Record<string, unknown>)
                  : {};
              const itemTitle = formatFraisProArrayItemTitle(record, index);
              return (
                <AccordionItem
                  key={index}
                  value={`${title || 'item'}-${index}`}
                  className={nestedAccordionClass}
                >
                  <AccordionTrigger className={nestedAccordionTriggerClass}>
                    {itemTitle}
                  </AccordionTrigger>
                  <AccordionContent className="pb-2">
                    <RatesComplexObject obj={item} depth={depth + 1} />
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </div>
      );
    }
    return (
      <div className="space-y-2">
        {title && (
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </div>
        )}
        {obj.map((item, index) => (
          <div key={index} className="rounded-md bg-muted/20 p-2">
            <RatesComplexObject obj={item} title={`Élément ${index + 1}`} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }

  if (typeof obj === 'object' && depth >= MAX_DEPTH) {
    return (
      <Table>
        <TableBody>
          {Object.entries(obj as Record<string, unknown>).map(([k, v]) => (
            <TableRow key={k} className="border-border/40">
              <TableCell className="p-1 text-xs text-muted-foreground">{formatRateKey(k)}</TableCell>
              <TableCell className="p-1 text-right text-sm tabular-nums">
                {typeof v === 'object' ? JSON.stringify(v) : formatRateDisplayValue(v, k)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  if (typeof obj === 'object') {
    const entries = Object.entries(obj as Record<string, unknown>);
    if (shouldUseAccordion(depth, entries.length)) {
      return (
        <div className="space-y-1">
          {title && (
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {title}
            </div>
          )}
          <RatesObjectAccordion entries={entries} depth={depth} itemPrefix={title ? `${title}-` : ''} />
        </div>
      );
    }

    const primitiveEntries = entries.filter(([, v]) => v === null || typeof v !== 'object');
    const nestedEntries = entries.filter(([, v]) => v !== null && typeof v === 'object');

    return (
      <div className="space-y-2">
        {title && (
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </div>
        )}
        {primitiveEntries.length > 0 && (
          <RatesLabeledValueTable
            rows={primitiveEntries.map(([k, v]) => ({ key: k, value: v }))}
          />
        )}
        {nestedEntries.length > 0 && (
          <RatesObjectAccordion
            entries={nestedEntries}
            depth={depth}
            itemPrefix={title ? `${title}-` : ''}
          />
        )}
      </div>
    );
  }

  return <span className="font-medium tabular-nums">{String(obj)}</span>;
}

type LogementBaremeRow = {
  remuneration_max_eur?: number;
  valeur_1_piece_eur?: number;
  valeur_par_piece_suppl_eur?: number;
};

function isLogementBaremeRow(row: unknown): row is LogementBaremeRow {
  return row !== null && typeof row === 'object' && !Array.isArray(row);
}

export function RatesAvantagesEnNatureView({
  configData,
}: {
  configData: Record<string, unknown>;
}) {
  const forfaitRows = AVANTAGES_EN_NATURE_FORFAIT_ROWS.map((row) => ({
    ...row,
    value: pickAvantagesEnNatureValue(configData, row.keys),
  })).filter((row) => row.value !== undefined);

  const logement =
    (configData.logement_bareme_forfaitaire as unknown) ??
    configData.logement ??
    configData.logement_bareme;
  const logementRows = Array.isArray(logement)
    ? logement.filter(isLogementBaremeRow)
    : [];

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-muted-foreground">
        Forfaits URSSAF pour l&apos;évaluation des avantages en nature (montants utilisés en paie
        pour la base taxable et les exonérations).
      </p>

      {forfaitRows.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow className="border-border/40 hover:bg-transparent">
              <TableHead className="h-9 text-xs font-medium text-muted-foreground">
                Forfait
              </TableHead>
              <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
                Montant
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {forfaitRows.map((row) => (
              <TableRow key={row.keys[0]} className="border-border/40">
                <TableCell className="py-2.5 align-top">
                  <div className="text-sm font-medium text-foreground">{row.label}</div>
                  <div className="mt-0.5 text-xs leading-snug text-muted-foreground">
                    {row.hint}
                  </div>
                </TableCell>
                <TableCell className="py-2.5 text-right align-top text-sm font-semibold tabular-nums text-foreground">
                  {formatAvantagesEnNatureAmount(row.value, row.unit)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {logementRows.length > 0 && (
        <Accordion type="single" collapsible defaultValue="logement" className="w-full">
          <AccordionItem value="logement" className={cn(nestedAccordionClass, 'px-3')}>
            <AccordionTrigger className={nestedAccordionTriggerClass}>
              <span className="flex min-w-0 flex-col items-start text-left">
                <span>Logement mis à disposition</span>
                <span className="text-xs font-normal text-muted-foreground">
                  Barème mensuel forfaitaire — {logementRows.length} tranches
                </span>
              </span>
            </AccordionTrigger>
            <AccordionContent className="pb-3">
              <p className="mb-2 text-xs leading-relaxed text-muted-foreground">
                Valeur de l&apos;avantage selon la rémunération mensuelle du salarié et le nombre de
                pièces du logement (montants mensuels).
              </p>
              <Table>
                <TableHeader>
                  <TableRow className="border-border/40 hover:bg-transparent">
                    <TableHead className="h-9 text-xs font-medium text-muted-foreground">
                      Rémunération max.
                    </TableHead>
                    <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
                      1 pièce
                    </TableHead>
                    <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
                      Pièce suppl.
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logementRows.map((row, index) => (
                    <TableRow key={index} className="border-border/40">
                      <TableCell className="py-2 text-sm tabular-nums text-muted-foreground">
                        {row.remuneration_max_eur != null
                          ? `≤ ${formatEurAmount(row.remuneration_max_eur)} / mois`
                          : '—'}
                      </TableCell>
                      <TableCell className="py-2 text-right text-sm font-medium tabular-nums">
                        {row.valeur_1_piece_eur != null
                          ? `${formatEurAmount(row.valeur_1_piece_eur)} / mois`
                          : '—'}
                      </TableCell>
                      <TableCell className="py-2 text-right text-sm font-medium tabular-nums">
                        {row.valeur_par_piece_suppl_eur != null
                          ? `${formatEurAmount(row.valeur_par_piece_suppl_eur)} / mois`
                          : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )}

      {forfaitRows.length === 0 && logementRows.length === 0 && (
        <RatesComplexObject obj={configData} />
      )}
    </div>
  );
}

export function RatesPasView({ configData }: { configData: Record<string, unknown> }) {
  const baremes = (
    configData as {
      baremes?: Array<{ zone: string; tranches: Array<{ plafond?: number; taux: number }> }>;
    }
  ).baremes;
  if (!baremes?.length) return <RatesComplexObject obj={configData} />;

  return (
    <Accordion type="multiple" defaultValue={[]} className="w-full space-y-1">
      {baremes.map((b) => (
        <AccordionItem key={b.zone} value={b.zone} className={cn(nestedAccordionClass, 'px-3')}>
          <AccordionTrigger className={nestedAccordionTriggerClass}>
            <span className="flex min-w-0 flex-1 items-center justify-between gap-3 pr-1">
              <span className="min-w-0 text-left leading-snug">
                Zone : {formatPasZone(b.zone)}
              </span>
              <span className="w-[6.5rem] shrink-0 text-right text-xs font-normal leading-none text-muted-foreground tabular-nums">
                ({b.tranches.length} tranches)
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="pb-2">
            <Table>
              <TableBody>
                {b.tranches.map((t, i) => (
                  <TableRow key={i} className="border-border/40">
                    <TableCell className="h-auto p-1 py-2 text-muted-foreground">
                      Plafond : {t.plafond ?? '∞'} €
                    </TableCell>
                    <TableCell className="h-auto p-1 py-2 text-right font-medium tabular-nums">
                      <RatesRateValue value={t.taux} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
