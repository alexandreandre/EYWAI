import type { ReactNode } from 'react';

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
  formatEurAmount,
  formatEffectifRange,
  formatHeuresSupPlage,
  formatIsoDateFr,
  formatPayrollPercent,
} from '@/lib/ratesUtils';
import { cn } from '@/lib/utils';

const sectionTitleClass = 'text-sm font-semibold text-foreground';
const sectionHintClass = 'text-xs leading-relaxed text-muted-foreground';
const nestedAccordionClass = 'border-0 bg-muted/20 rounded-md px-2 mb-1';
const nestedAccordionTriggerClass = 'hover:no-underline py-2 text-sm font-medium';

type HeuresSuppMeta = {
  date_doc?: string;
  source_primaire?: string;
};

type MajorationHsRow = {
  taux?: number;
  de_heure?: number;
  a_heure?: number | null;
};

type MajorationHcRow = {
  taux?: number;
  limite?: string;
};

type DeductionPalier = {
  effectif_min?: number;
  effectif_max?: number;
  montant_par_heure_sup_eur?: number;
};

function SectionBlock({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div>
        <h4 className={sectionTitleClass}>{title}</h4>
        {hint ? <p className={cn(sectionHintClass, 'mt-1')}>{hint}</p> : null}
      </div>
      {children}
    </section>
  );
}

