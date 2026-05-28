import { Fragment, type RefObject } from 'react';
import type { AbsenceRequest, SalaryCertificate } from '@/api/absences';
import {
  MaintenancePreviewBlock,
  ABSENCE_TYPES_MAINTIEN_PREVIEW,
} from '@/components/absences/MaintenancePreviewBlock';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ABSENCE_STATUS_FILTERS,
  type AbsenceStatusFilter,
  formatAbsenceCreatedAt,
  formatAbsenceDateRange,
  getAbsenceTypeLabel,
  getWorkflowStepLabel,
} from '@/lib/employeeAbsencesUtils';
import { EmployeeAbsenceRequestActions } from './EmployeeAbsenceRequestActions';
import { EmployeeAbsenceStatusBadge } from './EmployeeAbsenceStatusBadge';

interface EmployeeAbsenceRequestsSectionProps {
  absences: AbsenceRequest[];
  statusFilter: AbsenceStatusFilter;
  onStatusFilterChange: (filter: AbsenceStatusFilter) => void;
  certificates: Record<string, SalaryCertificate>;
  loadingCertificates: Set<string>;
  onCertificateLoaded: (absenceId: string, cert: SalaryCertificate) => void;
  onCertificateLoading: (absenceId: string, loading: boolean) => void;
  listRef?: RefObject<HTMLDivElement | null>;
}

function RequestMeta({ absence }: { absence: AbsenceRequest }) {
  const workflowLabel = getWorkflowStepLabel(absence.workflow_step);
  const daysCount = absence.selected_days?.length ?? 0;
  const joursPayesNote =
    absence.type === 'conge_paye' &&
    absence.jours_payes != null &&
    absence.jours_payes !== daysCount
      ? ` · ${absence.jours_payes} j. payés`
      : '';

  return (
    <>
      <p className="text-sm text-muted-foreground">
        {formatAbsenceDateRange(absence.selected_days)}
        {daysCount > 0 && (
          <span className="text-muted-foreground/80">
            {' '}
            ({daysCount} j.{joursPayesNote})
          </span>
        )}
      </p>
      {absence.created_at && (
        <p className="text-xs text-muted-foreground">
          Déposée le {formatAbsenceCreatedAt(absence.created_at)}
        </p>
      )}
      {workflowLabel && absence.status === 'pending' && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {workflowLabel}
        </p>
      )}
      {absence.status === 'rejected' && absence.manager_rejection_reason && (
        <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-xs text-destructive">
          Motif du refus : {absence.manager_rejection_reason}
        </p>
      )}
      {absence.comment && (
        <p className="mt-1 text-xs italic text-muted-foreground">
          {absence.comment}
        </p>
      )}
    </>
  );
}

function MaintenanceAccordion({ absence }: { absence: AbsenceRequest }) {
  if (!ABSENCE_TYPES_MAINTIEN_PREVIEW.has(absence.type)) return null;
  return (
    <Accordion type="single" collapsible className="mt-2 w-full">
      <AccordionItem value="maintien" className="border-0">
        <AccordionTrigger className="py-2 text-sm hover:no-underline">
          Détail maintien de salaire
        </AccordionTrigger>
        <AccordionContent>
          <MaintenancePreviewBlock
            absenceId={absence.id}
            arretType={absence.arret_type ?? null}
          />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function EmployeeAbsenceRequestsSection({
  absences,
  statusFilter,
  onStatusFilterChange,
  certificates,
  loadingCertificates,
  onCertificateLoaded,
  onCertificateLoading,
  listRef,
}: EmployeeAbsenceRequestsSectionProps) {
  return (
    <div ref={listRef}>
      <Card>
      <CardHeader className="space-y-3">
        <CardTitle>Mes demandes</CardTitle>
        <div className="flex flex-wrap gap-2">
          {ABSENCE_STATUS_FILTERS.map(({ value, label }) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={statusFilter === value ? 'default' : 'outline'}
              onClick={() => onStatusFilterChange(value)}
            >
              {label}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {absences.length === 0 ? (
          <p className="flex h-24 items-center justify-center text-center text-sm text-muted-foreground">
            Aucune demande pour ce filtre.
          </p>
        ) : (
          <>
            <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Période</TableHead>
                    <TableHead className="text-center">Jours</TableHead>
                    <TableHead className="text-right">Statut</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {absences.map((a) => (
                    <Fragment key={a.id}>
                      <TableRow className="align-top">
                        <TableCell className="font-medium">
                          {getAbsenceTypeLabel(a)}
                        </TableCell>
                        <TableCell>
                          <RequestMeta absence={a} />
                        </TableCell>
                        <TableCell className="text-center">
                          {a.selected_days?.length ?? 0}
                        </TableCell>
                        <TableCell className="text-right">
                          <EmployeeAbsenceStatusBadge status={a.status} />
                        </TableCell>
                        <TableCell className="text-right">
                          <EmployeeAbsenceRequestActions
                            absence={a}
                            certificates={certificates}
                            loadingCertificates={loadingCertificates}
                            onCertificateLoaded={onCertificateLoaded}
                            onCertificateLoading={onCertificateLoading}
                          />
                        </TableCell>
                      </TableRow>
                      {ABSENCE_TYPES_MAINTIEN_PREVIEW.has(a.type) && (
                        <TableRow>
                          <TableCell colSpan={5} className="bg-muted/30 pt-0">
                            <MaintenanceAccordion absence={a} />
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>

            <ul className="space-y-3 md:hidden">
              {absences.map((a) => (
                <li key={a.id} className="space-y-2 rounded-md border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{getAbsenceTypeLabel(a)}</p>
                      <RequestMeta absence={a} />
                    </div>
                    <EmployeeAbsenceStatusBadge status={a.status} />
                  </div>
                  <EmployeeAbsenceRequestActions
                    absence={a}
                    certificates={certificates}
                    loadingCertificates={loadingCertificates}
                    onCertificateLoaded={onCertificateLoaded}
                    onCertificateLoading={onCertificateLoading}
                  />
                  <MaintenanceAccordion absence={a} />
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
    </div>
  );
}
