import { useState } from 'react';
import { Download, Eye, FileText, Loader2, MoreHorizontal } from 'lucide-react';
import type { AbsenceRequest, SalaryCertificate } from '@/api/absences';
import * as absencesApi from '@/api/absences';
import { log } from '@/lib/logger';
import { requiresSalaryCertificate } from '@/lib/employeeAbsencesUtils';
import { AbsenceCertificateStatusBadge } from '@/components/absences/AbsenceCertificateStatusBadge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/components/ui/use-toast';
import { downloadBlob, openBlobInNewTab } from '@/lib/downloadBlob';

interface EmployeeAbsenceRequestActionsProps {
  absence: AbsenceRequest;
  certificates: Record<string, SalaryCertificate>;
  loadingCertificates: Set<string>;
  onCertificateLoaded: (absenceId: string, cert: SalaryCertificate) => void;
  onCertificateLoading: (absenceId: string, loading: boolean) => void;
}

export function EmployeeAbsenceRequestActions({
  absence,
  certificates,
  loadingCertificates,
  onCertificateLoaded,
  onCertificateLoading,
}: EmployeeAbsenceRequestActionsProps) {
  const { toast } = useToast();

  const loadCertificate = async (): Promise<boolean> => {
    if (certificates[absence.id] || loadingCertificates.has(absence.id)) {
      return Boolean(certificates[absence.id]);
    }
    onCertificateLoading(absence.id, true);
    try {
      const cert = await absencesApi.getSalaryCertificate(absence.id);
      onCertificateLoaded(absence.id, cert.data);
      return true;
    } catch (error: unknown) {
      const err = error as { response?: { status?: number } };
      if (err.response?.status !== 404) {
        log.error('Erreur chargement attestation:', error);
      }
      return false;
    } finally {
      onCertificateLoading(absence.id, false);
    }
  };

  const handleDownloadCertificate = async () => {
    try {
      const blob = await absencesApi.downloadSalaryCertificate(absence.id);
      const cert = certificates[absence.id];
      const filename = cert?.filename || `attestation_salaire_${absence.id}.pdf`;
      downloadBlob(blob, filename);
      toast({
        title: 'Succès',
        description: 'Attestation téléchargée avec succès.',
      });
    } catch (error) {
      log.error('Erreur téléchargement attestation:', error);
      toast({
        title: 'Erreur',
        description: "Impossible de télécharger l'attestation.",
        variant: 'destructive',
      });
    }
  };

  const handleDownloadAttachment = async () => {
    const signedUrl = absence.attachment_url;
    if (!signedUrl) {
      toast({
        title: 'Erreur',
        description: 'Aucun justificatif associé.',
        variant: 'destructive',
      });
      return;
    }
    try {
      const response = await fetch(signedUrl);
      if (!response.ok) throw new Error(`Erreur réseau: ${response.statusText}`);
      const blob = await response.blob();
      downloadBlob(blob, absence.filename || 'justificatif');
    } catch (error) {
      log.error('Erreur téléchargement justificatif:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de lancer le téléchargement.',
        variant: 'destructive',
      });
    }
  };

  const hasAttachment = Boolean(absence.attachment_url);
  const showCertFlow =
    absence.certificate_status === 'generated' ||
    absence.certificate_status === 'pending' ||
    ((absence.certificate_status === undefined ||
      absence.certificate_status === null) &&
      absence.status === 'validated' &&
      requiresSalaryCertificate(absence.type));

  if (!hasAttachment && !showCertFlow) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <AbsenceCertificateStatusBadge
        certificateStatus={absence.certificate_status}
        absenceType={absence.type}
        absenceStatus={absence.status}
        hasCertificateFile={Boolean(certificates[absence.id])}
      />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only sm:inline">Actions</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {hasAttachment && (
            <>
              <DropdownMenuItem asChild>
                <a
                  href={absence.attachment_url!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Eye className="mr-2 h-4 w-4" />
                  Voir le justificatif
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownloadAttachment}>
                <Download className="mr-2 h-4 w-4" />
                Télécharger le justificatif
              </DropdownMenuItem>
            </>
          )}
          {absence.certificate_status === 'generated' && (
            <DropdownMenuItem onClick={handleDownloadCertificate}>
              <FileText className="mr-2 h-4 w-4" />
              Télécharger attestation IJSS
            </DropdownMenuItem>
          )}
          {(absence.certificate_status === undefined ||
            absence.certificate_status === null) &&
            absence.status === 'validated' &&
            requiresSalaryCertificate(absence.type) && (
              <DropdownMenuItem
                onClick={() => {
                  void (async () => {
                    if (certificates[absence.id]) {
                      await handleDownloadCertificate();
                      return;
                    }
                    const ok = await loadCertificate();
                    if (ok) await handleDownloadCertificate();
                  })();
                }}
                disabled={loadingCertificates.has(absence.id)}
              >
                {loadingCertificates.has(absence.id) ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <FileText className="mr-2 h-4 w-4" />
                )}
                {certificates[absence.id]
                  ? 'Télécharger attestation'
                  : 'Charger attestation'}
              </DropdownMenuItem>
            )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Desktop : icônes rapides */}
      <div className="hidden gap-1 sm:flex">
        {hasAttachment && (
          <>
            <Button variant="outline" size="icon" className="h-8 w-8" asChild>
              <a
                href={absence.attachment_url!}
                target="_blank"
                rel="noopener noreferrer"
                title="Voir le justificatif"
              >
                <Eye className="h-4 w-4" />
              </a>
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => void handleDownloadAttachment()}
              title="Télécharger le justificatif"
            >
              <Download className="h-4 w-4" />
            </Button>
          </>
        )}
        {absence.certificate_status === 'generated' && (
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={() => void handleDownloadCertificate()}
            title="Télécharger attestation"
          >
            <FileText className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
