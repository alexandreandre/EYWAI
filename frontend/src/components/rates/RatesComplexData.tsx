import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';
import { formatRateKey } from '@/lib/ratesUtils';
import { RatesRateValue } from '@/components/rates/RatesRateValue';

const MAX_DEPTH = 4;
const ACCORDION_MIN_KEYS = 2;

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
        {Object.entries(obj).map(([k, v]) => (
          <TableRow key={k}>
            <TableCell className="p-1 h-auto text-muted-foreground">{formatRateKey(k)}</TableCell>
            <TableCell className="p-1 h-auto text-right font-bold text-lg text-foreground">
              {String(v)}
              {unit ? ` ${unit}` : ''}
            </TableCell>
          </TableRow>
        ))}
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
        return (
          <AccordionItem key={value} value={value} className="border rounded-md px-2 mb-1">
            <AccordionTrigger className="hover:no-underline py-2 text-sm font-medium">
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
            <div className="font-medium text-xs text-muted-foreground uppercase">{title}</div>
          )}
          <Accordion type="multiple" defaultValue={[]} className="w-full">
            {obj.map((item, index) => (
              <AccordionItem
                key={index}
                value={`${title || 'item'}-${index}`}
                className="border rounded-md px-2 mb-1"
              >
                <AccordionTrigger className="hover:no-underline py-2 text-sm">
                  Élément {index + 1}
                </AccordionTrigger>
                <AccordionContent className="pb-2">
                  <RatesComplexObject obj={item} depth={depth + 1} />
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      );
    }
    return (
      <div className="space-y-2">
        {title && (
          <div className="font-medium text-xs text-muted-foreground uppercase">{title}</div>
        )}
        {obj.map((item, index) => (
          <div key={index} className="border rounded-md p-2">
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
            <TableRow key={k}>
              <TableCell className="p-1 text-xs text-muted-foreground">{formatRateKey(k)}</TableCell>
              <TableCell className="p-1 text-right text-sm">
                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
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
            <div className="font-medium text-xs text-muted-foreground uppercase mb-1">{title}</div>
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
          <div className="font-medium text-xs text-muted-foreground uppercase">{title}</div>
        )}
        {primitiveEntries.length > 0 && (
          <Table>
            <TableBody>
              {primitiveEntries.map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell className="p-1 text-xs text-muted-foreground">
                    {formatRateKey(k)}
                  </TableCell>
                  <TableCell className="p-1 text-right text-sm font-medium">{String(v)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
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

  return <span className="font-medium">{String(obj)}</span>;
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
        <AccordionItem key={b.zone} value={b.zone} className="border rounded-lg px-2">
          <AccordionTrigger className="py-2 font-medium hover:no-underline">
            Zone : {b.zone.replaceAll('_', ' ')}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              ({b.tranches.length} tranches)
            </span>
          </AccordionTrigger>
          <AccordionContent className="pb-2">
            <Table>
              <TableBody>
                {b.tranches.map((t, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-muted-foreground p-1 h-auto">
                      Plafond : {t.plafond ?? '∞'} €
                    </TableCell>
                    <TableCell className="text-right font-medium p-1 h-auto">
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