function InfoTable({
  rows,
}: {
  rows: { label: string; value: ReactNode; hint?: string }[];
}) {
  if (rows.length === 0) return null;
  return (
    <Table>
      <TableHeader>
        <TableRow className="border-border/40 hover:bg-transparent">
          <TableHead className="h-9 text-xs font-medium text-muted-foreground">
            Élément
          </TableHead>
          <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
            Valeur
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.label} className="border-border/40">
            <TableCell className="py-2.5 align-top">
              <div className="text-sm text-foreground">{row.label}</div>
              {row.hint ? (
                <div className="mt-0.5 text-xs leading-snug text-muted-foreground">{row.hint}</div>
              ) : null}
            </TableCell>
            <TableCell className="py-2.5 text-right align-top text-sm font-semibold tabular-nums text-foreground">
              {row.value}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="list-disc space-y-1 pl-4 text-sm leading-relaxed text-muted-foreground">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function RatesHeuresSuppView({
  configData,
}: {
  configData: Record<string, unknown>;
}) {
  const meta = configData.meta as HeuresSuppMeta | undefined;
  const regles = configData.regles_calcul_communes as
    | {
        taux_majoration_par_defaut?: {
          heures_supplementaires?: MajorationHsRow[];
          heures_complementaires?: MajorationHcRow[];
        };
        determination_salaire_horaire?: string;
      }
    | undefined;
  const reduction = configData.reduction_salariale as
    | {
        libelle?: string;
        fiscalite?: {
          exoneration_ir?: boolean;
          regle_csg_crds?: string;
          limite_annuelle_exoneration_eur?: number;
        };
        base_calcul?: string;
        taux_reduction?: {
          principe?: string;
          plafond_legal?: number;
          taux_specifiques?: Record<string, number>;
        };
        reference_legale?: string;
        conditions?: string[];
        champ_application?: Record<string, string>;
      }
    | undefined;
  const deduction = configData.deduction_patronale as
    | {
        libelle?: string;
        reference_legale?: string;
        champ_application?: string;
        montants_forfaitaires?: DeductionPalier[];
        regle_franchissement_seuil?: string;
      }
    | undefined;
  const rtt = configData.monetisation_rtt as
    | {
        libelle?: string;
        conditions?: string[];
        remuneration?: string;
        traitement_social_fiscal?: string;
        periode_acquisition_jours?: { debut?: string; fin?: string };
      }
    | undefined;

  const hsRows = regles?.taux_majoration_par_defaut?.heures_supplementaires ?? [];
  const hcRows = regles?.taux_majoration_par_defaut?.heures_complementaires ?? [];
  const deductionPaliers = deduction?.montants_forfaitaires ?? [];

  return (
    <div className="space-y-6">
      {meta?.source_primaire ? (
        <p className={sectionHintClass}>
          Référentiel {meta.source_primaire}
          {meta.date_doc ? ` — document du ${formatIsoDateFr(meta.date_doc)}` : ''}.
        </p>
      ) : null}

      <SectionBlock
        title="Majorations de salaire"
        hint="Taux appliqués sur le salaire horaire de base pour rémunérer les heures effectuées au-delà du temps de travail contractuel."
      >
        {hsRows.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">
              Heures supplémentaires (temps plein)
            </p>
            <Table>
              <TableHeader>
                <TableRow className="border-border/40 hover:bg-transparent">
                  <TableHead className="h-9 text-xs font-medium text-muted-foreground">
                    Plage d&apos;heures
                  </TableHead>
                  <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
                    Majoration
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hsRows.map((row, index) => (
                  <TableRow key={index} className="border-border/40">
                    <TableCell className="py-2 text-sm text-muted-foreground">
                      {formatHeuresSupPlage(row.de_heure, row.a_heure)}
                    </TableCell>
                    <TableCell className="py-2 text-right text-sm font-semibold tabular-nums">
                      +{formatPayrollPercent(row.taux)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}

        {hcRows.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">
              Heures complémentaires (temps partiel)
            </p>
            <Table>
              <TableHeader>
                <TableRow className="border-border/40 hover:bg-transparent">
                  <TableHead className="h-9 text-xs font-medium text-muted-foreground">
                    Situation
                  </TableHead>
                  <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
                    Majoration
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hcRows.map((row, index) => (
                  <TableRow key={index} className="border-border/40">
                    <TableCell className="py-2 text-sm text-muted-foreground">
                      {row.limite ?? `Tranche ${index + 1}`}
                    </TableCell>
                    <TableCell className="py-2 text-right text-sm font-semibold tabular-nums">
                      +{formatPayrollPercent(row.taux)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}

        {regles?.determination_salaire_horaire ? (
          <p className={cn(sectionHintClass, 'rounded-md bg-muted/20 p-2')}>
            <span className="font-medium text-foreground">Base horaire : </span>
            {regles.determination_salaire_horaire}
          </p>
        ) : null}
      </SectionBlock>

      <SectionBlock
        title="Réduction de cotisations salariales"
        hint="Allègement appliqué sur la rémunération des heures supplémentaires et complémentaires éligibles."
      >
        <InfoTable
          rows={[
            {
              label: 'Taux de réduction (plafond légal)',
              hint: reduction?.taux_reduction?.principe,
              value: formatPayrollPercent(reduction?.taux_reduction?.plafond_legal),
            },
            {
              label: 'Plafond d’exonération fiscale',
              hint: 'Montant annuel maximum exonéré d’impôt sur le revenu',
              value: reduction?.fiscalite?.limite_annuelle_exoneration_eur != null
                ? `${formatEurAmount(reduction.fiscalite.limite_annuelle_exoneration_eur)} / an`
                : '—',
            },
            {
              label: 'Exonération d’impôt sur le revenu',
              value: reduction?.fiscalite?.exoneration_ir ? 'Oui' : 'Non',
            },
            {
              label: 'Base de calcul',
              value: reduction?.base_calcul ?? '—',
            },
          ]}
        />
        {reduction?.fiscalite?.regle_csg_crds ? (
          <p className={sectionHintClass}>{reduction.fiscalite.regle_csg_crds}</p>
        ) : null}
        {reduction?.conditions?.length ? (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Conditions</p>
            <BulletList items={reduction.conditions} />
          </div>
        ) : null}
        {reduction?.champ_application &&
        Object.keys(reduction.champ_application).length > 0 ? (
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="reduction-champs" className={nestedAccordionClass}>
              <AccordionTrigger className={nestedAccordionTriggerClass}>
                Champs d&apos;application par type de contrat
              </AccordionTrigger>
              <AccordionContent className="px-2 pb-3">
                <InfoTable
                  rows={[
                    {
                      label: 'Temps plein',
                      value: reduction.champ_application.temps_plein ?? '—',
                    },
                    {
                      label: 'Temps partiel',
                      value: reduction.champ_application.temps_partiel ?? '—',
                    },
                    {
                      label: 'Forfait en jours',
                      value: reduction.champ_application.forfait_jours ?? '—',
                    },
                    {
                      label: 'Forfait en heures',
                      value: reduction.champ_application.forfait_heures ?? '—',
                    },
                  ]}
                />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        ) : null}
        {reduction?.taux_reduction?.taux_specifiques ? (
          <InfoTable
            rows={[
              ...(reduction.taux_reduction.taux_specifiques.mayotte != null
                ? [
                    {
                      label: 'Taux Mayotte',
                      value: formatPayrollPercent(reduction.taux_reduction.taux_specifiques.mayotte),
                    },
                  ]
                : []),
              ...(reduction.taux_reduction.taux_specifiques.saint_pierre_et_miquelon != null
                ? [
                    {
                      label: 'Taux Saint-Pierre-et-Miquelon',
                      value: formatPayrollPercent(
                        reduction.taux_reduction.taux_specifiques.saint_pierre_et_miquelon,
                      ),
                    },
                  ]
                : []),
            ]}
          />
        ) : null}
        {reduction?.reference_legale ? (
          <p className="text-xs text-muted-foreground">
            Référence légale : {reduction.reference_legale}
          </p>
        ) : null}
      </SectionBlock>

      <SectionBlock
        title="Déduction forfaitaire patronale"
        hint="Montant déduit des cotisations patronales par heure supplémentaire, selon l’effectif de l’entreprise."
      >
        {deductionPaliers.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow className="border-border/40 hover:bg-transparent">
                <TableHead className="h-9 text-xs font-medium text-muted-foreground">
                  Effectif entreprise
                </TableHead>
                <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
                  Déduction
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deductionPaliers.map((palier, index) => (
                <TableRow key={index} className="border-border/40">
                  <TableCell className="py-2 text-sm text-muted-foreground">
                    {formatEffectifRange(palier.effectif_min, palier.effectif_max)}
                  </TableCell>
                  <TableCell className="py-2 text-right text-sm font-semibold tabular-nums">
                    {palier.montant_par_heure_sup_eur != null
                      ? `${formatEurAmount(palier.montant_par_heure_sup_eur)} / heure sup.`
                      : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : null}
        {deduction?.champ_application ? (
          <p className={sectionHintClass}>{deduction.champ_application}</p>
        ) : null}
        {deduction?.regle_franchissement_seuil ? (
          <p className={cn(sectionHintClass, 'rounded-md bg-muted/20 p-2')}>
            {deduction.regle_franchissement_seuil}
          </p>
        ) : null}
        {deduction?.reference_legale ? (
          <p className="text-xs text-muted-foreground">
            Référence légale : {deduction.reference_legale}
          </p>
        ) : null}
      </SectionBlock>

      {rtt ? (
        <Accordion type="single" collapsible className="w-full">
          <AccordionItem value="rtt" className={cn(nestedAccordionClass, 'px-3')}>
            <AccordionTrigger className={nestedAccordionTriggerClass}>
              <span className="flex min-w-0 flex-col items-start text-left">
                <span>Monétisation des jours de RTT</span>
                <span className="text-xs font-normal text-muted-foreground">
                  Dispositif temporaire — informations complémentaires
                </span>
              </span>
            </AccordionTrigger>
            <AccordionContent className="space-y-3 pb-3">
              {rtt.periode_acquisition_jours ? (
                <InfoTable
                  rows={[
                    {
                      label: 'Période du dispositif',
                      value: `${formatIsoDateFr(rtt.periode_acquisition_jours.debut)} → ${formatIsoDateFr(rtt.periode_acquisition_jours.fin)}`,
                    },
                  ]}
                />
              ) : null}
              {rtt.conditions?.length ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Conditions</p>
                  <BulletList items={rtt.conditions} />
                </div>
              ) : null}
              {rtt.remuneration ? (
                <p className={sectionHintClass}>
                  <span className="font-medium text-foreground">Rémunération : </span>
                  {rtt.remuneration}
                </p>
              ) : null}
              {rtt.traitement_social_fiscal ? (
                <p className={sectionHintClass}>
                  <span className="font-medium text-foreground">Traitement social et fiscal : </span>
                  {rtt.traitement_social_fiscal}
                </p>
              ) : null}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      ) : null}
    </div>
  );
}
