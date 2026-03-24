// Fichier : src/pages/Absences.tsx (VERSION COMPLÈTE ET AMÉLIORÉE)

import { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Check, X, Clock, Info, Download, Eye, FilePlus } from "lucide-react";
import apiClient from '@/api/apiClient'; // <-- AJOUTER
import type * as absencesApi from '@/api/absences'; // <-- CHANGER en 'import type'
import * as absencesApiFunctions from '@/api/absences';

type AbsenceRequest = absencesApi.AbsenceRequestWithEmployee;
type AbsenceType = AbsenceRequest['type'];

// --- NOUVEAU : Fonction utilitaire pour regrouper les dates consécutives ---
const groupConsecutiveDates = (dates: Date[]): { start: Date, end: Date }[] => {
  if (dates.length === 0) return [];

  const groups: { start: Date, end: Date }[] = [];
  let currentGroup = { start: dates[0], end: dates[0] };

  for (let i = 1; i < dates.length; i++) {
    const previousDate = currentGroup.end;
    const currentDate = dates[i];
    const expectedNextDate = new Date(previousDate.getTime() + 24 * 60 * 60 * 1000);

    if (currentDate.getTime() === expectedNextDate.getTime()) {
      // Le jour est consécutif, on étend le groupe
      currentGroup.end = currentDate;
    } else {
      // Rupture de la série, on sauvegarde le groupe et on en crée un nouveau
      groups.push(currentGroup);
      currentGroup = { start: currentDate, end: currentDate };
    }
  }

  // Ne pas oublier d'ajouter le dernier groupe
  groups.push(currentGroup);
  return groups;
};


