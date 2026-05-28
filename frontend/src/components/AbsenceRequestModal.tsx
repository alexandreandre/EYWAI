// Fichier : src/components/AbsenceRequestModal.tsx

import { useState, useEffect } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Calendar as CalendarIcon, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

// Composants UI
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";

// Logique
import { useAuth } from "@/contexts/AuthContext";
import { useEmployeeProfileQuery } from "@/hooks/queries/useEmployeeDashboardQueries";
import { useToast } from "@/components/ui/use-toast";
import * as absencesApi from "@/api/absences";
import { getEmployeesLite, type EmployeeLite } from "@/api/employees";

/** Types d’absence pour lesquels la qualification d’arrêt est obligatoire. */
const ARRET_PRINCIPAL_TYPES = [
  "arret_maladie",
  "arret_at",
  "arret_maladie_pro",
  "arret_maternite",
  "arret_paternite",
] as const;

function isArretPrincipalType(
  t: string
): t is (typeof ARRET_PRINCIPAL_TYPES)[number] {
  return (ARRET_PRINCIPAL_TYPES as readonly string[]).includes(t);
}

function BalanceHint({
  absenceType,
  balances,
}: {
  absenceType: string;
  balances: absencesApi.AbsenceBalance[];
}) {
  const labelByType: Record<string, string> = {
    conge_paye: 'Congés Payés',
    rtt: 'RTT',
    repos_compensateur: 'Repos compensateur',
  };
  const label = labelByType[absenceType];
  if (!label) return null;
  const row = balances.find((b) => b.type === label);
  const rest = typeof row?.remaining === 'number' ? row.remaining : null;
  if (rest == null) return null;
  const typeLabel =
    absenceType === 'conge_paye'
      ? 'congés payés'
      : absenceType === 'rtt'
        ? 'RTT'
        : 'repos compensateur';
  return (
    <p className="text-xs text-muted-foreground">
      Solde {typeLabel} restant : {rest.toFixed(1)} j
    </p>
  );
}

interface AbsenceRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  /** Soldes de l'employé (pour vérifier CP restant sur conge_paye). */
  balances?: absencesApi.AbsenceBalance[];
  /** Vue RH : liste des employés de l'entreprise active et choix du bénéficiaire. */
  showEmployeeSelector?: boolean;
}

