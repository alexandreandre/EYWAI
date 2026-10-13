// frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { previewPayslip } from '@/api/payslips';
import { cadreDApercu } from './apercuBulletin';

interface PayslipPreviewFrameProps {
  payslipId: string;
  /** Note du PDF en cours de saisie : seul écart possible avec le bulletin enregistré. */
  pdfNotes?: string;
}

export default function PayslipPreviewFrame({ payslipId, pdfNotes }: PayslipPreviewFrameProps) {
  const [apercu, setApercu] = useState<{ html: string; version: number }>({
    html: '',
    version: 0,
  });
  const [erreur, setErreur] = useState<string>('');
  const [chargement, setChargement] = useState<boolean>(false);

  const rafraichir = useCallback(async () => {
    setChargement(true);
    setErreur('');
    try {
      const html = await previewPayslip(payslipId, pdfNotes);
      setApercu((avant) => ({ html, version: avant.version + 1 }));
    } catch {
      setErreur('Aperçu indisponible pour le moment.');
    } finally {
      setChargement(false);
    }
  }, [payslipId, pdfNotes]);

  useEffect(() => {
    void rafraichir();
    // Rendu à l'ouverture de l'onglet ; les modifications suivantes passent par
    // le bouton, pour ne pas appeler le serveur à chaque frappe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cadre = cadreDApercu(apercu.html, apercu.version);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Le bulletin enregistré, avec la note en cours de saisie.
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

      {cadre ? (
        <iframe
          key={cadre.cle}
          title="Aperçu du bulletin"
          srcDoc={cadre.srcDoc}
          sandbox=""
          className="h-[1200px] w-full rounded-md border bg-white"
        />
      ) : !erreur ? (
        <p className="rounded-md border bg-muted/30 p-6 text-sm text-muted-foreground">
          Aperçu en cours de chargement…
        </p>
      ) : null}
    </div>
  );
}
