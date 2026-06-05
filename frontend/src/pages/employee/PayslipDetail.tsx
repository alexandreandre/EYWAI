/**
 * Détail bulletin côté collaborateur : comparaison N-1 et tendance (lecture seule).
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PayslipComparisonTab } from '@/components/payslip/PayslipComparisonTab';
import { PayslipTrendTab } from '@/components/payslip/PayslipTrendTab';
import { formatMonthYearFr } from '@/components/payslip/PayslipComparisonTab';
import { useToast } from '@/components/ui/use-toast';

export default function EmployeePayslipDetail() {
  const { payslipId } = useParams<{ payslipId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [payslip, setPayslip] = useState<PayslipDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('comparison');

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
        description="Comparaison avec le mois précédent et tendance sur l'historique (lecture seule)."
        actions={
          <Button variant="outline" size="sm" asChild>
            <a href={payslip.url} download={payslip.name}>
              <Download className="mr-2 h-4 w-4" />
              PDF
            </a>
          </Button>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-1 gap-1 sm:grid-cols-2">
          <TabsTrigger value="comparison">Comparaison N-1</TabsTrigger>
          <TabsTrigger value="trend">Tendance</TabsTrigger>
        </TabsList>
        <TabsContent value="comparison" className="mt-0">
          <PayslipComparisonTab
            payslipId={payslip.id}
            isRH={false}
            onShowTrend={() => setActiveTab('trend')}
          />
        </TabsContent>
        <TabsContent value="trend" className="mt-0">
          <PayslipTrendTab
            payslipId={payslip.id}
            referenceYear={payslip.year}
            referenceMonth={payslip.month}
            payslipRowHref={(id) => `/employee/payslips/${id}`}
          />
        </TabsContent>
      </Tabs>
    </EmployeePageShell>
  );
}
