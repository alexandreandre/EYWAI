// Fichier : src/components/AbsenceRequestModal.tsx

import { useState, useEffect, useMemo } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Calendar as CalendarIcon, Loader2 } from "lucide-react";
import axios from "axios";
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
import {
  EMPLOYEE_REQUESTABLE_ABSENCE_TYPES,
  RH_ONLY_ABSENCE_TYPES,
  formatCongePayeInsufficientMessage,
  getAvailableCongePayeDays,
  type EmployeeRequestableAbsenceType,
} from "@/lib/employeeAbsencesUtils";

export type AbsenceRequestModalMode = "employee" | "rh_arret" | "rh_leave";

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
  pendingAbsences = [],
}: {
  absenceType: string;
  balances: absencesApi.AbsenceBalance[];
  pendingAbsences?: absencesApi.AbsenceRequest[];
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

  if (absenceType === 'conge_paye') {
    const available = getAvailableCongePayeDays(balances, pendingAbsences);
    const pendingDays = Math.max(0, rest - available);
    return (
      <div className="space-y-1 text-xs text-muted-foreground">
        <p>Solde {typeLabel} restant : {rest.toFixed(1)} j</p>
        {pendingDays > 0 && (
          <p>{pendingDays.toFixed(1)} j déjà réservé(s) par des demandes en attente.</p>
        )}
        <p className="font-medium text-foreground">
          Disponible pour une nouvelle demande : {available.toFixed(1)} j
        </p>
      </div>
    );
  }

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
  /** Demandes en attente (pour réserver le solde CP côté salarié). */
  pendingAbsences?: absencesApi.AbsenceRequest[];
  /** Vue RH : liste des employés de l'entreprise active et choix du bénéficiaire. */
  showEmployeeSelector?: boolean;
  /** Parcours RH : arrêt direct (validé immédiatement) ou demande de congé pour un salarié. */
  mode?: AbsenceRequestModalMode;
}

const RH_ARRET_TYPE_LABELS: Record<
  (typeof RH_ONLY_ABSENCE_TYPES)[number],
  string
> = {
  arret_maladie: "Arrêt maladie",
  arret_at: "Accident du travail",
  arret_paternite: "Congé paternité",
  arret_maternite: "Congé maternité",
  arret_maladie_pro: "Maladie professionnelle",
};

function resolveModalMode(
  mode: AbsenceRequestModalMode | undefined,
  showEmployeeSelector: boolean,
): AbsenceRequestModalMode {
  if (mode) return mode;
  return showEmployeeSelector ? "rh_leave" : "employee";
}

function getApiErrorMessage(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return null;
}

