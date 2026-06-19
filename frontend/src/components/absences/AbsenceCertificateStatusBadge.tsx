import { Badge } from '@/components/ui/badge';
import { requiresSalaryCertificate } from '@/lib/employeeAbsencesUtils';

interface AbsenceCertificateStatusBadgeProps {
  certificateStatus?: 'generated' | 'not_required' | 'pending' | null;
  absenceType: string;
  absenceStatus: string;
  /** Attestation PDF déjà chargée côté RH (fallback si certificate_status absent). */
  hasCertificateFile?: boolean;
}

export function AbsenceCertificateStatusBadge({
  certificateStatus,
  absenceType,
  absenceStatus,
  hasCertificateFile,
}: AbsenceCertificateStatusBadgeProps) {
  if (!requiresSalaryCertificate(absenceType)) return null;

  if (certificateStatus === 'not_required') return null;

  if (certificateStatus === 'pending') {
    return (
      <Badge className="w-fit border-0 bg-orange-500 text-white hover:bg-orange-500">
        Attestation en cours
      </Badge>
    );
  }

  if (certificateStatus === 'generated' || hasCertificateFile) {
    return (
      <Badge className="w-fit border-0 bg-green-600 text-white hover:bg-green-600">
        Attestation IJSS générée
      </Badge>
    );
  }

  if (absenceStatus === 'validated') {
    return (
      <Badge variant="outline" className="w-fit border-amber-500/50 text-amber-800 dark:text-amber-200">
        Attestation à générer
      </Badge>
    );
  }

  return null;
}
