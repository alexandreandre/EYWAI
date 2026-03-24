// src/components/exports/ExportCommonModel.tsx
// Modèle commun d'export - ÉTAPE 1 : Structure et UX uniquement

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { 
  Settings, 
  Eye, 
  Download, 
  AlertTriangle, 
  CheckCircle2, 
  Calendar,
  Building,
  Users as UsersIcon
} from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { previewExport, generateExport, ExportPreviewResponse, ExportGenerateResponse, ExportType } from "@/api/exports";
import { useAuth } from "@/contexts/AuthContext";

export type ExportStep = "parametrage" | "previsualisation" | "generation";

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
  // Convertir l'ID technique en nom lisible
  const displayName = exportTypeLabels[exportType] || exportType;
  const { activeCompany } = useCompany();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState<ExportStep>("parametrage");
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<ExportPreviewResponse | null>(null);
  const [generateResponse, setGenerateResponse] = useState<ExportGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // État pour le paramétrage
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [selectedCompany, setSelectedCompany] = useState<string>(activeCompany?.company_id || "");
  const [selectedScope, setSelectedScope] = useState<"all" | "filtered">("all");
  
  // Paramètres spécifiques aux paiements
  const [executionDate, setExecutionDate] = useState<string>("");
  const [paymentLabel, setPaymentLabel] = useState<string>("");
  const [excludedEmployees, setExcludedEmployees] = useState<string[]>([]);

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
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Mapper le nom d'export vers le type API
      // Le exportType peut être soit un ID technique (depuis les onglets), soit un nom affiché (ancien code)
      const exportTypeMap: Record<string, ExportType> = {
        // IDs techniques (nouveaux)
        "journal_paie": "journal_paie",
        "od_salaires": "od_salaires",
        "od_charges_sociales": "od_charges_sociales",
        "od_pas": "od_pas",
        "od_globale": "od_globale",
        "export_cabinet_generique": "export_cabinet_generique",
        "export_cabinet_quadra": "export_cabinet_quadra",
        "export_cabinet_sage": "export_cabinet_sage",
        "dsn_mensuelle": "dsn_mensuelle",
        "virement_salaires": "virement_salaires",
        "charges_sociales": "charges_sociales",
        "conges_absences": "conges_absences",
        "notes_frais": "notes_frais",
        // Noms affichés (ancien code pour compatibilité)
        "Journal de paie": "journal_paie",
        "Écritures comptables (OD)": "ecritures_comptables",
        "Charges sociales par caisse": "charges_sociales",
        "Congés payés / Absences": "conges_absences",
        "Notes de frais": "notes_frais",
        "DSN mensuelle": "dsn_mensuelle",
        "Virement salaires": "virement_salaires",
        "Récapitulatif des montants": "recapitulatif_montants",
      };
      
      const apiExportType = exportTypeMap[exportType] || exportType as ExportType;
      
      const preview = await previewExport({
        export_type: apiExportType,
        period: selectedPeriod,
        company_id: selectedCompany,
        employee_ids: selectedScope === "all" ? undefined : [],
        excluded_employee_ids: excludedEmployees.length > 0 ? excludedEmployees : undefined,
        execution_date: executionDate || undefined,
        payment_label: paymentLabel || undefined,
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
      // Le exportType peut être soit un ID technique (depuis les onglets), soit un nom affiché (ancien code)
      const exportTypeMap: Record<string, ExportType> = {
        // IDs techniques (nouveaux)
        "journal_paie": "journal_paie",
        "od_salaires": "od_salaires",
        "od_charges_sociales": "od_charges_sociales",
        "od_pas": "od_pas",
        "od_globale": "od_globale",
        "export_cabinet_generique": "export_cabinet_generique",
        "export_cabinet_quadra": "export_cabinet_quadra",
        "export_cabinet_sage": "export_cabinet_sage",
        "dsn_mensuelle": "dsn_mensuelle",
        "virement_salaires": "virement_salaires",
        "charges_sociales": "charges_sociales",
        "conges_absences": "conges_absences",
        "notes_frais": "notes_frais",
        // Noms affichés (ancien code pour compatibilité)
        "Journal de paie": "journal_paie",
        "Écritures comptables (OD)": "ecritures_comptables",
        "Charges sociales par caisse": "charges_sociales",
        "Congés payés / Absences": "conges_absences",
        "Notes de frais": "notes_frais",
        "DSN mensuelle": "dsn_mensuelle",
        "Virement salaires": "virement_salaires",
      };
      
      const apiExportType = exportTypeMap[exportType] || exportType as ExportType;
      
      const response = await generateExport({
        export_type: apiExportType,
        period: selectedPeriod,
        company_id: selectedCompany,
        employee_ids: selectedScope === "all" ? undefined : [],
        format: "csv", // Par défaut CSV, peut être changé plus tard
        excluded_employee_ids: excludedEmployees.length > 0 ? excludedEmployees : undefined,
        execution_date: executionDate || undefined,
        payment_label: paymentLabel || undefined,
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
    if (currentStep === "previsualisation") {
      setCurrentStep("parametrage");
    } else if (currentStep === "generation") {
      setCurrentStep("previsualisation");
    }
  };

  return (
    <div className="w-full space-y-4">
      {/* Titre et description en dehors du Card */}
      <div>
        <h2 className="text-xl font-semibold">{displayName}</h2>
        <p className="text-sm text-muted-foreground mt-1">{exportDescription}</p>
        {(displayName === "Virement salaires" || displayName === "Récapitulatif des montants") && (
          <Alert className="mt-3 border-orange-200 bg-orange-50 dark:bg-orange-950">
            <AlertTriangle className="h-4 w-4 text-orange-600" />
            <AlertTitle className="text-orange-800 dark:text-orange-200">Important</AlertTitle>
            <AlertDescription className="text-orange-700 dark:text-orange-300">
              Ce fichier ne déclenche aucun paiement automatiquement. 
              Il doit être transmis manuellement à votre banque après validation.
            </AlertDescription>
          </Alert>
        )}
      </div>
      
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

            {/* Périmètre */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2">
                <UsersIcon className="h-4 w-4" />
                Périmètre collaborateur
              </Label>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="scope-all"
                  checked={selectedScope === "all"}
                  onCheckedChange={(checked) => checked && setSelectedScope("all")}
                />
                <Label htmlFor="scope-all" className="font-normal cursor-pointer">
                  Tous les collaborateurs
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="scope-filtered"
                  checked={selectedScope === "filtered"}
                  onCheckedChange={(checked) => checked && setSelectedScope("filtered")}
                />
                <Label htmlFor="scope-filtered" className="font-normal cursor-pointer">
                  Filtrer par critères (à venir)
                </Label>
              </div>
            </div>

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
                </div>
              </>
            )}

            <div className="flex justify-end gap-3">
              {onClose && (
                <Button variant="outline" onClick={onClose}>
                  Annuler
                </Button>
              )}
              <Button onClick={handlePreview} disabled={!selectedPeriod}>
                Prévisualiser
              </Button>
            </div>
          </div>
        )}

        {/* ÉTAPE 2 : Prévisualisation & Contrôles */}
        {currentStep === "previsualisation" && previewData && (
          <div className="space-y-6">
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
                  {previewData.totals.total_brut !== undefined && previewData.totals.total_brut !== null && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total brut :</span>
                      <span className="font-medium">{previewData.totals.total_brut.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                    </div>
                  )}
                  {(previewData.totals.total_cotisations_salariales !== undefined || previewData.totals.total_cotisations_patronales !== undefined) && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total cotisations :</span>
                      <span className="font-medium">
                        {((previewData.totals.total_cotisations_salariales ?? 0) + (previewData.totals.total_cotisations_patronales ?? 0)).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                      </span>
                    </div>
                  )}
                  {previewData.totals.total_net_a_payer !== undefined && previewData.totals.total_net_a_payer !== null && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total net :</span>
                      <span className="font-medium">{previewData.totals.total_net_a_payer.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Anomalies bloquantes */}
            {previewData.anomalies.filter(a => a.severity === "blocking").length > 0 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Anomalies bloquantes</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {previewData.anomalies
                      .filter(a => a.severity === "blocking")
                      .map((anomaly, index) => (
                        <li key={index}>{anomaly.message}</li>
                      ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            {/* Avertissements */}
            {previewData.warnings.length > 0 && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Avertissements</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {previewData.warnings.map((warning, index) => (
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

