// src/components/SaisieModal.tsx (VERSION FINALE ET DÉFINITIVE)

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { ChevronsUpDown, Check, Plus, Sparkles, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import apiClient from "@/api/apiClient";
import * as saisiesApi from "@/api/saisies";
import * as bonusTypesApi from "@/api/bonusTypes";
import * as calendarApi from "@/api/calendar";
import type { BonusType } from "@/api/bonusTypes";

// --- Types & Interfaces ---
interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string;
}

type PrimeFromCatalogue = saisiesApi.PrimeFromCatalogue;
type MonthlyInputCreate = saisiesApi.MonthlyInputCreate; // Le type pour notre payload

interface SaisieModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: MonthlyInputCreate[]) => void;
  employees: Employee[];
  employeeScopeId?: string;
  year?: number;
  month?: number;
}

const initialState = {
  name: "",
  amount: "" as number | "",
  description: "",
  selectedEmployees: [] as string[],
  is_socially_taxed: true,
  is_taxable: true,
};

const initialPrimeForm = {
  libelle: "",
  type: "montant_fixe" as "montant_fixe" | "selon_heures",
  montant: "" as number | "",
  seuil_heures: "" as number | "",
  soumise_a_cotisations: true,
  soumise_a_impot: true,
  prompt_ia: "",
  saveToCatalogue: false,
};

