// src/components/exports/ExportCommonModel.tsx
// Modèle commun d'export - ÉTAPE 1 : Structure et UX uniquement

import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEmptyExportAlertMessage, isEmptyDataMessage } from "@/lib/exportEmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { 
  Settings, 
  Eye, 
  Download, 
  AlertTriangle, 
  CheckCircle2, 
  Calendar,
  Building,
  Users as UsersIcon,
  FileSpreadsheet,
  Info,
} from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { previewExport, generateExport, ExportPreviewResponse, ExportGenerateResponse, ExportType } from "@/api/exports";
import { fetchEmployeesSummary } from "@/api/employees";

export type ExportStep = "parametrage" | "previsualisation" | "generation";
export type ExportFileFormat = "csv" | "xlsx";
export type NotesFraisCabinetFormat = "generique" | "quadra" | "sage";
export type OdRegroupement = "global" | "par_etablissement" | "par_analytique";
export type BankFileFormat = "sepa" | "csv";

const OD_EXPORT_TYPES = new Set<ExportType>([
  "od_salaires",
  "od_charges_sociales",
  "od_pas",
  "od_globale",
]);

const EXPORT_TYPE_MAP: Record<string, ExportType> = {
  journal_paie: "journal_paie",
  od_salaires: "od_salaires",
  od_charges_sociales: "od_charges_sociales",
  od_pas: "od_pas",
  od_globale: "od_globale",
  export_cabinet_generique: "export_cabinet_generique",
  export_cabinet_quadra: "export_cabinet_quadra",
  export_cabinet_sage: "export_cabinet_sage",
  dsn_mensuelle: "dsn_mensuelle",
  virement_salaires: "virement_salaires",
  "virement-salaires": "virement_salaires",
  charges_sociales: "charges_sociales",
  "charges-sociales": "charges_sociales",
  conges_absences: "conges_absences",
  "conges-absences": "conges_absences",
  notes_frais: "notes_frais",
  "notes-frais": "notes_frais",
  acomptes: "acomptes",
  saisies: "saisies",
  fec: "fec",
  prets_employeur: "prets_employeur",
  "prets-employeur": "prets_employeur",
  paiement_organismes: "paiement_organismes",
  "paiement-organismes": "paiement_organismes",
  attestations_annexes: "attestations_annexes",
  "attestations-annexes": "attestations_annexes",
  "Acomptes & avances": "acomptes",
  "Journal de paie": "journal_paie",
  "Charges sociales par caisse": "charges_sociales",
  "Congés payés / Absences": "conges_absences",
  "Notes de frais": "notes_frais",
  "DSN mensuelle": "dsn_mensuelle",
  "Virement salaires": "virement_salaires",
  "Récapitulatif des montants": "recapitulatif_montants",
};

const FILE_FORMAT_EXPORT_TYPES = new Set<ExportType>([
  "journal_paie",
  "charges_sociales",
  "conges_absences",
  "notes_frais",
  "recapitulatif_montants",
  "od_salaires",
  "od_charges_sociales",
  "od_pas",
  "od_globale",
  "export_cabinet_generique",
  "export_cabinet_quadra",
  "export_cabinet_sage",
  "acomptes",
  "saisies",
  "prets_employeur",
  "paiement_organismes",
  "attestations_annexes",
]);

function resolveApiExportType(exportType: string): ExportType {
  return EXPORT_TYPE_MAP[exportType] || (exportType as ExportType);
}

function formatEuro(amount: number): string {
  return amount.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
}

function hasCotisationsTotals(totals: ExportPreviewResponse["totals"]): boolean {
  return (
    totals.total_cotisations_salariales != null ||
    totals.total_cotisations_patronales != null
  );
}

function defaultExportFormat(exportType: string): ExportFileFormat {
  const apiType = resolveApiExportType(exportType);
  if (
    apiType === "charges_sociales" ||
    apiType === "conges_absences" ||
    apiType === "notes_frais" ||
    apiType === "acomptes" ||
    apiType === "saisies" ||
    apiType === "prets_employeur" ||
    apiType === "paiement_organismes" ||
    apiType === "attestations_annexes" ||
    apiType === "recapitulatif_montants"
  ) {
    return "xlsx";
  }
  return "csv";
}

