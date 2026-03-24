// Fichier : src/pages/employee/Absences.tsx (VERSION COMPLÈTE ET FINALE)

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Badge } from '@/components/ui/badge';
import { useState, useEffect, useCallback } from 'react';
import { PlusCircle, CheckCircle, Clock, Loader2, CircleX, Download, Eye, FileText } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AbsenceRequestModal } from '@/components/AbsenceRequestModal';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import * as absencesApi from '@/api/absences';
import * as absencesApiFunctions from '@/api/absences';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import type { DayPicker } from 'react-day-picker';
import apiClient from '@/api/apiClient';

type AbsenceRequest = absencesApi.AbsenceRequest;

const calendarLegend = {
  aujourdhui: { label: "Aujourd'hui", color: 'border-2 border-primary' },
  conge: { label: 'Congé / RTT', color: 'bg-blue-500', textColor: 'text-white' },
  arret_maladie: { label: 'Arrêt maladie', color: 'bg-orange-400', textColor: 'text-white' },
  ferie: { label: 'Jour férié', color: 'bg-green-500', textColor: 'text-white' },
  weekend: { label: 'Weekend', color: 'bg-gray-200 dark:bg-gray-700', textColor: 'text-muted-foreground' },
};
type CalendarDayType = keyof typeof calendarLegend;

