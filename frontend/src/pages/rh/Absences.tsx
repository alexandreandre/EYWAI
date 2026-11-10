// Fichier : src/pages/Absences.tsx (VERSION COMPLÈTE ET AMÉLIORÉE)

import { log } from '@/lib/logger';
import { displayNamePrenomNom } from '@/lib/employeeName';
import { formatQuantiteFr, formatQuotiteJours, quotiteJoursDemande } from '@/lib/employeeAbsencesUtils';
import { RhPageHeader } from '@/components/layout';
import { useState, useEffect, useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { useAbsencesQueries } from '@/hooks/queries/useAbsencesQuery';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { isPayrollFocusActive } from "@/lib/payrollFocus";
import { AbsenceRequestModal } from "@/components/AbsenceRequestModal";
import { Loader2, Check, X, Clock, Info, Download, Eye, ExternalLink, ChevronDown } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import type * as absencesApi from '@/api/absences'; // <-- CHANGER en 'import type'
import * as absencesApiFunctions from '@/api/absences';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { downloadBlob } from '@/lib/downloadBlob';
import {
  MaintenancePreviewBlock,
  ABSENCE_TYPES_MAINTIEN_PREVIEW,
} from '@/components/absences/MaintenancePreviewBlock';
import { AbsenceSignalementBadge } from '@/components/absences/AbsenceSignalementBadge';
import { listerSignalements } from '@/api/exports';
import { AbsenceIjssStatusBadge } from '@/components/absences/AbsenceIjssStatusBadge';
import { getAbsenceIjssStatus } from '@/api/ijssTracking';
import { estArretIjss, libelleDeLaDemande } from '@/lib/employeeAbsencesUtils';
import { LeaveCampaignSection } from '@/features/absences/components/LeaveCampaignSection';
import { LeaveNotificationSettingsPanel } from '@/features/absences/components/LeaveNotificationSettingsPanel';
import { RttYearEndRhSection } from '@/features/absences/components/RttYearEndRhSection';
import {
  bandeauAbsencesDuSalarie,
  lireNatureDuLien,
} from '@/features/payroll/utils/heuresSurArret';
import { estRoleRh } from '@/lib/rolesRh';

type AbsenceRequest = absencesApi.AbsenceRequestWithEmployee;
type AbsenceType = AbsenceRequest['type'];

/** Congés dont les jours se modifient après création (même liste que le serveur). */
const TYPES_CONGE_MODIFIABLES: ReadonlySet<string> = new Set([
  'conge_paye',
  'rtt',
  'jtc',
  'sans_solde',
  'repos_compensateur',
  'recuperation_modulation',
  'evenement_familial',
]);

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


function canShowRhNewAbsenceButton(user: { role?: string; is_super_admin?: boolean } | null): boolean {
  if (!user) return false;
  if (isPlatformAdmin(user)) return true;
  return estRoleRh(user.role);
}

export default function AbsencesPage() {
  const { toast } = useToast();
  const { user } = useAuth();
  const [showArretModal, setShowArretModal] = useState(false);
  const [showLeaveModal, setShowLeaveModal] = useState(false);
  // Congé validé en cours de modification (retour du 10/11).
  const [absenceAModifier, setAbsenceAModifier] = useState<AbsenceRequest | null>(null);
  const absencesQuery = useAbsencesQueries();
  const pending = absencesQuery.pending as AbsenceRequest[];
  const processed = useMemo(() => {
    const all = [
      ...(absencesQuery.validated as AbsenceRequest[]),
      ...(absencesQuery.rejected as AbsenceRequest[]),
    ];
    return all.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, [absencesQuery.validated, absencesQuery.rejected]);
  const isLoading = absencesQuery.isLoading;
  const fetchData = absencesQuery.refetch;
  // Recherche par salarié (demande Gaëlle 07/09) — insensible aux accents.
  const [rechercheSalarie, setRechercheSalarie] = useState('');
  // Lien depuis « Modifier l'arrêt » (heures saisies un jour d'arrêt) : les
  // demandes d'un seul salarié, par son id, sur l'onglet Historique.
  const [searchParams, setSearchParams] = useSearchParams();
  const salarieFiltre = searchParams.get('employee');
  const bandeauSalarie = salarieFiltre
    ? bandeauAbsencesDuSalarie({
        employeeId: salarieFiltre,
        nature: lireNatureDuLien(searchParams.get('nature')),
        chargement: isLoading,
        erreur: absencesQuery.isError,
        nombreDeDemandes: [...pending, ...processed].filter(
          (req) => req.employee_id === salarieFiltre,
        ).length,
      })
    : null;
  const normaliser = (v: string) =>
    v
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  const filtrerParSalarie = (toutes: AbsenceRequest[]) => {
    const requests = salarieFiltre
      ? toutes.filter((req) => req.employee_id === salarieFiltre)
      : toutes;
    const terme = normaliser(rechercheSalarie.trim());
    if (!terme) return requests;
    return requests.filter((req) =>
      normaliser(
        `${req.employee?.first_name ?? ''} ${req.employee?.last_name ?? ''} ${req.employee?.nom_usage ?? ''}`,
      ).includes(terme),
    );
  };
  const [pendingSubrogation, setPendingSubrogation] = useState<Record<string, boolean | undefined>>({});
  const { data: signalements } = useQuery({
    queryKey: ['dsn-signalements'],
    queryFn: listerSignalements,
    staleTime: 60_000,
  });

  const ijssAbsenceIds = useMemo(() => {
    const all = [...pending, ...processed];
    return all
      .filter((r) => r.status === 'validated' && estArretIjss(r.type))
      .map((r) => r.id);
  }, [pending, processed]);

  const ijssStatusQueries = useQueries({
    queries: ijssAbsenceIds.map((id) => ({
      queryKey: ['absence-ijss-status', id],
      queryFn: () => getAbsenceIjssStatus(id),
      staleTime: 30_000,
    })),
  });

  const ijssStatusMap = useMemo(() => {
    const map: Record<string, (typeof ijssStatusQueries)[number]['data']> = {};
    ijssAbsenceIds.forEach((id, index) => {
      const data = ijssStatusQueries[index]?.data;
      if (data) map[id] = data;
    });
    return map;
  }, [ijssAbsenceIds, ijssStatusQueries]);

  const handleUpdateStatus = async (
    id: string,
    status: 'validated' | 'rejected' | 'cancelled',
    subrogationActive?: boolean,
  ) => {
    try {
      await absencesApiFunctions.updateAbsenceRequestStatus(id, status, subrogationActive);
      toast({
        title: "Succès",
        description:
          status === 'cancelled'
            ? "Absence annulée — les jours ont été rendus au planning."
            : "La demande a été mise à jour.",
      });
      fetchData();
    } catch (error) {
      toast({ title: "Erreur", description: "La mise à jour a échoué.", variant: "destructive" });
    }
  };
  const typeLabels: Record<AbsenceType, string> = { 
    'conge_paye': 'Congé Payé', 
    'rtt': 'RTT', 
    'jtc': 'JTC',
    'sans_solde': 'Congé sans solde', 
    'repos_compensateur': 'Repos compensateur',
    'recuperation_modulation': 'Récupération (heures sup)',
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
  const renderDates = (days: string[], demiJournees?: Record<string, string> | null) => {
    if (!days || days.length === 0) return 'N/A';
    const count = quotiteJoursDemande({ selected_days: days, demi_journees: demiJournees });
    
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
        <p className="font-bold">{formatQuotiteJours(count)} jour{count > 1 ? 's' : ''} :</p>
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
    const balanceType =
      req.type === 'conge_paye' ? 'Congés Payés' : typeLabels[req.type];
    const balance = req.employee.balances.find((b) => b.type === balanceType);

    if (!balance || balance.remaining === 'N/A' || balance.remaining === 'selon événement') return <span className="text-muted-foreground">{balance?.remaining ?? 'N/A'}</span>;

    const remaining = balance.remaining as number;
    // Repos compensateur : compteur en HEURES (la demande, elle, est en
    // jours/heures mixtes) — on affiche le solde sans arithmétique de
    // prévision plutôt qu'une soustraction d'unités incompatibles.
    if (req.type === 'repos_compensateur') {
      return (
        <span className="flex items-center gap-1 text-muted-foreground">
          <Info className="h-4 w-4" /> {formatQuantiteFr(remaining, 'h')}
        </span>
      );
    }
    const requestedDaysCount = quotiteJoursDemande(req);
    const balanceAfterApproval = remaining - requestedDaysCount;

    const colorClass = balanceAfterApproval < 0 ? "text-destructive" : "text-muted-foreground";

    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>
            <span className={`flex items-center gap-1 ${colorClass}`}>
              <Info className="h-4 w-4" /> {formatQuantiteFr(remaining, 'j')}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>Solde actuel : {formatQuantiteFr(remaining, 'j')}</p>
            <p>Demande : −{formatQuantiteFr(requestedDaysCount, 'j')}</p>
            <hr className="my-1" />
            <p className={`font-bold ${colorClass}`}>Solde après validation : {formatQuantiteFr(balanceAfterApproval, 'j')}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

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

      downloadBlob(blob, absence.filename || "justificatif");
    } catch (error) {
      log.error("Erreur lors de la tentative de téléchargement:", error);
      toast({ title: "Erreur", description: "Impossible de lancer le téléchargement.", variant: "destructive" });
    }
  };

  const renderRequestsTable = (requests: AbsenceRequest[]) => (
    <div className="w-full overflow-x-auto">
    <Table>
      <TableHeader><TableRow>
          <TableHead>Employé</TableHead>
          <TableHead>Type</TableHead>
          <TableHead className="min-w-0 max-w-[220px]">Demande</TableHead>
          <TableHead>Solde aujourd&apos;hui</TableHead>
          <TableHead>Justificatif</TableHead>
          <TableHead>Signalement DSN</TableHead>
          <TableHead className="text-right">Actions</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {requests.map(req => (
          <TableRow key={req.id}>
            <TableCell className="font-medium">
              <div>
                <p>{displayNamePrenomNom(req.employee)}</p>
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
                libelleDeLaDemande(typeLabels[req.type], req.arret_type)
              )}
            </TableCell>
            <TableCell>{renderDates(req.selected_days, req.demi_journees)}</TableCell>
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
              {estArretIjss(req.type) && req.status === 'validated' && (
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap gap-1">
                    <AbsenceSignalementBadge arret={req} signalements={signalements} />
                    {ijssStatusMap[req.id] && (
                      <AbsenceIjssStatusBadge status={ijssStatusMap[req.id]!} />
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 items-center">
                    <Button variant="outline" size="sm" asChild>
                      <Link to="/suivi-ijss">
                        <ExternalLink className="mr-2 h-4 w-4" />
                        Suivi IJSS
                      </Link>
                    </Button>
                  </div>
                </div>
              )}
            </TableCell>
            <TableCell className="text-right align-top">
              <div className="flex flex-col items-end gap-3">
                {ABSENCE_TYPES_MAINTIEN_PREVIEW.has(req.type) ? (
                  <Collapsible
                    defaultOpen={req.status === 'pending'}
                    className="w-full max-w-md text-left"
                  >
                    <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted/50">
                      Maintien &amp; subrogation
                      <ChevronDown className="h-4 w-4" />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="pt-2">
                      <MaintenancePreviewBlock
                        absenceId={req.id}
                        arretType={req.arret_type ?? null}
                        onSubrogationChange={(v) =>
                          setPendingSubrogation((prev) => ({ ...prev, [req.id]: v }))
                        }
                      />
                    </CollapsibleContent>
                  </Collapsible>
                ) : null}
                {req.status === 'pending' ? (
                  <div className="flex gap-2 justify-end">
                    <Button size="sm" variant="outline" onClick={() => handleUpdateStatus(req.id, 'rejected')}><X className="mr-2 h-4 w-4" /> Rejeter</Button>
                    <Button
                      size="sm"
                      onClick={() =>
                        handleUpdateStatus(
                          req.id,
                          'validated',
                          pendingSubrogation[req.id],
                        )
                      }
                    >
                      <Check className="mr-2 h-4 w-4" /> Approuver
                    </Button>
                  </div>
                ) : req.status === 'validated' ? (
                  <div className="flex items-center gap-2 justify-end">
                    <Badge variant="success" className="justify-end">
                      <Check className="mr-1 h-3 w-3" /> Validée
                    </Badge>
                    {TYPES_CONGE_MODIFIABLES.has(req.type) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setAbsenceAModifier(req)}
                        data-testid="modifier-conge"
                      >
                        Modifier
                      </Button>
                    )}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button size="sm" variant="ghost" className="text-muted-foreground">
                          Annuler
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Annuler cette absence ?</AlertDialogTitle>
                          <AlertDialogDescription>
                            L'absence validée sera annulée et ses jours rendus au
                            planning (travail ou week-end). Les compteurs sont
                            recalculés.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Retour</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => handleUpdateStatus(req.id, 'cancelled')}
                          >
                            Annuler l'absence
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                ) : (
                  <Badge
                    variant={req.status === 'cancelled' ? 'secondary' : 'destructive'}
                    className="justify-end"
                  >
                    <X className="mr-1 h-3 w-3" />{' '}
                    {req.status === 'cancelled' ? 'Annulée' : 'Rejetée'}
                  </Badge>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageFetchIndicator isFetching={absencesQuery.isFetching} />
      <RhPageHeader
        title="Gestion des Congés & Absences"
        actions={
          canShowRhNewAbsenceButton(user) ? (
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={() => setShowArretModal(true)}>
                + Enregistrer un arrêt
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowLeaveModal(true)}
              >
                Nouveau congé
              </Button>
            </div>
          ) : null
        }
      />
      <AbsenceRequestModal
        mode="rh_arret"
        isOpen={showArretModal}
        onClose={() => setShowArretModal(false)}
        onSuccess={() => {
          setShowArretModal(false);
          void fetchData();
        }}
      />
      <AbsenceRequestModal
        mode="rh_leave"
        isOpen={absenceAModifier !== null}
        absenceAModifier={absenceAModifier}
        onClose={() => setAbsenceAModifier(null)}
        onSuccess={() => {
          setAbsenceAModifier(null);
          void fetchData();
        }}
      />
      <AbsenceRequestModal
        mode="rh_leave"
        isOpen={showLeaveModal}
        onClose={() => setShowLeaveModal(false)}
        onSuccess={() => {
          setShowLeaveModal(false);
          void fetchData();
        }}
      />
      <div className="space-y-4">
        {!isPayrollFocusActive(user) && (
          <>
            <LeaveCampaignSection />
            <LeaveNotificationSettingsPanel />
          </>
        )}
        <RttYearEndRhSection />
        <p className="text-sm text-muted-foreground">
          <Link to="/company?tab=paie#soldes-rtt" className="text-primary underline-offset-4 hover:underline">
            Gérer les soldes RTT effectif
          </Link>
          {' '}— Entreprise, onglet Paie, section Congés &amp; RTT.
        </p>
      </div>
      {bandeauSalarie && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm"
          data-testid="bandeau-absences-salarie"
        >
          <span>
            {bandeauSalarie.texte}{' '}
            <Link
              to={bandeauSalarie.lien.href}
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              {bandeauSalarie.lien.libelle}
            </Link>
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setSearchParams({}, { replace: true })}
          >
            Afficher tous les salariés
          </Button>
        </div>
      )}
      <Tabs defaultValue={salarieFiltre ? 'processed' : 'pending'}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="pending"><Clock className="mr-2 h-4 w-4" /> Demandes en attente <Badge className="ml-2">{pending.length}</Badge></TabsTrigger>
            <TabsTrigger value="processed">Historique</TabsTrigger>
          </TabsList>
          <Input
            value={rechercheSalarie}
            onChange={(e) => setRechercheSalarie(e.target.value)}
            placeholder="Rechercher un salarié…"
            className="w-full sm:w-64"
            aria-label="Rechercher un salarié"
          />
        </div>
        <TabsContent value="pending"><Card><CardHeader><CardTitle>Demandes à valider</CardTitle></CardHeader><CardContent>{isLoading ? <TableSkeleton rows={5} columns={5} /> : renderRequestsTable(filtrerParSalarie(pending))}</CardContent></Card></TabsContent>
        <TabsContent value="processed"><Card><CardHeader><CardTitle>Demandes traitées</CardTitle></CardHeader><CardContent>{isLoading ? <TableSkeleton rows={5} columns={5} /> : renderRequestsTable(filtrerParSalarie(processed))}</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}