export function AbsenceRequestModal({
  isOpen,
  onClose,
  onSuccess,
  balances = [],
  showEmployeeSelector = false,
}: AbsenceRequestModalProps) {
  const { user } = useAuth();
  const { data: myEmployeeProfile } = useEmployeeProfileQuery(user?.id);
  const { toast } = useToast();

  type AbsenceTypeValue = 'conge_paye' | 'rtt' | 'repos_compensateur' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro';
  const [absenceType, setAbsenceType] = useState<AbsenceTypeValue | ''>('');
  const [eventSubtype, setEventSubtype] = useState<string>('');
  const [evenementFamilialEvents, setEvenementFamilialEvents] = useState<absencesApi.EvenementFamilialEvent[]>([]);
  const [selectedDays, setSelectedDays] = useState<Date[] | undefined>([]);
  const [comment, setComment] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [error, setError] = useState("");
  const [confirmSansSoldeOpen, setConfirmSansSoldeOpen] = useState(false);
  const [arretType, setArretType] = useState<absencesApi.ArretType | "">("");
  const [employees, setEmployees] = useState<EmployeeLite[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [isLoadingEmployees, setIsLoadingEmployees] = useState(false);

  // Réinitialiser les états à l'ouverture du modal
  useEffect(() => {
    if (isOpen) {
      setAbsenceType('');
      setEventSubtype('');
      setEvenementFamilialEvents([]);
      setSelectedDays([]);
      setComment("");
      setFile(null);
      setError("");
      setArretType("");
      if (showEmployeeSelector) {
        setSelectedEmployeeId("");
      }
    }
  }, [isOpen, showEmployeeSelector]);

  useEffect(() => {
    if (!isOpen || !showEmployeeSelector) {
      return;
    }
    setIsLoadingEmployees(true);
    getEmployeesLite()
      .then(setEmployees)
      .catch(() => setEmployees([]))
      .finally(() => setIsLoadingEmployees(false));
  }, [isOpen, showEmployeeSelector]);

  useEffect(() => {
    if (!isArretPrincipalType(absenceType)) {
      setArretType("");
    }
  }, [absenceType]);

  // Charger les événements familiaux quand on sélectionne ce type
  useEffect(() => {
    if (isOpen && absenceType === 'evenement_familial') {
      setIsLoadingEvents(true);
      absencesApi.getEvenementsFamiliaux()
        .then(res => setEvenementFamilialEvents(res.data.events || []))
        .catch(() => setEvenementFamilialEvents([]))
        .finally(() => setIsLoadingEvents(false));
      setEventSubtype('');
    }
  }, [isOpen, absenceType]);

  const doSubmit = async () => {
    if (!selectedDays || selectedDays.length === 0) return;
    setError("");
    setIsLoading(true);

    try {
      // Formatage des dates au format YYYY-MM-DD attendu par le backend
      const formattedDays = selectedDays.map(day => format(day, "yyyy-MM-dd"));

      let attachmentUrl: string | null = null;
      let filename: string | null = null;

      // Si un fichier est sélectionné, l'uploader d'abord
      if (file) {
        // 1. Obtenir l'URL d'upload
        const { path, signedURL } = await absencesApi.getUploadUrl(file.name);

        // 2. Uploader le fichier
        await absencesApi.uploadFile(signedURL, file);

        // 3. Conserver les informations pour la création de la demande
        attachmentUrl = path;
        filename = file.name;
      }

      const employeeId =
        showEmployeeSelector && selectedEmployeeId
          ? selectedEmployeeId
          : myEmployeeProfile?.id ?? user!.id;

      // Créer la demande d'absence avec ou sans justificatif
      const payload: absencesApi.AbsenceCreationPayload = {
        employee_id: employeeId,
        type: absenceType as 'conge_paye' | 'rtt' | 'repos_compensateur' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro',
        selected_days: formattedDays,
        comment: comment || null,
        attachment_url: attachmentUrl,
        filename: filename,
      };
      if (absenceType === 'evenement_familial' && eventSubtype) {
        payload.event_subtype = eventSubtype;
      }
      if (isArretPrincipalType(absenceType)) {
        payload.arret_type = arretType as absencesApi.ArretType;
      }
      await absencesApi.createAbsenceRequest(payload);

      toast({ title: "Succès", description: "Votre demande d'absence a été soumise." });
      onSuccess();
      onClose();
      setConfirmSansSoldeOpen(false);
    } catch (err) {
      toast({ title: "Erreur", description: "Impossible de soumettre la demande.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = () => {
    if (showEmployeeSelector && !selectedEmployeeId) {
      setError("Veuillez sélectionner un employé.");
      return;
    }
    if (!absenceType) {
      setError("Veuillez sélectionner un type d'absence.");
      return;
    }
    if (absenceType === 'evenement_familial' && !eventSubtype) {
      setError("Veuillez sélectionner le type d'événement familial.");
      return;
    }
    if (isArretPrincipalType(absenceType) && !arretType) {
      setError("Veuillez sélectionner le type d'arrêt.");
      return;
    }
    if (!selectedDays || selectedDays.length === 0) {
      setError("Veuillez sélectionner au moins un jour de congé.");
      return;
    }

    // Congés payés : alerte si la demande dépasse le solde
    if (absenceType === 'conge_paye') {
      const cpBalance = balances.find((b) => b.type === "Congés Payés");
      const cpRestant = typeof cpBalance?.remaining === "number" ? cpBalance.remaining : 0;
      const nbJours = selectedDays.length;
      if (nbJours > cpRestant) {
        setConfirmSansSoldeOpen(true);
        return;
      }
    }

    setError("");
    doSubmit();
  };

  const selectedDaysCount = selectedDays?.length ?? 0;

  const cpBalance = balances.find((b) => b.type === "Congés Payés");
  const cpRestant = typeof cpBalance?.remaining === "number" ? cpBalance.remaining : 0;
  const nbJoursSansSolde = Math.max(0, (selectedDays?.length ?? 0) - cpRestant);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Faire une demande d'absence</DialogTitle>
          <DialogDescription>
            Sélectionnez un type et choisissez les jours dans le calendrier.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {showEmployeeSelector ? (
            <div className="grid gap-2">
              <Label htmlFor="absence-employee">Employé</Label>
              {isLoadingEmployees ? (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Chargement des employés…
                </p>
              ) : (
                <Select
                  value={selectedEmployeeId || undefined}
                  onValueChange={setSelectedEmployeeId}
                >
                  <SelectTrigger id="absence-employee">
                    <SelectValue placeholder="Sélectionner un employé…" />
                  </SelectTrigger>
                  <SelectContent>
                    {employees.map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.first_name} {e.last_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          ) : null}

          <div className="grid gap-2">
            <Label htmlFor="absence-type">Type d'absence</Label>
            <Select value={absenceType} onValueChange={(value: AbsenceTypeValue) => setAbsenceType(value)}>
              <SelectTrigger id="absence-type"><SelectValue placeholder="Sélectionner un type..." /></SelectTrigger>
              <SelectContent>
                <SelectItem value="conge_paye">Congé Payé</SelectItem>
                <SelectItem value="rtt">RTT</SelectItem>
                <SelectItem value="repos_compensateur">Repos Compensateur</SelectItem>
                <SelectItem value="evenement_familial">Événement Familial</SelectItem>
                <SelectItem value="arret_maladie">Arrêt Maladie</SelectItem>
                <SelectItem value="arret_at">Accident du Travail</SelectItem>
                <SelectItem value="arret_paternite">Congé Paternité</SelectItem>
                <SelectItem value="arret_maternite">Congé Maternité</SelectItem>
                <SelectItem value="arret_maladie_pro">Maladie Professionnelle</SelectItem>
              </SelectContent>
            </Select>
            {!showEmployeeSelector && balances.length > 0 && absenceType && (
              <BalanceHint absenceType={absenceType} balances={balances} />
            )}
          </div>

          {isArretPrincipalType(absenceType) && (
            <div className="grid gap-2">
              <Label htmlFor="arret-type">Type d&apos;arrêt</Label>
              <Select
                value={arretType || undefined}
                onValueChange={(v) => setArretType(v as absencesApi.ArretType)}
              >
                <SelectTrigger id="arret-type">
                  <SelectValue placeholder="Sélectionner le type d'arrêt…" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="maladie_simple">Maladie simple</SelectItem>
                  <SelectItem value="accident_travail">Accident du travail</SelectItem>
                  <SelectItem value="maladie_professionnelle">Maladie professionnelle</SelectItem>
                  <SelectItem value="accident_trajet">Accident de trajet</SelectItem>
                  <SelectItem value="mi_temps_therapeutique">Mi-temps thérapeutique</SelectItem>
                  <SelectItem value="ald">ALD</SelectItem>
                  <SelectItem value="rechute_at">Rechute AT</SelectItem>
                  <SelectItem value="arret_exceptionnel">Arrêt exceptionnel</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {absenceType === 'evenement_familial' && (
            <div className="grid gap-2">
              <Label htmlFor="event-subtype">Type d'événement</Label>
              {isLoadingEvents ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Chargement...</p>
              ) : evenementFamilialEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun événement familial disponible. Assurez-vous que votre convention collective est configurée.</p>
              ) : (
                <>
                  <Select value={eventSubtype} onValueChange={(v) => { setEventSubtype(v); setSelectedDays([]); }}>
                    <SelectTrigger id="event-subtype"><SelectValue placeholder="Sélectionner l'événement..." /></SelectTrigger>
                    <SelectContent>
                      {evenementFamilialEvents.map(ev => (
                        <SelectItem key={ev.code} value={ev.code}>
                          {ev.libelle} ({ev.solde_restant} j restant{ev.solde_restant > 1 ? 's' : ''}{ev.cycles_completed ? ` · consommé ${ev.cycles_completed}×` : ''})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {eventSubtype && (() => {
                    const ev = evenementFamilialEvents.find(e => e.code === eventSubtype);
                    if (!ev) return null;
                    const nbSelected = selectedDays?.length ?? 0;
                    const restantApresSelection = ev.solde_restant - nbSelected;
                    return (
                      <p className="text-xs text-muted-foreground">
                        Quota : {ev.duree_jours} j. Restant : {restantApresSelection} j.
                        {ev.cycles_completed ? <span className="ml-1 text-muted-foreground/80">· Consommé entièrement {ev.cycles_completed}×</span> : null}
                      </p>
                    );
                  })()}
                </>
              )}
            </div>
          )}

          <div className="grid gap-2">
            <Label>Jours demandés</Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className={cn("justify-start text-left font-normal", !selectedDaysCount && "text-muted-foreground")}>
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {selectedDaysCount > 0
                    ? `${selectedDaysCount} jour${selectedDaysCount > 1 ? 's' : ''} sélectionné${selectedDaysCount > 1 ? 's' : ''}`
                    : "Cliquez pour choisir les dates"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="multiple"
                  selected={selectedDays}
                  onSelect={(dates) => {
                    if (!dates) { setSelectedDays([]); return; }
                    if (absenceType === 'evenement_familial' && eventSubtype) {
                      const ev = evenementFamilialEvents.find(e => e.code === eventSubtype);
                      if (ev && dates.length > ev.solde_restant) {
                        const sorted = [...dates].sort((a, b) => a.getTime() - b.getTime());
                        setSelectedDays(sorted.slice(0, ev.solde_restant));
                        return;
                      }
                    }
                    setSelectedDays(dates);
                  }}
                  initialFocus
                  locale={fr}
                  disabled={{ before: new Date() }}
                />
              </PopoverContent>
            </Popover>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="attachment">Justificatif (facultatif)</Label>
            <Input
              id="attachment"
              type="file"
              accept="image/*,application/pdf"
              onChange={e => setFile(e.target.files ? e.target.files[0] : null)}
            />
            {file && <p className="text-xs text-muted-foreground">Fichier sélectionné : {file.name}</p>}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="comment">Commentaire (facultatif)</Label>
            <Textarea id="comment" placeholder="Ajoutez un message pour votre manager..." value={comment} onChange={e => setComment(e.target.value)} />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Soumettre la demande
          </Button>
        </DialogFooter>
      </DialogContent>

      <AlertDialog open={confirmSansSoldeOpen} onOpenChange={setConfirmSansSoldeOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Attention — congé sans solde</AlertDialogTitle>
            <AlertDialogDescription>
              Votre solde de congés payés est de {cpRestant} jour{cpRestant !== 1 ? "s" : ""}. Vous demandez {(selectedDays?.length ?? 0)} jour{(selectedDays?.length ?? 0) !== 1 ? "s" : ""}.
              Les {nbJoursSansSolde} jour{nbJoursSansSolde !== 1 ? "s" : ""} excédentaire{nbJoursSansSolde !== 1 ? "s" : ""} seront considéré{nbJoursSansSolde !== 1 ? "s" : ""} comme congé sans solde (non rémunéré).
              Confirmez-vous cette demande ?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); doSubmit(); }} disabled={isLoading}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Confirmer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
}