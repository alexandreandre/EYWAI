/**
 * Détail bulletin côté collaborateur : ce qui a changé et tendance (lecture seule).
 * Route : /employee/payslips/:payslipId
 */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Download } from 'lucide-react';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { getPayslipDetails, type PayslipDetail } from '@/api/payslips';
import {
  EmployeePageBackLink,
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { Button } from '@/components/ui/button';
import { PayslipTrendTab } from '@/components/payslip/PayslipTrendTab';
import { formatMonthYearFr } from '@/components/payslip/PayslipComparisonTab';
import { ComparaisonMoisDernier } from '@/features/payroll/components/ComparaisonMoisDernier';
import { useToast } from '@/components/ui/use-toast';

export default function EmployeePayslipDetail() {
  const { payslipId } = useParams<{ payslipId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [payslip, setPayslip] = useState<PayslipDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!payslipId) {
      navigate('/payslips', { replace: true });
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await getPayslipDetails(payslipId);
        if (!cancelled) setPayslip(data);
      } catch {
        if (!cancelled) {
          toast({
            variant: 'destructive',
            title: 'Erreur',
            description: 'Impossible de charger ce bulletin.',
          });
          navigate('/payslips', { replace: true });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [payslipId, navigate, toast]);

  if (loading || !payslip) {
    return <SharkFinLoader variant="fullPage" label="Chargement du bulletin…" />;
  }

  return (
    <EmployeePageShell>
      <EmployeePageHeader
        back={
          <EmployeePageBackLink to="/payslips" label="Retour à ma rémunération" />
        }
        title={`Mon bulletin — ${formatMonthYearFr(payslip.month, payslip.year)}`}
        description="Ce qui a changé depuis le mois précédent et tendance sur l'historique (lecture seule)."
        actions={
          <Button variant="outline" size="sm" asChild>
            <a href={payslip.url} download={payslip.name}>
              <Download className="mr-2 h-4 w-4" />
              PDF
            </a>
          </Button>
        }
      />

      {/* Les alertes de contrôle de la comparaison N-1 sont un outil de la RH :
          le salarié n'a que « ce qui a changé » et la tendance. */}
      <div className="space-y-4">
        <ComparaisonMoisDernier comparaison={payslip.comparaison_mois_dernier} />
        <PayslipTrendTab
          payslipId={payslip.id}
          referenceYear={payslip.year}
          referenceMonth={payslip.month}
          payslipRowHref={(id) => `/employee/payslips/${id}`}
        />
      </div>
    </EmployeePageShell>
  );
}
