// frontend/src/pages/employee/Documents.tsx 
import { useState, useEffect } from 'react';
import apiClient from '@/api/apiClient';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { FileText, Download, Loader2, Wallet, HardHat, UserRound, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext'; // Pour afficher le nom

// --- Types de données ---
interface Document {
  id: string;
  name: string;
  url: string;
  date?: string; // Pour les bulletins
}

interface ContractResponse {
  url: string | null;
}

interface PayslipResponse {
  id: string;
  name: string;
  url: string;
  month: number;
  year: number;
}

interface ExpenseResponse {
  id: string;
  date: string;
  type: string;
  receipt_url: string | null;
}

// --- Composant de Ligne ---
const DocumentRow = ({ doc }: { doc: Document }) => {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDownloading(true);
    try {
      // Si l'URL est déjà une URL signée Supabase, l'utiliser directement
      // Sinon, passer par apiClient
      if (doc.url.startsWith('http') && doc.url.includes('supabase')) {
        // URL signée Supabase - télécharger directement
        const response = await fetch(doc.url);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', doc.name.endsWith('.pdf') ? doc.name : `${doc.name}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.parentNode?.removeChild(link);
        window.URL.revokeObjectURL(url);
      } else {
        // URL API - utiliser apiClient
        const response = await apiClient.get(doc.url, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', doc.name.endsWith('.pdf') ? doc.name : `${doc.name}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.parentNode?.removeChild(link);
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error("Erreur lors du téléchargement du document:", error);
      // On pourrait afficher une notification d'erreur ici
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <li className="flex items-center justify-between p-3 rounded-md hover:bg-muted">
      <div className="flex items-center gap-3">
        <FileText className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="font-medium">{doc.name}</p>
          {doc.date && <p className="text-xs text-muted-foreground">{doc.date}</p>}
        </div>
      </div>
      <Button variant="ghost" size="icon" onClick={handleDownload} disabled={isDownloading}>
        {isDownloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
      </Button>
    </li>
  );
};

// --- Composant de Chargement ---
const LoadingSkeleton = () => (
  <div className="flex items-center p-3 space-x-3">
    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    <span className="text-sm text-muted-foreground">Chargement...</span>
  </div>
);

// --- Composant Principal ---
export default function DocumentsPage() {
  const { user } = useAuth();
  const [contract, setContract] = useState<Document | null>(null);
  const [payslips, setPayslips] = useState<Document[]>([]);
  const [receipts, setReceipts] = useState<Document[]>([]);
  const [otherDocuments, setOtherDocuments] = useState<Document[]>([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDocuments = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const [contractRes, payslipsRes, expensesRes, publishedDocsRes] = await Promise.allSettled([
          apiClient.get<ContractResponse>('/api/employees/me/contract'),
          apiClient.get<PayslipResponse[]>('/api/me/payslips'),
          apiClient.get<ExpenseResponse[]>('/api/expenses/me'),
          apiClient.get<Document[]>('/api/employees/me/published-exit-documents'),
        ]);

        // 1. Traiter le contrat
        if (contractRes.status === 'fulfilled' && contractRes.value.data.url) {
          setContract({
            id: 'contract-1',
            name: `Contrat de Travail - ${user?.first_name} ${user?.last_name}.pdf`,
            url: contractRes.value.data.url,
            date: `Signé` // On pourrait ajouter la date d'embauche ici si on la récupérait
          });
        }

        // 2. Traiter les bulletins de paie
        if (payslipsRes.status === 'fulfilled') {
          const formattedPayslips = payslipsRes.value.data.map(p => ({
            id: p.id,
            name: p.name,
            url: p.url,
            date: new Date(p.year, p.month - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })
          }));
          setPayslips(formattedPayslips);
        }

        // 3. Traiter les justificatifs de notes de frais
        if (expensesRes.status === 'fulfilled') {
          const formattedReceipts = expensesRes.value.data
            .filter(exp => exp.receipt_url) // Garder seulement ceux avec un justificatif
            .map(exp => ({
              id: exp.id,
              name: `Justificatif - ${exp.type} (${new Date(exp.date).toLocaleDateString('fr-FR')}).pdf`,
              url: exp.receipt_url!,
              date: `Soumis le ${new Date(exp.date).toLocaleDateString('fr-FR')}`
            }));
          setReceipts(formattedReceipts);
        }

        // 4. Traiter les documents de sortie publiés
        if (publishedDocsRes.status === 'fulfilled') {
          const formattedOtherDocs = publishedDocsRes.value.data.map((doc: any) => ({
            id: doc.id,
            name: doc.name,
            url: doc.url,
            date: doc.date ? new Date(doc.date).toLocaleDateString('fr-FR') : undefined
          }));
          setOtherDocuments(formattedOtherDocs);
        }

        // Gérer les erreurs partielles si nécessaire
        if (contractRes.status === 'rejected' || payslipsRes.status === 'rejected' || expensesRes.status === 'rejected' || publishedDocsRes.status === 'rejected') {
          console.error("Une ou plusieurs requêtes ont échoué:", { contractRes, payslipsRes, expensesRes, publishedDocsRes });
          setError("Erreur lors du chargement de certains documents.");
        }

      } catch (err) {
        console.error("Erreur fatale lors du chargement des documents:", err);
        setError("Impossible de charger les documents.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchDocuments();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Mes Documents</h1>
      <p className="text-muted-foreground">
        Retrouvez ici tous vos documents personnels et ceux de l'entreprise.
      </p>

      {error && (
        <div className="p-4 bg-destructive/10 text-destructive border border-destructive/20 rounded-md flex items-center gap-3">
          <AlertCircle className="h-5 w-5" />
          <p>{error}</p>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        
        {/* --- CARTE "MON CONTRAT" --- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><UserRound className="mr-2 h-5 w-5" />Mon Contrat</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {isLoading ? (
                <LoadingSkeleton />
              ) : contract ? (
                <DocumentRow doc={contract} />
              ) : (
                <li className="p-3 text-sm text-muted-foreground">Aucun contrat trouvé.</li>
              )}
            </ul>
          </CardContent>
        </Card>

        {/* --- ACCORDÉON "MES BULLETINS" --- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><Wallet className="mr-2 h-5 w-5" />Mes Bulletins</CardTitle>
          </CardHeader>
          <CardContent>
            <Accordion type="single" collapsible className="w-full">
              <AccordionItem value="item-1">
                <AccordionTrigger>
                  {isLoading ? 'Chargement...' : `${payslips.length} bulletin(s) disponible(s)`}
                </AccordionTrigger>
                <AccordionContent>
                  {isLoading ? (
                    <LoadingSkeleton />
                  ) : payslips.length > 0 ? (
                    <ul className="space-y-1">
                      {payslips.map(doc => <DocumentRow key={doc.id} doc={doc} />)}
                    </ul>
                  ) : (
                    <p className="p-3 pt-0 text-sm text-muted-foreground">Aucun bulletin de paie disponible.</p>
                  )}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>

        {/* --- ACCORDÉON "MES JUSTIFICATIFS" --- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><HardHat className="mr-2 h-5 w-5" />Mes Justificatifs</CardTitle>
          </CardHeader>
          <CardContent>
            <Accordion type="single" collapsible className="w-full">
              <AccordionItem value="item-1">
                <AccordionTrigger>
                  {isLoading ? 'Chargement...' : `${receipts.length} justificatif(s) trouvé(s)`}
                </AccordionTrigger>
                <AccordionContent>
                  {isLoading ? (
                    <LoadingSkeleton />
                  ) : receipts.length > 0 ? (
                    <ul className="space-y-1">
                      {receipts.map(doc => <DocumentRow key={doc.id} doc={doc} />)}
                    </ul>
                  ) : (
                    <p className="p-3 pt-0 text-sm text-muted-foreground">Aucun justificatif de note de frais.</p>
                  )}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>

        {/* --- ACCORDÉON "AUTRES" --- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center"><FileText className="mr-2 h-5 w-5" />Autres</CardTitle>
          </CardHeader>
          <CardContent>
            <Accordion type="single" collapsible className="w-full">
              <AccordionItem value="item-1">
                <AccordionTrigger>
                  {isLoading ? 'Chargement...' : `${otherDocuments.length} document(s) disponible(s)`}
                </AccordionTrigger>
                <AccordionContent>
                  {isLoading ? (
                    <LoadingSkeleton />
                  ) : otherDocuments.length > 0 ? (
                    <ul className="space-y-1">
                      {otherDocuments.map(doc => <DocumentRow key={doc.id} doc={doc} />)}
                    </ul>
                  ) : (
                    <p className="p-3 pt-0 text-sm text-muted-foreground">Aucun autre document pour le moment.</p>
                  )}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}