// Mapping des IDs techniques vers les noms lisibles
const exportTypeLabels: Record<string, string> = {
  // Paie & Comptabilité
  journal_paie: "Journal de paie",
  od_salaires: "OD Salaires",
  od_charges_sociales: "OD Charges sociales",
  od_pas: "OD PAS",
  od_globale: "OD Globale de paie",
  export_cabinet_generique: "Export format cabinet générique",
  export_cabinet_quadra: "Export format Quadra",
  export_cabinet_sage: "Export format Sage",
  acomptes: "Acomptes & avances",
  // Déclarations
  dsn_mensuelle: "DSN mensuelle",
  // Paiements
  "virement-salaires": "Virement salaires",
  "recapitulatif-montants": "Récapitulatif des montants",
  virement_salaires: "Virement salaires",
  recapitulatif_montants: "Récapitulatif des montants",
  // Exports RH
  "charges-sociales": "Charges sociales par caisse",
  "conges-absences": "Congés payés / Absences",
  "notes-frais": "Notes de frais",
  charges_sociales: "Charges sociales par caisse",
  conges_absences: "Congés payés / Absences",
  notes_frais: "Notes de frais",
};

interface ExportCommonModelProps {
  exportType: string;
  exportDescription: string;
  onClose?: () => void;
}