export function SaisieModal({ isOpen, onClose, onSave, employees, employeeScopeId, year, month }: SaisieModalProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const [formData, setFormData] = useState(initialState);
  const [primesCatalogue, setPrimesCatalogue] = useState<PrimeFromCatalogue[]>([]);
  const [bonusTypes, setBonusTypes] = useState<BonusType[]>([]);
  const [isCustomPrime, setIsCustomPrime] = useState(true);
  const [selectedBonusTypeId, setSelectedBonusTypeId] = useState<string | null>(null);
  const [showCreatePrimeForm, setShowCreatePrimeForm] = useState(false);
  const [primeForm, setPrimeForm] = useState(initialPrimeForm);
  const [isCalculating, setIsCalculating] = useState(false);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [employeePopoverOpen, setEmployeePopoverOpen] = useState(false);

  const canSaveToCatalogue = user?.role === 'admin' || user?.role === 'rh' || user?.role === 'super_admin';

  useEffect(() => {
    // Charger les primes depuis le catalogue (ancien système)
    saisiesApi.getPrimesCatalogue().then(res => setPrimesCatalogue(res.data || []));
    // Charger les bonus types depuis la nouvelle table
    bonusTypesApi.getBonusTypes()
      .then(res => setBonusTypes(res.data || []))
      .catch(err => {
        console.warn("Erreur lors du chargement des bonus types:", err);
        // Si l'endpoint n'existe pas encore, on continue avec l'ancien système
      });
  }, []);

  // Recharger les bonus types après création
  const reloadBonusTypes = () => {
    bonusTypesApi.getBonusTypes()
      .then(res => setBonusTypes(res.data || []))
      .catch(() => {});
  };

  useEffect(() => {
    if (isOpen) {
      setFormData(initialState);
      setPrimeForm(initialPrimeForm);
      setIsCustomPrime(true);
      setSelectedBonusTypeId(null);
      setShowCreatePrimeForm(false);
      setIsCalculating(false);
      if (employeeScopeId) {
        setFormData(prev => ({ ...prev, selectedEmployees: [employeeScopeId] }));
      }
    }
  }, [isOpen, employeeScopeId]);

  const handleSave = async () => {
    if (!formData.name || formData.amount === "" || formData.selectedEmployees.length === 0) {
      toast({
        title: "Erreur",
        description: "Veuillez remplir le nom, le montant et sélectionner au moins un employé.",
        variant: "destructive",
      });
      return;
    }

    const currentYear = year || new Date().getFullYear();
    const currentMonth = month || new Date().getMonth() + 1;

    // Si une prime "selon_heures" a été créée à la volée, calculer le montant pour chaque employé
    const amountsByEmployee: Record<string, number> = {};
    if (showCreatePrimeForm && primeForm.type === "selon_heures") {
      setIsCalculating(true);
      try {
        // Calculer le montant pour chaque employé sélectionné
        for (const empId of formData.selectedEmployees) {
          try {
            // Récupérer les heures réelles du mois
            const hoursResponse = await calendarApi.getActualHours(empId, currentYear, currentMonth);
            
            let totalHours = 0.0;
            if (hoursResponse.data?.calendrier_reel) {
              totalHours = hoursResponse.data.calendrier_reel.reduce(
                (sum: number, day: any) => sum + (parseFloat(day.heures_faites || 0)),
                0
              );
            }

            // Comparer avec le seuil
            const seuil = Number(primeForm.seuil_heures);
            amountsByEmployee[empId] = totalHours >= seuil ? Number(primeForm.montant) : 0.0;
          } catch (error) {
            console.error(`Erreur lors du calcul pour l'employé ${empId}:`, error);
            // En cas d'erreur, utiliser le montant par défaut
            amountsByEmployee[empId] = Number(formData.amount);
          }
        }
      } catch (error) {
        console.error("Erreur lors du calcul des montants:", error);
        toast({
          title: "Avertissement",
          description: "Impossible de calculer automatiquement les montants. Le montant saisi sera utilisé pour tous les employés.",
          variant: "default",
        });
      } finally {
        setIsCalculating(false);
      }
    }

    // Si une prime a été créée et doit être enregistrée dans le catalogue
    if (showCreatePrimeForm && primeForm.saveToCatalogue && canSaveToCatalogue) {
      try {
        await bonusTypesApi.createBonusType({
          libelle: primeForm.libelle,
          type: primeForm.type,
          montant: Number(primeForm.montant),
          seuil_heures: primeForm.type === "selon_heures" ? Number(primeForm.seuil_heures) : null,
          soumise_a_cotisations: primeForm.soumise_a_cotisations,
          soumise_a_impot: primeForm.soumise_a_impot,
          prompt_ia: primeForm.prompt_ia || null,
        });
        reloadBonusTypes();
        toast({
          title: "Succès",
          description: "Prime enregistrée dans le catalogue.",
        });
      } catch (error) {
        console.error("Erreur lors de l'enregistrement de la prime:", error);
        toast({
          title: "Erreur",
          description: "Impossible d'enregistrer la prime dans le catalogue.",
          variant: "destructive",
        });
      }
    }

    // Créer les payloads pour chaque employé avec le montant calculé si disponible
    const payloads: MonthlyInputCreate[] = formData.selectedEmployees.map(empId => ({
      employee_id: empId,
      name: formData.name,
      description: formData.description || undefined,
      amount: amountsByEmployee[empId] !== undefined ? amountsByEmployee[empId] : Number(formData.amount),
      is_socially_taxed: formData.is_socially_taxed,
      is_taxable: formData.is_taxable,
      year: currentYear,
      month: currentMonth,
    }));
    onSave(payloads);
  };
  
  const handlePrimeSelect = (prime: PrimeFromCatalogue) => {
    setFormData(prev => ({
      ...prev,
      name: prime.libelle,
      is_socially_taxed: prime.soumise_a_cotisations,
      is_taxable: prime.soumise_a_impot,
    }));
    setIsCustomPrime(false);
    setSelectedBonusTypeId(null);
    setShowCreatePrimeForm(false);
  };

  const handleBonusTypeSelect = async (bonusTypeId: string) => {
    const bonusType = bonusTypes.find(bt => bt.id === bonusTypeId);
    if (!bonusType) return;

    setSelectedBonusTypeId(bonusTypeId);
    setIsCustomPrime(false);
    setShowCreatePrimeForm(false);

    setFormData(prev => ({
      ...prev,
      name: bonusType.libelle,
      is_socially_taxed: bonusType.soumise_a_cotisations,
      is_taxable: bonusType.soumise_a_impot,
    }));

    // Si c'est un type "selon_heures", calculer le montant pour chaque employé sélectionné
    if (bonusType.type === "selon_heures" && formData.selectedEmployees.length > 0) {
      setIsCalculating(true);
      try {
        const currentYear = year || new Date().getFullYear();
        const currentMonth = month || new Date().getMonth() + 1;
        
        // Pour l'instant, on calcule pour le premier employé (on pourrait améliorer pour plusieurs)
        const employeeId = formData.selectedEmployees[0];
        const result = await bonusTypesApi.calculateBonusAmount(
          bonusTypeId,
          employeeId,
          currentYear,
          currentMonth
        );
        
        setFormData(prev => ({
          ...prev,
          amount: result.data.amount,
        }));

        if (result.data.condition_met === false) {
          toast({
            title: "Information",
            description: `La condition n'est pas remplie (${result.data.total_hours}h < ${result.data.seuil}h). Montant: 0€`,
          });
        }
      } catch (error) {
        console.error("Erreur lors du calcul:", error);
        toast({
          title: "Erreur",
          description: "Impossible de calculer le montant automatiquement.",
          variant: "destructive",
        });
      } finally {
        setIsCalculating(false);
      }
    } else {
      // Montant fixe
      setFormData(prev => ({
        ...prev,
        amount: bonusType.montant,
      }));
    }
  };

  const handleCreatePrimeClick = () => {
    setShowCreatePrimeForm(true);
    setSelectedBonusTypeId(null);
    setIsCustomPrime(true);
    setFormData(prev => ({ ...prev, name: "", amount: "" }));
  };

  const handleCreatePrimeFormChange = (field: string, value: any) => {
    setPrimeForm(prev => ({ ...prev, [field]: value }));
    
    // Si on change le type, réinitialiser les champs spécifiques
    if (field === "type") {
      if (value === "montant_fixe") {
        setPrimeForm(prev => ({ ...prev, seuil_heures: "" }));
      }
    }

    // Mettre à jour le formulaire principal avec les valeurs de la prime
    if (field === "libelle") {
      setFormData(prev => ({ ...prev, name: value }));
    }
    if (field === "montant") {
      // Synchroniser le montant pour tous les types (il sera calculé plus tard pour "selon_heures")
      setFormData(prev => ({ ...prev, amount: value ? parseFloat(value) : "" }));
    }
    if (field === "soumise_a_cotisations") {
      setFormData(prev => ({ ...prev, is_socially_taxed: value }));
    }
    if (field === "soumise_a_impot") {
      setFormData(prev => ({ ...prev, is_taxable: value }));
    }
  };
  
  const handleCustomInputChange = (value: string) => {
    setFormData(prev => ({ ...prev, name: value }));
    // Si l'utilisateur tape un nom qui ne correspond à aucune prime du catalogue, on active les cases
    const isStandardPrime = primesCatalogue.some(p => p.libelle === value) ||
                           bonusTypes.some(bt => bt.libelle === value);
    setIsCustomPrime(!isStandardPrime);
    setSelectedBonusTypeId(null);
    setShowCreatePrimeForm(false);
  };

  const handleSelectAll = () => {
    if (formData.selectedEmployees.length === employees.length) {
        setFormData(prev => ({ ...prev, selectedEmployees: [] }));
    } else {
        setFormData(prev => ({ ...prev, selectedEmployees: employees.map(e => e.id) }));
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-background/80 backdrop-blur-xl border-white/20 sm:max-w-md max-h-[90vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle>Ajouter une Saisie du Mois</DialogTitle>
          <DialogDescription>
            {employeeScopeId ? "Cette saisie ponctuelle ne s'appliquera que pour le mois en cours." : "Créez une saisie pour un ou plusieurs employés."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4 overflow-y-auto flex-1 min-h-0">
          
          {/* Masquer le champ "Nom / Type de Saisie" si on est en mode création de prime */}
          {!showCreatePrimeForm && (
            <div className="grid gap-2">
              <Label>Nom / Type de Saisie</Label>
              <div className="flex gap-2">
                <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
                  <PopoverTrigger asChild>
                    <Input 
                      placeholder="Sélectionnez ou saisissez un nom..."
                      value={formData.name}
                      onChange={e => handleCustomInputChange(e.target.value)}
                      onClick={() => setPopoverOpen(true)}
                      className="flex-1"
                    />
                  </PopoverTrigger>
                  <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                    <Command>
                      <CommandInput placeholder="Rechercher une prime..." />
                      <CommandList>
                        <CommandEmpty>Aucune prime trouvée. Le nom saisi sera utilisé.</CommandEmpty>
                        {bonusTypes.length > 0 && (
                          <CommandGroup heading="Primes de l'entreprise">
                            {bonusTypes.map((prime) => (
                              <CommandItem key={prime.id} value={prime.libelle} onSelect={() => {
                                handleBonusTypeSelect(prime.id);
                                setPopoverOpen(false);
                              }}>
                                <Check className={cn("mr-2 h-4 w-4", selectedBonusTypeId === prime.id ? "opacity-100" : "opacity-0")}/>
                                <div className="flex flex-col gap-1">
                                  <div className="flex items-center gap-2">
                                    <span>{prime.libelle}</span>
                                    {prime.type === "selon_heures" && (
                                      <span className="text-xs text-muted-foreground">
                                        (si ≥ {prime.seuil_heures}h)
                                      </span>
                                    )}
                                  </div>
                                  {prime.prompt_ia && (
                                    <p className="text-xs text-muted-foreground italic">
                                      {prime.prompt_ia}
                                    </p>
                                  )}
                                </div>
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        )}
                        {primesCatalogue.length > 0 && (
                          <CommandGroup heading="Primes Standard">
                            {primesCatalogue.map((prime) => (
                              <CommandItem key={prime.id} value={prime.libelle} onSelect={() => {
                                handlePrimeSelect(prime);
                                setPopoverOpen(false);
                              }}>
                                <Check className={cn("mr-2 h-4 w-4", formData.name === prime.libelle && !isCustomPrime && !selectedBonusTypeId ? "opacity-100" : "opacity-0")}/>
                                {prime.libelle}
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        )}
                        <CommandGroup>
                          <CommandItem onSelect={() => {
                            handleCreatePrimeClick();
                            setPopoverOpen(false);
                          }}>
                            <Plus className="mr-2 h-4 w-4" />
                            <span className="font-medium">Créer une prime...</span>
                          </CommandItem>
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>
            </div>
          )}

          {/* Formulaire de création de prime */}
          {showCreatePrimeForm && (
            <div className="border rounded-lg p-4 space-y-4 bg-muted/50">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => {
                    setShowCreatePrimeForm(false);
                    setPrimeForm(initialPrimeForm);
                    setFormData(prev => ({ ...prev, name: "", amount: "" }));
                  }}
                  title="Retour au formulaire principal"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Sparkles className="h-4 w-4" />
                <Label className="font-semibold">Créer une nouvelle prime</Label>
              </div>
              
              <div className="grid gap-2">
                <Label>Nom de la prime *</Label>
                <Input
                  value={primeForm.libelle}
                  onChange={e => handleCreatePrimeFormChange("libelle", e.target.value)}
                  placeholder="Ex: Prime d'assiduité"
                />
              </div>

              <div className="grid gap-2">
                <Label>Type de prime *</Label>
                <Select
                  value={primeForm.type}
                  onValueChange={(value) => handleCreatePrimeFormChange("type", value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="montant_fixe">Montant fixe</SelectItem>
                    <SelectItem value="selon_heures">Selon heures faites</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {primeForm.type === "montant_fixe" ? (
                <div className="grid gap-2">
                  <Label>Montant (€) *</Label>
                  <Input
                    type="number"
                    value={primeForm.montant}
                    onChange={e => {
                      const val = e.target.value ? parseFloat(e.target.value) : "";
                      handleCreatePrimeFormChange("montant", val);
                    }}
                    placeholder="0.00"
                  />
                </div>
              ) : (
                <>
                  <div className="grid gap-2">
                    <Label>Seuil d'heures *</Label>
                    <Input
                      type="number"
                      value={primeForm.seuil_heures}
                      onChange={e => handleCreatePrimeFormChange("seuil_heures", e.target.value ? parseFloat(e.target.value) : "")}
                      placeholder="Ex: 150"
                    />
                    <p className="text-xs text-muted-foreground">
                      Si heures du mois ≥ seuil, alors montant = X, sinon 0
                    </p>
                  </div>
                  <div className="grid gap-2">
                    <Label>Montant si condition remplie (€) *</Label>
                    <Input
                      type="number"
                      value={primeForm.montant}
                      onChange={e => {
                        const val = e.target.value ? parseFloat(e.target.value) : "";
                        handleCreatePrimeFormChange("montant", val);
                      }}
                      placeholder="0.00"
                    />
                  </div>
                </>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="prime_soumise_cotisations"
                    checked={primeForm.soumise_a_cotisations}
                    onCheckedChange={(c) => handleCreatePrimeFormChange("soumise_a_cotisations", !!c)}
                  />
                  <Label htmlFor="prime_soumise_cotisations" className="cursor-pointer text-sm">
                    Soumise à cotisations
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="prime_soumise_impot"
                    checked={primeForm.soumise_a_impot}
                    onCheckedChange={(c) => handleCreatePrimeFormChange("soumise_a_impot", !!c)}
                  />
                  <Label htmlFor="prime_soumise_impot" className="cursor-pointer text-sm">
                    Soumise à impôt
                  </Label>
                </div>
              </div>

              <div className="grid gap-2">
                <Label>Description (optionnel)</Label>
                <Input
                  value={primeForm.prompt_ia}
                  onChange={e => handleCreatePrimeFormChange("prompt_ia", e.target.value)}
                  placeholder="Ex: Prime versée si l'employé a fait au moins 150h dans le mois"
                />
                <p className="text-xs text-muted-foreground">
                  Cette description s'affichera dans le menu de sélection pour aider à identifier la prime
                </p>
              </div>

              {canSaveToCatalogue && (
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="save_to_catalogue"
                    checked={primeForm.saveToCatalogue}
                    onCheckedChange={(c) => handleCreatePrimeFormChange("saveToCatalogue", !!c)}
                  />
                  <Label htmlFor="save_to_catalogue" className="cursor-pointer">
                    Enregistrer dans les primes de l'entreprise
                  </Label>
                </div>
              )}

              {!canSaveToCatalogue && (
                <p className="text-xs text-muted-foreground">
                  Seuls les Admin/RH peuvent enregistrer une prime dans le catalogue.
                </p>
              )}

              {/* Aperçu du montant qui sera utilisé pour la saisie */}
              {primeForm.montant && (
                <div className="border-t pt-4 mt-4">
                  <p className="text-sm font-medium mb-2">Aperçu de la saisie :</p>
                  <div className="bg-background/50 rounded p-3 space-y-1">
                    <p className="text-sm">
                      <span className="font-medium">Montant :</span>{" "}
                      {primeForm.type === "selon_heures" 
                        ? `${new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(Number(primeForm.montant))} (si ≥ ${primeForm.seuil_heures}h)` 
                        : new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(Number(primeForm.montant))}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Soumise à cotisations :</span> {primeForm.soumise_a_cotisations ? 'Oui' : 'Non'}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Soumise à impôt :</span> {primeForm.soumise_a_impot ? 'Oui' : 'Non'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Masquer les champs du formulaire principal si on est en mode création de prime */}
          {!showCreatePrimeForm && (
            <>
              <div className="grid gap-2">
                <Label>Montant (€) {isCalculating && <span className="text-muted-foreground">(calcul en cours...)</span>}</Label>
                <Input
                  type="number"
                  value={formData.amount}
                  onChange={e => setFormData(p => ({ ...p, amount: e.target.value ? parseFloat(e.target.value) : '' }))}
                  disabled={isCalculating || (selectedBonusTypeId && bonusTypes.find(bt => bt.id === selectedBonusTypeId)?.type === "selon_heures")}
                />
                {selectedBonusTypeId && bonusTypes.find(bt => bt.id === selectedBonusTypeId)?.type === "selon_heures" && (
                  <p className="text-xs text-muted-foreground">
                    Le montant est calculé automatiquement selon les heures faites.
                  </p>
                )}
              </div>
              
              <div className="grid grid-cols-2 gap-4 pt-2">
                <div className="flex items-center space-x-2">
                  <Checkbox id="is_socially_taxed" checked={formData.is_socially_taxed} disabled={!isCustomPrime} onCheckedChange={(c) => setFormData(p => ({ ...p, is_socially_taxed: !!c }))}/>
                  <Label htmlFor="is_socially_taxed" className={cn("cursor-pointer", !isCustomPrime && "text-muted-foreground")}>Soumise à cotisations</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox id="is_taxable" checked={formData.is_taxable} disabled={!isCustomPrime} onCheckedChange={(c) => setFormData(p => ({ ...p, is_taxable: !!c }))}/>
                  <Label htmlFor="is_taxable" className={cn("cursor-pointer", !isCustomPrime && "text-muted-foreground")}>Soumise à impôt</Label>
                </div>
              </div>
            </>
          )}
          
          {!employeeScopeId && (
             <div className="grid gap-2">
              <Label>Appliquer à</Label>
              <Popover open={employeePopoverOpen} onOpenChange={setEmployeePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" role="combobox" className="w-full justify-between font-normal">
                    {formData.selectedEmployees.length > 0 ? `${formData.selectedEmployees.length} employé(s) sélectionné(s)`: "Sélectionner des employés..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                  <Command>
                    <CommandInput placeholder="Rechercher un employé..." />
                    <CommandList>
                      <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem onSelect={handleSelectAll} className="cursor-pointer">
                          <Check className={cn("mr-2 h-4 w-4", formData.selectedEmployees.length === employees.length ? "opacity-100" : "opacity-0")}/>
                          {formData.selectedEmployees.length === employees.length ? "Tout désélectionner" : "Tout sélectionner"}
                        </CommandItem>
                        {employees.map((employee) => (
                          <CommandItem key={employee.id} value={`${employee.first_name} ${employee.last_name}`} onSelect={() => {
                            const isSelected = formData.selectedEmployees.includes(employee.id);
                            setFormData((p) => ({...p, selectedEmployees: isSelected ? p.selectedEmployees.filter((id) => id !== employee.id) : [...p.selectedEmployees, employee.id]}));
                          }}>
                            <Check className={cn("mr-2 h-4 w-4", formData.selectedEmployees.includes(employee.id) ? "opacity-100" : "opacity-0")}/>
                            <div>
                              <p>{employee.first_name} {employee.last_name}</p>
                              <p className="text-xs text-muted-foreground">{employee.job_title}</p>
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          )}

        </div>
        <DialogFooter className="flex-shrink-0 border-t pt-4 mt-4">
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={handleSave}>Enregistrer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}