export default function AbsencesPage() {
  const { toast } = useToast();
  const [pending, setPending] = useState<AbsenceRequest[]>([]);
  const [processed, setProcessed] = useState<AbsenceRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [certificates, setCertificates] = useState<Record<string, absencesApi.SalaryCertificate>>({});
  const [loadingCertificates, setLoadingCertificates] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      // On utilise apiClient avec les URL relatives (en HTTPS)
      const [pendingRes, validatedRes, rejectedRes] = await Promise.all([
        apiClient.get<AbsenceRequest[]>(`/api/absences/?status=pending`),
        apiClient.get<AbsenceRequest[]>(`/api/absences/?status=validated`),
        apiClient.get<AbsenceRequest[]>(`/api/absences/?status=rejected`),
      ]);
      setPending(pendingRes.data);
      // On fusionne et trie les demandes traitées (validées et refusées) par date de création
      const allProcessed = [...validatedRes.data, ...rejectedRes.data];
      setProcessed(allProcessed.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (error) {
      toast({ title: "Erreur", description: "Impossible de charger les demandes.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [toast]); // Ajout de 'toast' dans les dépendances

  // Charger les attestations existantes après le chargement des données
  useEffect(() => {
    const validatedRequests = processed.filter(req => req.status === 'validated' && requiresCertificate(req.type));
    for (const req of validatedRequests) {
      if (!certificates[req.id] && !loadingCertificates.has(req.id)) {
        loadCertificate(req.id).catch(() => {
          // Ignorer les erreurs 404 (attestation pas encore générée)
        });
      }
    }
  }, [processed]); // Se déclenche quand les demandes traitées changent
  

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleUpdateStatus = async (id: string, status: 'validated' | 'rejected') => {
    try {
      // On utilise apiClient.patch pour mettre à jour la ressource
      await apiClient.patch(`/api/absences/${id}`, { status: status });
      toast({ title: "Succès", description: "La demande a été mise à jour." });
      fetchData();
    } catch (error) {
      toast({ title: "Erreur", description: "La mise à jour a échoué.", variant: "destructive" });
    }
  };
  const typeLabels: Record<AbsenceType, string> = { 
    'conge_paye': 'Congé Payé', 
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
    mariage_salarie: 'Mariage du collaborateur', pacs_salarie: 'PACS du collaborateur', mariage_enfant: "Mariage d'un enfant",
    naissance_adoption: 'Naissance ou adoption', deces_conjoint: 'Décès du conjoint', deces_enfant: "Décès d'un enfant",
    deces_pere_mere: 'Décès parent', deces_frere_soeur: 'Décès frère/sœur', deces_beaux_parents: 'Décès beaux-parents',
    deces_grands_parents: 'Décès grands-parents', annonce_handicap_enfant: 'Annonce handicap enfant', demenagement: 'Déménagement',
  };
  
  // --- NOUVEAU : Fonction d'affichage intelligente des dates ---
  const renderDates = (days: string[]) => {
    if (!days || days.length === 0) return 'N/A';
    const count = days.length;
    
    const sortedDates = days.map(d => new Date(d)).sort((a, b) => a.getTime() - b.getTime());
    const groups = groupConsecutiveDates(sortedDates);

    const dateOptions: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'numeric' };

    const formattedParts = groups.map(group => {
      const startDateStr = group.start.toLocaleDateString('fr-FR', dateOptions);
      if (group.start.getTime() === group.end.getTime()) {
        return `Le ${startDateStr}`;
      } else {
        const endDateStr = group.end.toLocaleDateString('fr-FR', dateOptions);
        return `Du ${startDateStr} au ${endDateStr}`;
      }
    });

    return (
      <div>
        <p className="font-bold">{count} jour{count > 1 ? 's' : ''} :</p>
        <div className="flex flex-col text-xs text-muted-foreground">
          {formattedParts.map((part, index) => (
            <span key={index}>{part}</span>
          ))}
        </div>
      </div>
    );
  };
  
  // Composant pour afficher le solde restant (inchangé)
  const renderRemainingBalance = (req: AbsenceRequest) => {
    const requestTypeLabel = typeLabels[req.type];
    const balance = req.employee.balances.find(b => b.type === requestTypeLabel);

    if (!balance || balance.remaining === 'N/A' || balance.remaining === 'selon événement') return <span className="text-muted-foreground">{balance?.remaining ?? 'N/A'}</span>;

    const remaining = balance.remaining as number;
    const requestedDaysCount = req.selected_days.length;
    const balanceAfterApproval = remaining - requestedDaysCount;

    const colorClass = balanceAfterApproval < 0 ? "text-destructive" : "text-muted-foreground";

    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>
            <span className={`flex items-center gap-1 ${colorClass}`}>
              <Info className="h-4 w-4" /> {remaining} j
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>Solde actuel : {remaining} j</p>
            <p>Demande : -{requestedDaysCount} j</p>
            <hr className="my-1" />
            <p className={`font-bold ${colorClass}`}>Solde après validation : {balanceAfterApproval} j</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

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

  const handleViewCertificate = async (absenceId: string) => {
    try {
      // Toujours récupérer le PDF en blob et ouvrir une URL objet pour afficher
      // dans le navigateur (visualisation) sans déclencher de téléchargement
      const blob = await absencesApiFunctions.downloadSalaryCertificate(absenceId);
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (error: any) {
      console.error('Erreur ouverture attestation:', error);
      if (error.response?.status === 404) {
        toast({ title: 'Information', description: 'L\'attestation n\'a pas encore été générée pour cet arrêt.', variant: 'default' });
      } else {
        toast({ title: 'Erreur', description: 'Impossible d\'ouvrir l\'attestation.', variant: 'destructive' });
      }
    }
  };

  const handleGenerateCertificate = async (absenceId: string) => {
    try {
      setLoadingCertificates(prev => new Set(prev).add(absenceId));
      await absencesApiFunctions.generateSalaryCertificate(absenceId);
      toast({ title: 'Succès', description: 'Attestation générée avec succès.' });
      // Recharger l'attestation
      await loadCertificate(absenceId);
    } catch (error) {
      console.error('Erreur génération attestation:', error);
      toast({ title: 'Erreur', description: 'Impossible de générer l\'attestation.', variant: 'destructive' });
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
      // Charger l'attestation si elle n'est pas déjà chargée
      if (!certificates[absenceId]) {
        await loadCertificate(absenceId);
      }
      
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
    } catch (error: any) {
      console.error('Erreur téléchargement attestation:', error);
      if (error.response?.status === 404) {
        toast({ 
          title: 'Attestation non trouvée', 
          description: 'L\'attestation n\'existe pas encore. Cliquez sur le bouton de génération pour la créer.',
          variant: 'default'
        });
      } else {
        toast({ title: 'Erreur', description: 'Impossible de télécharger l\'attestation.', variant: 'destructive' });
      }
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

  const renderRequestsTable = (requests: AbsenceRequest[]) => (
    <Table>
      <TableHeader><TableRow>
          <TableHead>Employé</TableHead>
          <TableHead>Type</TableHead>
          <TableHead className="w-[220px]">Demande</TableHead>
          <TableHead>Solde Restant</TableHead>
          <TableHead>Justificatif</TableHead>
          <TableHead>Attestation</TableHead>
          <TableHead className="text-right">Actions</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {requests.map(req => (
          <TableRow key={req.id}>
            <TableCell className="font-medium">
              <div>
                <p>{req.employee.first_name} {req.employee.last_name}</p>
                {req.comment && <p className="text-xs text-muted-foreground italic mt-1">{req.comment}</p>}
              </div>
            </TableCell>
            <TableCell>
              {req.type === 'evenement_familial' && req.event_subtype ? (
                <div>
                  <p>{evenementFamilialLabels[req.event_subtype] ?? req.event_subtype}</p>
                  {(req.event_familial_cycles_consumed ?? 0) > 0 && (
                    <p className="text-xs text-muted-foreground">Consommé entièrement {req.event_familial_cycles_consumed}×</p>
                  )}
                </div>
              ) : (
                typeLabels[req.type]
              )}
            </TableCell>
            <TableCell>{renderDates(req.selected_days)}</TableCell>
            <TableCell>{renderRemainingBalance(req)}</TableCell>
            <TableCell>
              {req.attachment_url && (
                <div className="flex gap-2">
                  <Button variant="outline" size="icon" asChild>
                    <a href={req.attachment_url} target="_blank" rel="noopener noreferrer" title="Voir le justificatif">
                      <Eye className="h-4 w-4" />
                    </a>
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => handleDownload(req)}
                    title="Télécharger le justificatif"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </TableCell>
            <TableCell>
              {req.status === 'validated' && requiresCertificate(req.type) && (
                <div className="flex gap-2">
                  {loadingCertificates.has(req.id) ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : certificates[req.id] ? (
                    <>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={() => handleViewCertificate(req.id)}
                              title="Voir l'attestation de salaire"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>Voir l'attestation de salaire</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={() => handleDownloadCertificate(req.id)}
                              title="Télécharger l'attestation de salaire"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>Télécharger l'attestation de salaire</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </>
                  ) : (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => handleGenerateCertificate(req.id)}
                            title="Générer l'attestation de salaire"
                          >
                            <FilePlus className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Générer l'attestation de salaire</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
              )}
            </TableCell>
            <TableCell className="text-right">
              {req.status === 'pending' ? (
                <div className="flex gap-2 justify-end">
                  <Button size="sm" variant="outline" onClick={() => handleUpdateStatus(req.id, 'rejected')}><X className="mr-2 h-4 w-4" /> Rejeter</Button>
                  <Button size="sm" onClick={() => handleUpdateStatus(req.id, 'validated')}><Check className="mr-2 h-4 w-4" /> Approuver</Button>
                </div>
              ) : (
                <Badge variant={req.status === 'validated' ? 'success' : 'destructive'} className="justify-end">
                  {req.status === 'validated' ? <><Check className="mr-1 h-3 w-3" /> Validée</> : <><X className="mr-1 h-3 w-3" /> Rejetée</>}
                </Badge>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Gestion des Congés & Absences</h1>
      <Tabs defaultValue="pending">
        <TabsList>
          <TabsTrigger value="pending"><Clock className="mr-2 h-4 w-4" /> Demandes en attente <Badge className="ml-2">{pending.length}</Badge></TabsTrigger>
          <TabsTrigger value="processed">Historique</TabsTrigger>
        </TabsList>
        <TabsContent value="pending"><Card><CardHeader><CardTitle>Demandes à valider</CardTitle></CardHeader><CardContent>{isLoading ? <Loader2 className="mx-auto h-8 w-8 animate-spin" /> : renderRequestsTable(pending)}</CardContent></Card></TabsContent>
        <TabsContent value="processed"><Card><CardHeader><CardTitle>Demandes traitées</CardTitle></CardHeader><CardContent>{isLoading ? <Loader2 className="mx-auto h-8 w-8 animate-spin" /> : renderRequestsTable(processed)}</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}