export default function AbsencesPage() {
  const { user } = useAuth();
  const { toast } = useToast();

  // --- ÉTATS SIMPLIFIÉS ---
  const [balances, setBalances] = useState<absencesApi.AbsenceBalance[]>([]);
  const [calendarDays, setCalendarDays] = useState<absencesApi.CalendarDay[]>([]);
  const [myAbsences, setMyAbsences] = useState<AbsenceRequest[]>([]);
  const [certificates, setCertificates] = useState<Record<string, absencesApi.SalaryCertificate>>({});
  const [loadingCertificates, setLoadingCertificates] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEvenementFamilialModalOpen, setIsEvenementFamilialModalOpen] = useState(false);
  const [evenementFamilialEvents, setEvenementFamilialEvents] = useState<absencesApi.EvenementFamilialEvent[]>([]);
  const [isLoadingEvenementFamilial, setIsLoadingEvenementFamilial] = useState(false);

  // --- UNE SEULE FONCTION DE FETCH ---
  const fetchPageData = useCallback(async (date: Date) => {
    if (!user?.id) return;
    setIsLoading(true);
    try {
      const year = date.getFullYear();
      const month = date.getMonth() + 1;

      // On utilise apiClient avec l'URL relative (qui sera en HTTPS)
      const url = `/api/absences/employees/me/page-data?year=${year}&month=${month}`;
      const response = await apiClient.get<absencesApi.AbsencePageData>(url);

      setBalances(response.data.balances);
      setCalendarDays(response.data.calendar_days);
      setMyAbsences(response.data.history);
      
    } catch (error) {
      // Utilisation directe de toast sans dépendance dans useCallback
      toast({ title: "Erreur", description: "Impossible de charger les données.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]); // Suppression de la dépendance toast

  // --- UN SEUL USE EFFECT ---
  useEffect(() => {
    fetchPageData(currentMonth);
  }, [fetchPageData, currentMonth]);

  // --- LOGIQUE CALENDRIER ---
  const today = new Date();
  
  // --- CORRECTION : Générer un calendrier par défaut si les données sont vides ---
  const getCalendarModifiers = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();

    // Si le calendrier de la BDD est vide, on génère un calendrier par défaut avec seulement les week-ends
    if (calendarDays.length === 0) {
      const weekends: Date[] = [];
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month, day);
        if (date.getDay() === 0 || date.getDay() === 6) { // 0 = Dimanche, 6 = Samedi
          weekends.push(date);
        }
      }
      return { weekend: weekends, aujourdhui: [today] };
    }

    // Sinon, on utilise les données de la BDD comme avant
    return calendarDays.reduce((acc, day) => {
      const type = day.type as CalendarDayType;
      if (!acc[type]) acc[type] = [];
      acc[type].push(new Date(year, month, day.jour));
      return acc;
    }, {} as Record<CalendarDayType, Date[]>);
  };

  const modifiers = getCalendarModifiers();
  modifiers.aujourdhui = [today];

  // --- FONCTIONS UTILITAIRES ---
  const typeLabels: Record<AbsenceRequest['type'], string> = { 
    'conge_paye': 'Congé payé', 
    'rtt': 'RTT', 
    'sans_solde': 'Congé sans solde', 
    'repos_compensateur': 'Repos compensateur', 
    'evenement_familial': 'Événement familial',
    'arret_maladie': 'Arrêt maladie',
    'arret_at': 'Accident du travail',
    'arret_paternite': 'Congé paternité',
    'arret_maternite': 'Congé maternité',
    'arret_maladie_pro': 'Maladie professionnelle'
  };
  const evenementFamilialLabels: Record<string, string> = {
    mariage_salarie: 'Mariage du collaborateur', pacs_salarie: 'PACS du collaborateur', mariage_enfant: 'Mariage d\'un enfant',
    naissance_adoption: 'Naissance ou adoption', deces_conjoint: 'Décès du conjoint', deces_enfant: 'Décès d\'un enfant',
    deces_pere_mere: 'Décès parent', deces_frere_soeur: 'Décès frère/sœur', deces_beaux_parents: 'Décès beaux-parents',
    deces_grands_parents: 'Décès grands-parents', annonce_handicap_enfant: 'Annonce handicap enfant', demenagement: 'Déménagement',
  };
  const getStatusBadge = (status: string) => {
    if (status === 'validated') return <Badge variant="success"><CheckCircle className="mr-1 h-3 w-3"/>Validée</Badge>;
    if (status === 'rejected') return <Badge variant="destructive"><CircleX className="mr-1 h-3 w-3"/>Rejetée</Badge>;
    return <Badge variant="secondary"><Clock className="mr-1 h-3 w-3"/>En attente</Badge>;
  };
  const renderDates = (days: string[]) => {
    const count = days.length;
    if (count === 0) return 'N/A';
    const sortedDays = days.map(d => new Date(d)).sort((a, b) => a.getTime() - b.getTime());
    const formattedDays = sortedDays.map(d => d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }));
    return (
      <TooltipProvider>
        <Tooltip><TooltipTrigger>
            <span className="underline decoration-dashed cursor-help">{count} jour{count > 1 ? 's' : ''}</span>
        </TooltipTrigger><TooltipContent><p>{formattedDays.join(', ')}</p></TooltipContent></Tooltip>
      </TooltipProvider>
    );
  };

  const handleOpenEvenementFamilialModal = () => {
    setIsEvenementFamilialModalOpen(true);
    setIsLoadingEvenementFamilial(true);
    absencesApi.getEvenementsFamiliaux()
      .then((res) => setEvenementFamilialEvents(res.data.events || []))
      .catch(() => setEvenementFamilialEvents([]))
      .finally(() => setIsLoadingEvenementFamilial(false));
  };

  const requiresCertificate = (type: string) => {
    return ['arret_maladie', 'arret_at', 'arret_paternite', 'arret_maternite', 'arret_maladie_pro'].includes(type);
  };

  const loadCertificate = async (absenceId: string) => {
    if (certificates[absenceId] || loadingCertificates.has(absenceId)) return;
    
    setLoadingCertificates(prev => new Set(prev).add(absenceId));
    try {
      const cert = await absencesApiFunctions.getSalaryCertificate(absenceId);
      setCertificates(prev => ({ ...prev, [absenceId]: cert.data }));
    } catch (error: any) {
      if (error.response?.status !== 404) {
        console.error('Erreur chargement attestation:', error);
      }
    } finally {
      setLoadingCertificates(prev => {
        const next = new Set(prev);
        next.delete(absenceId);
        return next;
      });
    }
  };

  const handleDownloadCertificate = async (absenceId: string) => {
    try {
      const blob = await absencesApiFunctions.downloadSalaryCertificate(absenceId);
      const cert = certificates[absenceId];
      const filename = cert?.filename || `attestation_salaire_${absenceId}.pdf`;
      
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast({ title: 'Succès', description: 'Attestation téléchargée avec succès.' });
    } catch (error) {
      console.error('Erreur téléchargement attestation:', error);
      toast({ title: 'Erreur', description: 'Impossible de télécharger l\'attestation.', variant: 'destructive' });
    }
  };

  const handleDownload = async (absence: AbsenceRequest) => {
    const signedUrl = absence.attachment_url;
    if (!signedUrl) {
      toast({ title: "Erreur", description: "Aucun justificatif associé.", variant: "destructive" });
      return;
    }

    try {
      const response = await fetch(signedUrl);
      if (!response.ok) {
        throw new Error(`Erreur réseau: ${response.statusText}`);
      }
      const blob = await response.blob();

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = absence.filename || "justificatif";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Erreur lors de la tentative de téléchargement:", error);
      toast({ title: "Erreur", description: "Impossible de lancer le téléchargement.", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Congés & Absences</h1>
        <Button onClick={() => setIsModalOpen(true)}><PlusCircle className="mr-2 h-4 w-4" /> Faire une demande</Button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader><CardTitle>Mes Soldes</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center border-b pb-2"><p className="text-sm text-muted-foreground text-left">Type</p><p className="text-sm text-muted-foreground">Pris</p><p className="text-sm font-bold text-primary">Restant</p></div>
              {isLoading ? <div className="flex justify-center items-center h-24"><Loader2 className="h-6 w-6 animate-spin" /></div>
               : balances.map(b => (
                <div key={b.type} className="grid grid-cols-3 gap-4 text-center mt-2 p-2 rounded hover:bg-muted items-center">
                  <p className="font-medium text-left">{b.type}</p>
                  <p className="text-muted-foreground">{b.taken} j</p>
                  {b.type === 'Événement familial' ? (
                    <Button
                      variant="link"
                      className="font-bold text-xl h-auto p-0 text-primary hover:underline"
                      onClick={handleOpenEvenementFamilialModal}
                    >
                      Voir
                    </Button>
                  ) : (
                    <p className="font-bold text-xl">{typeof b.remaining === 'string' ? b.remaining : `${b.remaining} j`}</p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Mes Demandes Récentes</CardTitle></CardHeader>
            <CardContent>
              {isLoading ? <div className="flex justify-center items-center h-24"><Loader2 className="h-6 w-6 animate-spin" /></div>
               : myAbsences.length > 0 ? (
                <ul className="space-y-3">{myAbsences.map(a => (
                    <li key={a.id} className="p-3 rounded-md border">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <p className="font-medium">{a.type === 'evenement_familial' && a.event_subtype ? `Événement familial - ${evenementFamilialLabels[a.event_subtype] ?? a.event_subtype}` : typeLabels[a.type]}</p>
                          <p className="text-sm text-muted-foreground">{renderDates(a.selected_days)}</p>
                          {a.comment && <p className="text-xs text-muted-foreground mt-1 italic">{a.comment}</p>}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex gap-1">
                            {a.attachment_url && (
                              <>
                                <Button variant="outline" size="icon" className="h-8 w-8" asChild>
                                  <a href={a.attachment_url} target="_blank" rel="noopener noreferrer" title="Voir le justificatif">
                                    <Eye className="h-4 w-4" />
                                  </a>
                                </Button>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  className="h-8 w-8"
                                  onClick={() => handleDownload(a)}
                                  title="Télécharger le justificatif"
                                >
                                  <Download className="h-4 w-4" />
                                </Button>
                              </>
                            )}
                            {a.status === 'validated' && requiresCertificate(a.type) && (
                              <>
                                {loadingCertificates.has(a.id) ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : certificates[a.id] ? (
                                  <Button
                                    variant="outline"
                                    size="icon"
                                    className="h-8 w-8"
                                    onClick={() => handleDownloadCertificate(a.id)}
                                    title="Télécharger l'attestation de salaire"
                                  >
                                    <FileText className="h-4 w-4" />
                                  </Button>
                                ) : (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8"
                                    onClick={() => loadCertificate(a.id)}
                                    title="Charger l'attestation"
                                  >
                                    <FileText className="h-4 w-4" />
                                  </Button>
                                )}
                              </>
                            )}
                          </div>
                          {getStatusBadge(a.status)}
                        </div>
                      </div>
                    </li>))}
                </ul>
              ) : <p className="text-center text-sm text-muted-foreground h-24 flex items-center justify-center">Aucune demande récente.</p>}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Calendrier</CardTitle></CardHeader>
          <CardContent className="flex flex-col items-center">
            {isLoading && <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10 rounded-lg"><Loader2 className="h-6 w-6 animate-spin" /></div>}
            <Calendar
              mode="single" month={currentMonth} onMonthChange={setCurrentMonth} className="rounded-md border p-0" weekStartsOn={1} modifiers={modifiers}
              modifiersClassNames={{
                  aujourdhui: 'border-2 border-primary rounded-md !bg-transparent text-primary', conge: 'bg-blue-500 text-white rounded-md',
                  arret_maladie: 'bg-orange-400 text-white rounded-md', ferie: 'bg-green-500 text-white rounded-md',
                  weekend: 'text-muted-foreground opacity-80', travail: 'font-semibold',
              }}
            />
            <div className="w-full mt-4 space-y-2 border-t pt-4">{Object.entries(calendarLegend).map(([key, { label, color }]) => (
                <div key={key} className="flex items-center text-sm"><span className={`w-4 h-4 rounded-full mr-2 ${color}`}></span><span>{label}</span></div>
            ))}</div>
          </CardContent>
        </Card>
      </div>

      <AbsenceRequestModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onSuccess={() => fetchPageData(currentMonth)} balances={balances} />

      <Dialog open={isEvenementFamilialModalOpen} onOpenChange={setIsEvenementFamilialModalOpen}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader className="flex-shrink-0">
            <DialogTitle>Événements familiaux – Jours restants</DialogTitle>
          </DialogHeader>
          {isLoadingEvenementFamilial ? (
            <div className="flex justify-center py-8"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
          ) : evenementFamilialEvents.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">Aucun événement familial disponible. Assurez-vous que votre convention collective est configurée.</p>
          ) : (
            <div className="overflow-y-auto max-h-[50vh] min-h-0 rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-semibold">Événement</TableHead>
                  <TableHead className="text-right font-semibold">Quota</TableHead>
                  <TableHead className="text-right font-semibold">Pris</TableHead>
                  <TableHead className="text-right font-semibold text-primary">Restant</TableHead>
                  {evenementFamilialEvents.some(ev => (ev.cycles_completed ?? 0) > 0) && (
                    <TableHead className="text-right font-semibold text-muted-foreground">Consommé</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {evenementFamilialEvents.map((ev) => (
                  <TableRow key={ev.code}>
                    <TableCell className="font-medium">{ev.libelle}</TableCell>
                    <TableCell className="text-right text-muted-foreground">{ev.quota} j</TableCell>
                    <TableCell className="text-right text-muted-foreground">{ev.taken} j</TableCell>
                    <TableCell className="text-right font-bold text-primary">{ev.solde_restant} j</TableCell>
                    {(ev.cycles_completed ?? 0) > 0 ? (
                      <TableCell className="text-right text-muted-foreground text-xs">entièrement {ev.cycles_completed}×</TableCell>
                    ) : evenementFamilialEvents.some(e => (e.cycles_completed ?? 0) > 0) ? (
                      <TableCell className="text-right text-muted-foreground/50">—</TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}