export function ExportCommonModel({ exportType, exportDescription, onClose }: ExportCommonModelProps) {
  const displayName = exportTypeLabels[exportType] || exportType;
  const { activeCompany } = useCompany();
  const apiExportType = useMemo(() => resolveApiExportType(exportType), [exportType]);
  const supportsFileFormat = FILE_FORMAT_EXPORT_TYPES.has(apiExportType);
  const [currentStep, setCurrentStep] = useState<ExportStep>("parametrage");
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<ExportPreviewResponse | null>(null);
  const [generateResponse, setGenerateResponse] = useState<ExportGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFileFormat>(() =>
    defaultExportFormat(exportType),
  );
  const [cabinetFormat, setCabinetFormat] = useState<NotesFraisCabinetFormat>("generique");
  
  // État pour le paramétrage
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [selectedCompany, setSelectedCompany] = useState<string>(activeCompany?.company_id || "");
  const [selectedScope, setSelectedScope] = useState<"all" | "selection">("all");
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<string[]>([]);
  const [odRegroupement, setOdRegroupement] = useState<OdRegroupement>("global");
  const [bankFileFormat, setBankFileFormat] = useState<BankFileFormat>("sepa");
  
  // Paramètres spécifiques aux paiements
  const [executionDate, setExecutionDate] = useState<string>("");
  const [paymentLabel, setPaymentLabel] = useState<string>("");
  const [excludedEmployees, setExcludedEmployees] = useState<string[]>([]);

  const { data: employeesSummary = [] } = useQuery({
    queryKey: ["employees-summary-payroll", activeCompany?.company_id],
    queryFn: () => fetchEmployeesSummary("payroll"),
    enabled: Boolean(activeCompany?.company_id),
  });

  const resolvedEmployeeIds = useMemo(() => {
    if (selectedScope === "all") return undefined;
    return selectedEmployeeIds.length > 0 ? selectedEmployeeIds : undefined;
  }, [selectedScope, selectedEmployeeIds]);

  const buildExportFilters = () => {
    const filters: Record<string, unknown> = { include_consolidated: true };
    if (apiExportType === "notes_frais") {
      filters.cabinet_format = cabinetFormat;
    }
    if (OD_EXPORT_TYPES.has(apiExportType)) {
      filters.regroupement = odRegroupement;
    }
    if (apiExportType === "virement_salaires") {
      filters.bank_format = bankFileFormat;
    }
    return filters;
  };

  // Générer les options de mois
  const generateMonthOptions = () => {
    const options = [];
    const now = new Date();
    for (let i = -12; i <= 2; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const value = `${year}-${month}`;
      const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
      options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) });
    }
    return options;
  };

  const monthOptions = generateMonthOptions();

  const emptyExportMessage = useMemo(() => {
    if (!previewData) return null;
    return getEmptyExportAlertMessage(previewData, apiExportType, selectedPeriod);
  }, [previewData, apiExportType, selectedPeriod]);

  const blockingAnomalies = useMemo(() => {
    if (!previewData) return [];
    return previewData.anomalies.filter(
      (a) => a.severity === "blocking" && !isEmptyDataMessage(a.message),
    );
  }, [previewData]);

  const previewWarnings = useMemo(() => {
    if (!previewData) return [];
    if (emptyExportMessage) {
      return previewData.warnings.filter((w) => !isEmptyDataMessage(w));
    }
    return previewData.warnings;
  }, [previewData, emptyExportMessage]);

  useEffect(() => {
    setExportFormat(defaultExportFormat(exportType));
    setCabinetFormat("generique");
    setOdRegroupement("global");
    setBankFileFormat("sepa");
    setSelectedScope("all");
    setSelectedEmployeeIds([]);
  }, [exportType]);

  // Initialiser avec le mois actuel
  useEffect(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    setSelectedPeriod(currentMonth);
  }, []);

  const handlePreview = async () => {
    if (!selectedPeriod) {
      setError("Veuillez sélectionner une période");
      return;
    }
    if (selectedScope === "selection" && selectedEmployeeIds.length === 0) {
      setError("Sélectionnez au moins un collaborateur");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const preview = await previewExport({
        export_type: apiExportType,
        period: selectedPeriod,
        company_id: selectedCompany,
        employee_ids: resolvedEmployeeIds,
        excluded_employee_ids: excludedEmployees.length > 0 ? excludedEmployees : undefined,
        execution_date: executionDate || undefined,
        payment_label: paymentLabel || undefined,
        filters: buildExportFilters(),
      });
      
      setPreviewData(preview);
      setCurrentStep("previsualisation");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors de la prévisualisation");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!previewData || !previewData.can_generate) {
      setError("Impossible de générer l'export. Vérifiez les anomalies bloquantes.");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await generateExport({
        export_type: apiExportType,
        period: selectedPeriod,
        company_id: selectedCompany,
        employee_ids: selectedScope === "all" ? undefined : [],
        format: exportFormat,
        excluded_employee_ids: excludedEmployees.length > 0 ? excludedEmployees : undefined,
        execution_date: executionDate || undefined,
        payment_label: paymentLabel || undefined,
        filters: buildExportFilters(),
      });
      
      setGenerateResponse(response);
      setCurrentStep("generation");
      
      // Télécharger automatiquement les fichiers
      if (response.download_urls && Object.keys(response.download_urls).length > 0) {
        // Pour les virements, télécharger tous les fichiers
        Object.values(response.download_urls).forEach((url) => {
          window.open(url, '_blank');
        });
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors de la génération");
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setError(null);
    if (currentStep === "previsualisation") {
      setCurrentStep("parametrage");
    } else if (currentStep === "generation") {
      setCurrentStep("previsualisation");
    }
  };

  return (
    <div className="w-full space-y-4">
      <DialogHeader className="text-left">
        <DialogTitle className="text-xl">{displayName}</DialogTitle>
        <DialogDescription>{exportDescription}</DialogDescription>
      </DialogHeader>
      {(displayName === "Virement salaires" || displayName === "Récapitulatif des montants") && (
        <Alert className="border-orange-200 bg-orange-50 dark:bg-orange-950">
          <AlertTriangle className="h-4 w-4 text-orange-600" />
          <AlertTitle className="text-orange-800 dark:text-orange-200">Important</AlertTitle>
          <AlertDescription className="text-orange-700 dark:text-orange-300">
            Ce fichier ne déclenche aucun paiement automatiquement.
            Il doit être transmis manuellement à votre banque après validation.
          </AlertDescription>
        </Alert>
      )}
      
      <Card className="w-full">
        <CardContent className="space-y-6 pt-6">
        {/* Indicateur d'étape */}
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 ${currentStep === "parametrage" ? "text-primary" : "text-muted-foreground"}`}>
            <div className={`rounded-full p-2 ${currentStep === "parametrage" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
              <Settings className="h-4 w-4" />
            </div>
            <span className="text-sm font-medium">Paramétrage</span>
          </div>
          <div className="flex-1 h-px bg-border" />
          <div className={`flex items-center gap-2 ${currentStep === "previsualisation" ? "text-primary" : currentStep === "generation" ? "text-primary" : "text-muted-foreground"}`}>
            <div className={`rounded-full p-2 ${currentStep === "previsualisation" || currentStep === "generation" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
              <Eye className="h-4 w-4" />
            </div>
            <span className="text-sm font-medium">Prévisualisation</span>
          </div>
          <div className="flex-1 h-px bg-border" />
          <div className={`flex items-center gap-2 ${currentStep === "generation" ? "text-primary" : "text-muted-foreground"}`}>
            <div className={`rounded-full p-2 ${currentStep === "generation" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
              <Download className="h-4 w-4" />
            </div>
            <span className="text-sm font-medium">Génération</span>
          </div>
        </div>

        <Separator />

        {/* ÉTAPE 1 : Paramétrage */}
        {currentStep === "parametrage" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Période */}
              <div className="space-y-2">
                <Label htmlFor="period" className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  Période
                </Label>
                <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                  <SelectTrigger id="period">
                    <SelectValue placeholder="Sélectionner une période" />
                  </SelectTrigger>
                  <SelectContent>
                    {monthOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Entreprise / Établissement */}
              <div className="space-y-2">
                <Label htmlFor="company" className="flex items-center gap-2">
                  <Building className="h-4 w-4" />
                  Entreprise / Établissement
                </Label>
                <Select value={selectedCompany} onValueChange={setSelectedCompany}>
                  <SelectTrigger id="company">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={activeCompany?.company_id || ""}>
                      {activeCompany?.company_name || "Entreprise active"}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {supportsFileFormat ? (
              <div className="space-y-2 max-w-xs">
                <Label htmlFor="export-format" className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  Format de fichier
                </Label>
                <Select
                  value={exportFormat}
                  onValueChange={(value) => setExportFormat(value as ExportFileFormat)}
                >
                  <SelectTrigger id="export-format">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="xlsx">Excel (.xlsx)</SelectItem>
                    <SelectItem value="csv">CSV (.csv)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            {apiExportType === "notes_frais" ? (
              <div className="space-y-2 max-w-xs">
                <Label htmlFor="cabinet-format" className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  Format cabinet comptable
                </Label>
                <Select
                  value={cabinetFormat}
                  onValueChange={(value) => setCabinetFormat(value as NotesFraisCabinetFormat)}
                >
                  <SelectTrigger id="cabinet-format">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="generique">Générique</SelectItem>
                    <SelectItem value="quadra">Quadra</SelectItem>
                    <SelectItem value="sage">Sage</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            {/* Périmètre */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2">
                <UsersIcon className="h-4 w-4" />
                Périmètre collaborateur
              </Label>
              <div className="flex flex-col gap-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="scope-all"
                    checked={selectedScope === "all"}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        setSelectedScope("all");
                        setSelectedEmployeeIds([]);
                      }
                    }}
                  />
                  <Label htmlFor="scope-all" className="font-normal cursor-pointer">
                    Tous les collaborateurs
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="scope-selection"
                    checked={selectedScope === "selection"}
                    onCheckedChange={(checked) => checked && setSelectedScope("selection")}
                  />
                  <Label htmlFor="scope-selection" className="font-normal cursor-pointer">
                    Sélection de collaborateurs
                  </Label>
                </div>
              </div>
              {selectedScope === "selection" ? (
                <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-3">
                  {employeesSummary.length === 0 ? (
                    <p className="text-muted-foreground text-sm">Aucun collaborateur éligible paie.</p>
                  ) : (
                    employeesSummary.map((emp) => (
                      <div key={emp.id} className="flex items-center space-x-2">
                        <Checkbox
                          id={`emp-${emp.id}`}
                          checked={selectedEmployeeIds.includes(emp.id)}
                          onCheckedChange={(checked) => {
                            setSelectedEmployeeIds((prev) =>
                              checked
                                ? [...prev, emp.id]
                                : prev.filter((id) => id !== emp.id),
                            );
                          }}
                        />
                        <Label htmlFor={`emp-${emp.id}`} className="font-normal cursor-pointer">
                          {emp.first_name} {emp.last_name}
                        </Label>
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </div>

            {OD_EXPORT_TYPES.has(apiExportType) ? (
              <div className="space-y-2 max-w-xs">
                <Label htmlFor="od-regroupement">Regroupement comptable</Label>
                <Select
                  value={odRegroupement}
                  onValueChange={(v) => setOdRegroupement(v as OdRegroupement)}
                >
                  <SelectTrigger id="od-regroupement">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">Global</SelectItem>
                    <SelectItem value="par_etablissement">Par établissement</SelectItem>
                    <SelectItem value="par_analytique">Par analytique</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            {/* Paramètres spécifiques aux paiements */}
            {(exportType === "virement-salaires" || exportType === "virement_salaires" || exportType === "recapitulatif-montants" || exportType === "recapitulatif_montants") && (
              <>
                <Separator />
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="execution-date" className="flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      Date d'exécution souhaitée
                    </Label>
                    <Input
                      id="execution-date"
                      type="date"
                      value={executionDate}
                      onChange={(e) => setExecutionDate(e.target.value)}
                      placeholder="Date d'exécution"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="payment-label">
                      Libellé de virement
                    </Label>
                    <Input
                      id="payment-label"
                      value={paymentLabel}
                      onChange={(e) => setPaymentLabel(e.target.value)}
                      placeholder={`Salaire ${selectedPeriod || "mois"}`}
                    />
                    <p className="text-xs text-muted-foreground">
                      Libellé qui apparaîtra sur les relevés bancaires des collaborateurs
                    </p>
                  </div>
                  <div className="space-y-2 max-w-xs">
                    <Label htmlFor="bank-format">Format fichier bancaire</Label>
                    <Select
                      value={bankFileFormat}
                      onValueChange={(v) => setBankFileFormat(v as BankFileFormat)}
                    >
                      <SelectTrigger id="bank-format">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sepa">SEPA pain.001 (XML)</SelectItem>
                        <SelectItem value="csv">CSV bancaire</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </>
            )}

            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Erreur</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-3">
              {onClose && (
                <Button variant="outline" onClick={onClose} disabled={isLoading}>
                  Annuler
                </Button>
              )}
              <Button onClick={handlePreview} disabled={!selectedPeriod || isLoading}>
                {isLoading ? "Prévisualisation..." : "Prévisualiser"}
              </Button>
            </div>
          </div>
        )}

        {/* ÉTAPE 2 : Prévisualisation & Contrôles */}
        {currentStep === "previsualisation" && previewData && (
          <div className="space-y-6">
            {emptyExportMessage ? (
              <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/40">
                <Info className="h-4 w-4 text-blue-600" />
                <AlertDescription className="text-blue-800 dark:text-blue-200">
                  {emptyExportMessage}
                </AlertDescription>
              </Alert>
            ) : null}

            {/* Résumé du périmètre */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Résumé du périmètre</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {(exportType === "virement-salaires" || exportType === "virement_salaires") ? "Virements à générer" : "Collaborateurs concernés"}
                    </p>
                    <p className="text-2xl font-bold">{previewData.employees_count}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Période</p>
                    <p className="text-2xl font-bold">{selectedPeriod}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Montant total</p>
                    <p className="text-2xl font-bold">
                      {previewData.totals.total_net_a_payer?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' }) || 
                       previewData.totals.total_amount?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' }) || 
                       "N/A"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Totaux de contrôle */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  Totaux de contrôle
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  {apiExportType === "acomptes" || apiExportType === "saisies" ? (
                    <>
                      {apiExportType === "acomptes" && previewData.totals.total_versements != null && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total versements :</span>
                          <span className="font-medium">
                            {formatEuro(previewData.totals.total_versements)}
                          </span>
                        </div>
                      )}
                      {apiExportType === "acomptes" && previewData.totals.total_remboursements != null && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total remboursements :</span>
                          <span className="font-medium">
                            {formatEuro(previewData.totals.total_remboursements)}
                          </span>
                        </div>
                      )}
                      {apiExportType === "saisies" && previewData.totals.total_prelevements != null && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total prélèvements :</span>
                          <span className="font-medium">
                            {formatEuro(previewData.totals.total_prelevements)}
                          </span>
                        </div>
                      )}
                      {previewData.totals.operations_count != null && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Opérations :</span>
                          <span className="font-medium">{previewData.totals.operations_count}</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      {previewData.totals.total_brut != null && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total brut :</span>
                          <span className="font-medium">{formatEuro(previewData.totals.total_brut)}</span>
                        </div>
                      )}
                      {hasCotisationsTotals(previewData.totals) && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total cotisations :</span>
                          <span className="font-medium">
                            {formatEuro(
                              (previewData.totals.total_cotisations_salariales ?? 0) +
                                (previewData.totals.total_cotisations_patronales ?? 0),
                            )}
                          </span>
                        </div>
                      )}
                      {previewData.totals.total_net_a_payer != null && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Total net :</span>
                          <span className="font-medium">
                            {formatEuro(previewData.totals.total_net_a_payer)}
                          </span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </CardContent>
            </Card>

            {previewData.details?.organismes && previewData.details.organismes.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Tableau des charges par organisme</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Organisme</TableHead>
                        <TableHead className="text-right">Salariés</TableHead>
                        <TableHead className="text-right">Part salariale</TableHead>
                        <TableHead className="text-right">Part patronale</TableHead>
                        <TableHead className="text-right">Total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewData.details.organismes.map((row) => (
                        <TableRow key={row.organisme}>
                          <TableCell className="font-medium">{row.organisme}</TableCell>
                          <TableCell className="text-right">{row.nombre_salaries}</TableCell>
                          <TableCell className="text-right">
                            {row.total_cotisations_salariales.toLocaleString("fr-FR", {
                              style: "currency",
                              currency: "EUR",
                            })}
                          </TableCell>
                          <TableCell className="text-right">
                            {row.total_cotisations_patronales.toLocaleString("fr-FR", {
                              style: "currency",
                              currency: "EUR",
                            })}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {row.total_cotisations.toLocaleString("fr-FR", {
                              style: "currency",
                              currency: "EUR",
                            })}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            ) : null}

            {/* Anomalies bloquantes (hors export vide) */}
            {blockingAnomalies.length > 0 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Anomalies bloquantes</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {blockingAnomalies.map((anomaly, index) => (
                      <li key={index}>{anomaly.message}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            {/* Avertissements */}
            {previewWarnings.length > 0 && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Avertissements</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {previewWarnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Erreur</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={handleBack} disabled={isLoading}>
                Retour
              </Button>
              <Button 
                onClick={handleGenerate}
                disabled={!previewData.can_generate || isLoading}
              >
                {isLoading ? "Génération..." : "Générer l'export"}
              </Button>
            </div>
          </div>
        )}

        {/* ÉTAPE 3 : Génération */}
        {currentStep === "generation" && generateResponse && (
          <div className="space-y-6">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertTitle>Export généré avec succès</AlertTitle>
              <AlertDescription>
                {(exportType === "virement-salaires" || exportType === "virement_salaires") ? (
                  <>
                    Les fichiers ont été générés et téléchargés automatiquement :
                    <ul className="list-disc list-inside mt-2 space-y-1">
                      {generateResponse.files.map((file, index) => (
                        <li key={index}>{file.filename}</li>
                      ))}
                    </ul>
                    L'export a été enregistré dans l'historique.
                    <p className="mt-2 font-semibold text-orange-700 dark:text-orange-300">
                      ⚠️ Rappel : Ces fichiers ne déclenchent aucun paiement automatiquement. 
                      Transmettez-les manuellement à votre banque après validation.
                    </p>
                  </>
                ) : (
                  <>
                    Le fichier a été généré et téléchargé automatiquement. 
                    L'export a été enregistré dans l'historique.
                  </>
                )}
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Rapport d'export</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Type d'export :</span>
                  <span className="font-medium">{exportType}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Période :</span>
                  <span className="font-medium">{generateResponse.period}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Date de génération :</span>
                  <span className="font-medium">{generateResponse.report.generated_at ? new Date(generateResponse.report.generated_at).toLocaleString('fr-FR') : 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Statut :</span>
                  <Badge variant="default">{generateResponse.status}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Fichiers générés :</span>
                  <span className="font-medium">{generateResponse.files.length}</span>
                </div>
              </CardContent>
            </Card>

            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Erreur</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={handleBack} disabled={isLoading}>
                Retour
              </Button>
              {onClose && (
                <Button onClick={onClose} disabled={isLoading}>
                  Fermer
                </Button>
              )}
            </div>
          </div>
        )}
        </CardContent>
      </Card>
    </div>
  );
}