export function AbsenceRequestModal({
  isOpen,
  onClose,
  onSuccess,
  balances = [],
  pendingAbsences = [],
  showEmployeeSelector = false,
  mode,
}: AbsenceRequestModalProps) {
  const effectiveMode = resolveModalMode(mode, showEmployeeSelector);
  const isRhArret = effectiveMode === "rh_arret";
  const isRhLeave = effectiveMode === "rh_leave";
  const isRhMode = isRhArret || isRhLeave;
  const { user } = useAuth();
  const { data: myEmployeeProfile } = useEmployeeProfileQuery(user?.id);
  const { toast } = useToast();

  type AbsenceTypeValue = EmployeeRequestableAbsenceType | absencesApi.AbsenceCreationPayload['type'];
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
      setAbsenceType(isRhArret ? "arret_maladie" : "");
      setEventSubtype("");
      setEvenementFamilialEvents([]);
      setSelectedDays([]);
      setComment("");
      setFile(null);
      setError("");
      setArretType("");
      if (isRhMode) {
        setSelectedEmployeeId("");
      }
    }
  }, [isOpen, isRhArret, isRhMode]);

  useEffect(() => {
    if (!isOpen || !isRhMode) {
      return;
    }
    setIsLoadingEmployees(true);
    getEmployeesLite()
      .then(setEmployees)
      .catch(() => setEmployees([]))
      .finally(() => setIsLoadingEmployees(false));
  }, [isOpen, isRhMode]);

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

  const selectedDaysCount = selectedDays?.length ?? 0;

  const availableCongePayeDays = useMemo(
    () => getAvailableCongePayeDays(balances, pendingAbsences),
    [balances, pendingAbsences],
  );

  const cpBalanceExceeded =
    effectiveMode === "employee" &&
    absenceType === "conge_paye" &&
    selectedDaysCount > availableCongePayeDays;

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
        isRhMode && selectedEmployeeId
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

      toast({
        title: "Succès",
        description: isRhArret
          ? "L'arrêt a été enregistré."
          : isRhLeave
            ? "La demande a été créée pour le salarié."
            : "Votre demande d'absence a été soumise.",
      });
      onSuccess();
      onClose();
      setConfirmSansSoldeOpen(false);
    } catch (err) {
      const apiMessage = getApiErrorMessage(err);
      if (apiMessage) {
        setError(apiMessage);
      }
      toast({
        title: "Erreur",
        description: apiMessage ?? (
          isRhArret
            ? "Impossible d'enregistrer l'arrêt."
            : "Impossible de soumettre la demande."
        ),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = () => {
    if (isRhMode && !selectedEmployeeId) {
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
      setError(
        isRhArret
          ? "Veuillez sélectionner au moins un jour d'arrêt."
          : "Veuillez sélectionner au moins un jour de congé.",
      );
      return;
    }

    // Congés payés : blocage salarié si solde insuffisant ; RH peut confirmer du sans solde
    if (absenceType === "conge_paye") {
      const nbJours = selectedDays.length;
      if (effectiveMode === "employee") {
        if (nbJours > availableCongePayeDays) {
          setError(formatCongePayeInsufficientMessage(availableCongePayeDays, nbJours));
          return;
        }
      } else {
        const cpBalance = balances.find((b) => b.type === "Congés Payés");
        const cpRestant = typeof cpBalance?.remaining === "number" ? cpBalance.remaining : 0;
        if (nbJours > cpRestant) {
          setConfirmSansSoldeOpen(true);
          return;
        }
      }
    }

    setError("");
    doSubmit();
  };

  const employeeAbsenceTypeLabels: Record<EmployeeRequestableAbsenceType, string> = {
    conge_paye: 'Congé Payé',
    rtt: 'RTT',
    repos_compensateur: 'Repos Compensateur',
    recuperation_modulation: 'Récupération modulation',
    evenement_familial: 'Événement Familial',
  };

  const modBalance = balances.find((b) => b.type === 'Compte modulation');
  const modRestant =
    typeof modBalance?.remaining === 'number' ? modBalance.remaining : 0;

  const absenceTypeOptions: { value: AbsenceTypeValue; label: string }[] = isRhArret
    ? RH_ONLY_ABSENCE_TYPES.map((value) => ({
        value,
        label: RH_ARRET_TYPE_LABELS[value],
      }))
    : isRhLeave
      ? [
          { value: "conge_paye", label: "Congé Payé" },
          { value: "rtt", label: "RTT" },
          { value: "repos_compensateur", label: "Repos Compensateur" },
          { value: "evenement_familial", label: "Événement Familial" },
        ]
      : EMPLOYEE_REQUESTABLE_ABSENCE_TYPES.filter(
          (value) =>
            value !== "recuperation_modulation" || modRestant > 0,
        ).map((value) => ({
          value,
          label: employeeAbsenceTypeLabels[value],
        }));

  const dialogTitle = isRhArret
    ? "Enregistrer un arrêt"
    : isRhLeave
      ? "Créer une demande de congé"
      : "Faire une demande d'absence";

  const dialogDescription = isRhArret
    ? "Saisie directe par les RH — l'arrêt est enregistré immédiatement, sans demande du salarié."
    : isRhLeave
      ? "Créez une demande de congé au nom d'un salarié. Elle devra être validée comme une demande classique."
      : "Sélectionnez un type et choisissez les jours dans le calendrier.";

  const submitLabel = isRhArret
    ? "Enregistrer l'arrêt"
    : isRhLeave
      ? "Créer la demande"
      : "Soumettre la demande";

  const cpBalance = balances.find((b) => b.type === "Congés Payés");
  const cpRestant = typeof cpBalance?.remaining === "number" ? cpBalance.remaining : 0;
  const nbJoursSansSolde = Math.max(0, (selectedDays?.length ?? 0) - cpRestant);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {isRhMode ? (
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
            <Label htmlFor="absence-type">
              {isRhArret ? "Nature de l'arrêt" : "Type d'absence"}
            </Label>
            <Select value={absenceType} onValueChange={(value: AbsenceTypeValue) => setAbsenceType(value)}>
              <SelectTrigger id="absence-type"><SelectValue placeholder="Sélectionner un type..." /></SelectTrigger>
              <SelectContent>
                {absenceTypeOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!isRhMode && balances.length > 0 && absenceType && (
              <BalanceHint
                absenceType={absenceType}
                balances={balances}
                pendingAbsences={pendingAbsences}
              />
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
            <Label>{isRhArret ? "Période d'arrêt" : "Jours demandés"}</Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className={cn("justify-start text-left font-normal", !selectedDaysCount && "text-muted-foreground")}>
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {selectedDaysCount > 0
                    ? `${selectedDaysCount} jour${selectedDaysCount > 1 ? "s" : ""} sélectionné${selectedDaysCount > 1 ? "s" : ""}`
                    : isRhArret
                      ? "Cliquez pour choisir la période"
                      : "Cliquez pour choisir les dates"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="multiple"
                  selected={selectedDays}
                  onSelect={(dates) => {
                    if (!dates) { setSelectedDays([]); setError(""); return; }
                    if (absenceType === 'evenement_familial' && eventSubtype) {
                      const ev = evenementFamilialEvents.find(e => e.code === eventSubtype);
                      if (ev && dates.length > ev.solde_restant) {
                        const sorted = [...dates].sort((a, b) => a.getTime() - b.getTime());
                        setSelectedDays(sorted.slice(0, ev.solde_restant));
                        return;
                      }
                    }
                    if (
                      effectiveMode === "employee" &&
                      absenceType === "conge_paye" &&
                      dates.length > availableCongePayeDays
                    ) {
                      const sorted = [...dates].sort((a, b) => a.getTime() - b.getTime());
                      const capped = sorted.slice(0, Math.max(0, Math.floor(availableCongePayeDays)));
                      setSelectedDays(capped);
                      setError(
                        formatCongePayeInsufficientMessage(
                          availableCongePayeDays,
                          dates.length,
                        ),
                      );
                      return;
                    }
                    setError("");
                    setSelectedDays(dates);
                  }}
                  initialFocus
                  locale={fr}
                  disabled={effectiveMode === "employee" ? { before: new Date() } : undefined}
                />
              </PopoverContent>
            </Popover>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="attachment">
              {isRhArret ? "Certificat médical (facultatif)" : "Justificatif (facultatif)"}
            </Label>
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
            <Textarea
              id="comment"
              placeholder={
                isRhArret
                  ? "Ex. certificat reçu par mail, prolongation…"
                  : isRhLeave
                    ? "Note pour le circuit de validation…"
                    : "Ajoutez un message pour votre manager…"
              }
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={handleSave} disabled={isLoading || cpBalanceExceeded}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {submitLabel}
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