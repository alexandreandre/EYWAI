// frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx

import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { previewPayslip } from '@/api/payslips';
import { cadreDApercu, chargerApercu } from './apercuBulletin';

interface PayslipPreviewFrameProps {
  payslipId: string;
  /** Note du PDF en cours de saisie : seul écart possible avec le bulletin enregistré. */
  pdfNotes?: string;
  /** Société du bulletin, envoyée avec l'appel comme pour les autres lectures du bulletin. */
  companyId?: string | null;
}

export default function PayslipPreviewFrame({
  payslipId,
  pdfNotes,
  companyId,
}: PayslipPreviewFrameProps) {
  const [apercu, setApercu] = useState<{ html: string; version: number }>({
    html: '',
    version: 0,
  });
  const [erreur, setErreur] = useState<string>('');
  const [chargement, setChargement] = useState<boolean>(false);

  // Seule la dernière demande compte : une réponse plus ancienne, ou arrivée
  // après la fermeture de l'onglet, ne remplace rien.
  const derniereDemande = useRef(0);
  useEffect(() => () => void (derniereDemande.current = -1), []);

  const rafraichir = useCallback(async () => {
    const demande = (derniereDemande.current += 1);
    setChargement(true);
    setErreur('');
    const resultat = await chargerApercu(() => previewPayslip(payslipId, pdfNotes, companyId));
    if (derniereDemande.current !== demande) return;
    if ('html' in resultat) {
      setApercu((avant) => ({ html: resultat.html, version: avant.version + 1 }));
    } else {
      // Pas d'ancien aperçu sous un message d'échec : il passerait pour le bulletin à jour.
      setApercu((avant) => ({ html: '', version: avant.version + 1 }));
      setErreur(resultat.erreur);
    }
    setChargement(false);
  }, [payslipId, pdfNotes, companyId]);

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
