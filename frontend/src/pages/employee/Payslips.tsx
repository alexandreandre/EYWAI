// src/pages/employee/Payslips.tsx (COMPLET, FONCTIONNEL AVEC BACKEND À JOUR)

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Download, BarChart2, Loader2, Euro, CalendarDays, TrendingUp } from 'lucide-react';
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip as RechartsTooltip } from 'recharts';
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/api/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { Label } from '@/components/ui/label';

// --- Interfaces pour les données attendues ---

interface PayslipInfo {
  id: string;
  month: number;
  year: number;
  name: string; // Nom du fichier
  url: string; // URL de téléchargement
  net_a_payer?: number | null; // <-- Champ ajouté pour le graphique
}

interface EmployeeSalaryInfo {
  salaire_de_base?: {
    valeur?: number;
  } | null;
}

interface CumulsData {
  periode?: {
      annee_en_cours?: number;
      dernier_mois_calcule?: number;
  };
  cumuls?: {
      brut_total?: number;
      net_imposable?: number;
      impot_preleve_a_la_source?: number;
      heures_remunerees?: number;
      heures_supplementaires_remunerees?: number;
      // ... autres cumuls si disponibles
  };
}

// --- Fonctions Utilitaires ---

const formatMonthYear = (month: number, year: number) => {
  return new Date(year, month - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' });
};

const formatCurrency = (amount: number | undefined | null): string => {
    if (amount == null || isNaN(amount)) return 'N/A'; // Ajout vérification NaN
    return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
};

// --- Composant Principal ---

export default function PayslipsPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [payslips, setPayslips] = useState<PayslipInfo[]>([]);
  const [salaryInfo, setSalaryInfo] = useState<EmployeeSalaryInfo | null>(null);
  const [cumuls, setCumuls] = useState<CumulsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.id) {
      const fetchRemunerationData = async () => {
        setIsLoading(true);
        setError(null);
        try {
          // Utiliser Promise.allSettled pour gérer les erreurs partielles
          const results = await Promise.allSettled([
            apiClient.get<PayslipInfo[]>(`/api/me/payslips`),
            apiClient.get<EmployeeSalaryInfo>(`/api/employees/${user.id}`),
            // ✅ Appel pour les cumuls activé
            apiClient.get<CumulsData>('/api/me/current-cumuls')
          ]);

          let fetchError = false;

          // Traitement des bulletins
          if (results[0].status === 'fulfilled') {
            // Tri du plus récent au plus ancien
            const sortedPayslips = results[0].value.data.sort((a, b) => {
              if (a.year !== b.year) return b.year - a.year;
              return b.month - a.month;
            });
            setPayslips(sortedPayslips);
            console.log("Bulletins chargés:", sortedPayslips); // Debug
          } else {
            console.error("Erreur chargement bulletins:", results[0].reason);
            fetchError = true;
          }

          // Traitement des infos salaire
          if (results[1].status === 'fulfilled') {
            setSalaryInfo(results[1].value.data);
            console.log("Infos salaire chargées:", results[1].value.data); // Debug
          } else {
            console.error("Erreur chargement infos salaire:", results[1].reason);
            fetchError = true;
          }

          // ✅ Traitement des cumuls activé
          if (results[2].status === 'fulfilled') {
             // Vérifie si la réponse n'est pas juste un objet vide (au cas où la route renvoie {} si rien n'est trouvé)
             const cumulsData = results[2].value.data;
             if (cumulsData && (cumulsData.periode || cumulsData.cumuls)) {
                 setCumuls(cumulsData);
                 console.log("Cumuls chargés:", cumulsData); // Debug
             } else {
                 console.log("Aucun cumul trouvé ou données vides.");
                 setCumuls(null); // Assure la réinitialisation si vide
             }
          } else {
            console.error("Erreur chargement cumuls:", results[2].reason);
            setCumuls(null); // Assure la réinitialisation si erreur
            // Optionnel : Mettre une erreur non bloquante si les cumuls échouent
            // setError(prev => prev ? prev + " Cumuls non chargés." : "Cumuls non chargés.");
          }


          if (fetchError) {
            const currentError = "Certaines informations n'ont pas pu être chargées.";
            setError(currentError);
            toast({ variant: "destructive", title: "Erreur", description: currentError });
          }

        } catch (err) {
          console.error("Erreur globale chargement rémunération:", err);
          const currentError = "Impossible de charger les informations de rémunération.";
          setError(currentError);
          toast({ variant: "destructive", title: "Erreur", description: currentError });
        } finally {
          setIsLoading(false);
        }
      };
      fetchRemunerationData();
    }
  }, [user?.id, toast]);

  // ✅ Données pour le graphique (activées et utilisant net_a_payer)
  const salaryEvolutionData = payslips
    .filter(p => p.net_a_payer != null && !isNaN(p.net_a_payer)) // Filtre pour être sûr
    .slice(0, 6) // Prend les 6 plus récents (déjà triés)
    .map(p => ({
      name: new Date(p.year, p.month - 1).toLocaleString('fr-FR', { month: 'short' }),
      // Utilise la clé 'net_a_payer' retournée par l'API
      Net: p.net_a_payer,
    }))
    .reverse(); // Remet dans l'ordre chronologique pour Recharts

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Ma Rémunération</h1>

      {/* --- Affichage d'Erreur --- */}
      {error && !isLoading && ( // N'affiche l'erreur qu'après le chargement initial
          <Card className="border-destructive bg-destructive/10">
              <CardContent className="pt-6 text-destructive text-sm font-medium">
                  {error}
              </CardContent>
          </Card>
      )}

      {/* --- Section Informations Salariales --- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><Euro className="mr-2 h-5 w-5" />Mon Salaire Actuel</CardTitle>
          <CardDescription>Informations principales de votre rémunération contractuelle.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
             <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Chargement...</div>
          ) : salaryInfo ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">Salaire de base mensuel</Label>
                <p className="text-lg font-semibold">{formatCurrency(salaryInfo.salaire_de_base?.valeur)}</p>
              </div>
              {/* Ajoutez ici d'autres infos salariales si elles sont dans EmployeeSalaryInfo */}
            </div>
          ) : !error ? ( // N'affiche ce message que s'il n'y a pas d'erreur globale
            <p className="text-sm text-muted-foreground">Informations salariales non disponibles.</p>
          ) : null}
        </CardContent>
      </Card>

      {/* --- Section Cumuls Annuels --- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><TrendingUp className="mr-2 h-5 w-5" />Cumuls Annuels</CardTitle>
          <CardDescription>
            {/* Affiche l'année des cumuls si dispo, sinon l'année actuelle */}
            Total de l'année {cumuls?.periode?.annee_en_cours || new Date().getFullYear()}
            {cumuls?.periode?.dernier_mois_calcule
                ? ` (arrêtés fin ${formatMonthYear(cumuls.periode.dernier_mois_calcule, cumuls.periode.annee_en_cours || new Date().getFullYear())})`
                : ' (données non disponibles)'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
             <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Chargement...</div>
          // --- Affichage des cumuls (si disponibles) ---
          ) : cumuls?.cumuls ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-y-4 gap-x-6">
              <div>
                <Label className="text-xs text-muted-foreground">Brut Total</Label>
                <p className="font-semibold">{formatCurrency(cumuls.cumuls.brut_total)}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Net Imposable</Label>
                <p className="font-semibold">{formatCurrency(cumuls.cumuls.net_imposable)}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Impôt Prélevé (PAS)</Label>
                <p className="font-semibold">{formatCurrency(cumuls.cumuls.impot_preleve_a_la_source)}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Heures Rémunérées</Label>
                <p className="font-semibold">{cumuls.cumuls.heures_remunerees?.toFixed(2) ?? 'N/A'} h</p>
              </div>
               <div>
                <Label className="text-xs text-muted-foreground">Heures Supp. Rémunérées</Label>
                <p className="font-semibold">{cumuls.cumuls.heures_supplementaires_remunerees?.toFixed(2) ?? 'N/A'} h</p>
              </div>
              {/* Ajoutez ici d'autres cumuls si présents dans cumuls.cumuls */}
            </div>
          // --- Message si les cumuls ne sont pas disponibles ---
          ) : !error ? ( // N'affiche ce message que s'il n'y a pas d'erreur globale
             <p className="text-sm text-muted-foreground">
                Les cumuls annuels ne sont pas encore disponibles.
             </p>
          ) : null}
        </CardContent>
      </Card>


       {/* --- ✅ Section Graphique (Activée) --- */}
       <Card>
        <CardHeader>
            <CardTitle className="flex items-center"><BarChart2 className="mr-2 h-5 w-5" />Évolution du Net à Payer (6 derniers mois)</CardTitle>
        </CardHeader>
        <CardContent className="h-[250px] w-full">
           {isLoading ? (
            <div className="flex h-full items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div>
           ) : salaryEvolutionData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={salaryEvolutionData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <XAxis dataKey="name" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value.toLocaleString('fr-FR')}€`}
                    width={80} // Donne un peu plus d'espace pour les montants
                 />
                <RechartsTooltip
                    cursor={{ fill: 'hsl(var(--muted))' }}
                    contentStyle={{ backgroundColor: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 'var(--radius)', padding: '8px' }}
                    labelStyle={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}
                    itemStyle={{ fontSize: '12px' }}
                    formatter={(value: number) => [formatCurrency(value), 'Net à payer']} // Formatage dans l'infobulle
                 />
                 {/* Utilise 'Net' comme défini dans salaryEvolutionData */}
                <Bar dataKey="Net" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
           ) : !error ? ( // N'affiche ce message que s'il n'y a pas d'erreur globale
            <p className="text-center text-sm text-muted-foreground pt-16">
                Données indisponibles pour afficher le graphique.
                <br />
                <span className="text-xs">(Vérifiez que les bulletins de paie récents contiennent le montant net à payer)</span>
            </p>
           ) : null}
        </CardContent>
       </Card>

      {/* --- Section Liste des Bulletins --- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><CalendarDays className="mr-2 h-5 w-5" />Mes Bulletins de Paie</CardTitle>
          <CardDescription>Historique de vos bulletins disponibles en téléchargement.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
             <div className="flex items-center justify-center h-24"><Loader2 className="h-6 w-6 animate-spin" /></div>
          ) : payslips.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Période</TableHead>
                  {/* Optionnel: Ajouter colonne Net si besoin */}
                  {/* <TableHead className="text-right">Net à Payer</TableHead> */}
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payslips.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium capitalize">
                        {formatMonthYear(p.month, p.year)}
                    </TableCell>
                    {/* Optionnel: Afficher Net */}
                    {/* <TableCell className="text-right">{formatCurrency(p.net_a_payer)}</TableCell> */}
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" asChild>
                        {/* Utilise le nom de fichier retourné par l'API */}
                        <a href={p.url} download={p.name} title={`Télécharger ${p.name}`}>
                            <Download className="h-4 w-4" />
                        </a>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : !error ? ( // N'affiche ce message que s'il n'y a pas d'erreur globale
             <p className="text-sm text-muted-foreground text-center py-8">Aucun bulletin de paie trouvé.</p>
          ) : null}
        </CardContent>
      </Card>

    </div>
  );
}