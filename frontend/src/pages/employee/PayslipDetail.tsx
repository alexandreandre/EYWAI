/**
 * Détail bulletin côté collaborateur : comparaison N-1 et tendance (lecture seule).
 * Route : /employee/payslips/:payslipId
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, Loader2 } from 'lucide-react';
import { getPayslipDetails, type PayslipDetail } from '@/api/payslips';
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
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-5xl space-y-6 py-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button variant="outline" size="sm" asChild>
            <Link to="/payslips">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Retour à ma rémunération
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Mon bulletin — {formatMonthYearFr(payslip.month, payslip.year)}
            </h1>
            <p className="text-sm text-muted-foreground">
              Comparaison avec le mois précédent et tendance sur l’historique (lecture seule).
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href={payslip.url} download={payslip.name}>
            <Download className="mr-2 h-4 w-4" />
            PDF
          </a>
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
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
    </div>
  );
}
