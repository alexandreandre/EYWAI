// frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { previewPayslip } from '@/api/payslips';

interface PayslipPreviewFrameProps {
  payslipId: string;
  data: unknown;
  pdfNotes?: string;
}

export default function PayslipPreviewFrame({
  payslipId,
  data,
  pdfNotes,
}: PayslipPreviewFrameProps) {
  const [html, setHtml] = useState<string>('');
  const [erreur, setErreur] = useState<string>('');
  const [chargement, setChargement] = useState<boolean>(false);

  const rafraichir = useCallback(async () => {
    setChargement(true);
    setErreur('');
    try {
      setHtml(await previewPayslip(payslipId, data, pdfNotes));
    } catch {
      setErreur('Aperçu indisponible pour le moment.');
    } finally {
      setChargement(false);
    }
  }, [payslipId, data, pdfNotes]);

  useEffect(() => {
    void rafraichir();
    // Rendu à l'ouverture de l'onglet ; les modifications suivantes passent par
    // le bouton, pour ne pas appeler le serveur à chaque frappe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Aperçu du bulletin tel qu'il sera généré.
        </p>
        <Button variant="outline" size="sm" onClick={rafraichir} disabled={chargement}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Rafraîchir l'aperçu
        </Button>
      </div>

      {erreur && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{erreur}</AlertDescription>
        </Alert>
      )}

      <iframe
        title="Aperçu du bulletin"
        srcDoc={html}
        sandbox=""
        className="h-[1200px] w-full rounded-md border bg-white"
      />
    </div>
  );
}
