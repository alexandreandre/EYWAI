// frontend/src/components/PromotionModal.tsx
// Modal pour créer ou éditer une promotion

import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import { Loader2 } from "lucide-react";
import {
  createPromotion,
  updatePromotion,
  type Promotion,
  type PromotionCreate,
  type PromotionUpdate,
  type PromotionType,
  type RhAccessRole,
  type Salary,
  type Classification,
} from "@/api/promotions";

interface PromotionModalProps {
  isOpen: boolean;
  onClose: () => void;
  promotion?: Promotion | null;
  initialEmployeeId?: string;
  onSuccess: () => void;
}

const PROMOTION_TYPE_OPTIONS: { value: PromotionType; label: string }[] = [
  { value: "poste", label: "Changement de poste" },
  { value: "salaire", label: "Augmentation de salaire" },
  { value: "statut", label: "Changement de statut" },
  { value: "classification", label: "Changement de classification" },
  { value: "mixte", label: "Promotion mixte" },
];

const RH_ACCESS_OPTIONS: { value: RhAccessRole; label: string }[] = [
  { value: "collaborateur_rh", label: "Collaborateur RH" },
  { value: "rh", label: "RH" },
  { value: "admin", label: "Administrateur" },
];

const STATUT_OPTIONS = ["Cadre", "Non-Cadre"];

export function PromotionModal({
  isOpen,
  onClose,
  promotion,
  initialEmployeeId,
  onSuccess,
}: PromotionModalProps) {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  // États du formulaire
  const [employeeId, setEmployeeId] = useState<string>(initialEmployeeId || promotion?.employee_id || "");
  const [promotionType, setPromotionType] = useState<PromotionType>(promotion?.promotion_type || "poste");
  const [newJobTitle, setNewJobTitle] = useState<string>(promotion?.new_job_title || "");
  const [newSalaryValue, setNewSalaryValue] = useState<string>(
    promotion?.new_salary?.valeur?.toString() || ""
  );
  const [newSalaryCurrency, setNewSalaryCurrency] = useState<string>(
    promotion?.new_salary?.devise || "EUR"
  );
  const [newStatut, setNewStatut] = useState<string>(promotion?.new_statut || "");
  const [newCoefficient, setNewCoefficient] = useState<string>(
    promotion?.new_classification?.coefficient?.toString() || ""
  );
  const [newClasseEmploi, setNewClasseEmploi] = useState<string>(
    promotion?.new_classification?.classe_emploi?.toString() || ""
  );
  const [newGroupeEmploi, setNewGroupeEmploi] = useState<string>(
    promotion?.new_classification?.groupe_emploi || ""
  );
  const [effectiveDate, setEffectiveDate] = useState<string>(
    promotion?.effective_date ? promotion.effective_date.split("T")[0] : ""
  );
  const [reason, setReason] = useState<string>(promotion?.reason || "");
  const [justification, setJustification] = useState<string>(promotion?.justification || "");
  const [grantRhAccess, setGrantRhAccess] = useState<boolean>(promotion?.grant_rh_access || false);
  const [newRhAccess, setNewRhAccess] = useState<RhAccessRole | null>(
    promotion?.new_rh_access || null
  );

  // Réinitialiser le formulaire quand le modal s'ouvre ou que la promotion change
  useEffect(() => {
    if (isOpen) {
      if (promotion) {
        // Mode édition
        setEmployeeId(promotion.employee_id);
        setPromotionType(promotion.promotion_type);
        setNewJobTitle(promotion.new_job_title || "");
        setNewSalaryValue(promotion.new_salary?.valeur?.toString() || "");
        setNewSalaryCurrency(promotion.new_salary?.devise || "EUR");
        setNewStatut(promotion.new_statut || "");
        setNewCoefficient(promotion.new_classification?.coefficient?.toString() || "");
        setNewClasseEmploi(promotion.new_classification?.classe_emploi?.toString() || "");
        setNewGroupeEmploi(promotion.new_classification?.groupe_emploi || "");
        setEffectiveDate(promotion.effective_date ? promotion.effective_date.split("T")[0] : "");
        setReason(promotion.reason || "");
        setJustification(promotion.justification || "");
        setGrantRhAccess(promotion.grant_rh_access || false);
        setNewRhAccess(promotion.new_rh_access || null);
      } else {
        // Mode création
        setEmployeeId(initialEmployeeId || "");
        setPromotionType("poste");
        setNewJobTitle("");
        setNewSalaryValue("");
        setNewSalaryCurrency("EUR");
        setNewStatut("");
        setNewCoefficient("");
        setNewClasseEmploi("");
        setNewGroupeEmploi("");
        setEffectiveDate("");
        setReason("");
        setJustification("");
        setGrantRhAccess(false);
        setNewRhAccess(null);
      }
    }
  }, [isOpen, promotion, initialEmployeeId]);

  const handleSubmit = async () => {
    // Validation
    if (!employeeId) {
      toast({
        title: "Erreur",
        description: "L'ID de l'employé est requis.",
        variant: "destructive",
      });
      return;
    }

    if (!effectiveDate) {
      toast({
        title: "Erreur",
        description: "La date d'effet est requise.",
        variant: "destructive",
      });
      return;
    }

    // Validation selon le type de promotion
    if (promotionType === "poste" && !newJobTitle) {
      toast({
        title: "Erreur",
        description: "Le nouveau poste est requis pour un changement de poste.",
        variant: "destructive",
      });
      return;
    }

    if (promotionType === "salaire" && !newSalaryValue) {
      toast({
        title: "Erreur",
        description: "Le nouveau salaire est requis pour une augmentation de salaire.",
        variant: "destructive",
      });
      return;
    }

    if (promotionType === "statut" && !newStatut) {
      toast({
        title: "Erreur",
        description: "Le nouveau statut est requis pour un changement de statut.",
        variant: "destructive",
      });
      return;
    }

    if (promotionType === "classification" && !newCoefficient && !newClasseEmploi && !newGroupeEmploi) {
      toast({
        title: "Erreur",
        description: "Au moins un champ de classification est requis.",
        variant: "destructive",
      });
      return;
    }

    if (grantRhAccess && !newRhAccess) {
      toast({
        title: "Erreur",
        description: "Veuillez sélectionner un rôle d'accès RH.",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);

    try {
      const newSalary: Salary | null =
        newSalaryValue && newSalaryCurrency
          ? {
              valeur: parseFloat(newSalaryValue),
              devise: newSalaryCurrency,
            }
          : null;

      const newClassification: Classification | null =
        newCoefficient || newClasseEmploi || newGroupeEmploi
          ? {
              coefficient: newCoefficient ? parseInt(newCoefficient) : undefined,
              classe_emploi: newClasseEmploi ? parseInt(newClasseEmploi) : undefined,
              groupe_emploi: newGroupeEmploi || undefined,
            }
          : null;

      if (promotion) {
        // Mode édition
        const updateData: PromotionUpdate = {
          promotion_type: promotionType,
          new_job_title: promotionType === "poste" || promotionType === "mixte" ? newJobTitle || null : null,
          new_salary: promotionType === "salaire" || promotionType === "mixte" ? newSalary : null,
          new_statut: promotionType === "statut" || promotionType === "mixte" ? newStatut || null : null,
          new_classification:
            promotionType === "classification" || promotionType === "mixte" ? newClassification : null,
          effective_date: effectiveDate,
          reason: reason || null,
          justification: justification || null,
          grant_rh_access: grantRhAccess,
          new_rh_access: grantRhAccess ? newRhAccess : null,
        };

        await updatePromotion(promotion.id, updateData);
        toast({
          title: "Succès",
          description: "La promotion a été mise à jour avec succès.",
        });
      } else {
        // Mode création
        // Déterminer le statut : effective si date <= aujourd'hui, sinon draft
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const effectiveDateObj = new Date(effectiveDate);
        effectiveDateObj.setHours(0, 0, 0, 0);
        const initialStatus = effectiveDateObj <= today ? "effective" : "draft";

        const createData: PromotionCreate = {
          employee_id: employeeId,
          promotion_type: promotionType,
          new_job_title: promotionType === "poste" || promotionType === "mixte" ? newJobTitle || null : null,
          new_salary: promotionType === "salaire" || promotionType === "mixte" ? newSalary : null,
          new_statut: promotionType === "statut" || promotionType === "mixte" ? newStatut || null : null,
          new_classification:
            promotionType === "classification" || promotionType === "mixte" ? newClassification : null,
          effective_date: effectiveDate,
          reason: reason || null,
          justification: justification || null,
          status: initialStatus,
          grant_rh_access: grantRhAccess,
          new_rh_access: grantRhAccess ? newRhAccess : null,
        };

        await createPromotion(createData);
        toast({
          title: "Succès",
          description: initialStatus === "effective" 
            ? "La promotion a été créée et appliquée avec succès."
            : "La promotion a été créée en brouillon. Marquez-la comme effective quand la date d'effet arrive.",
        });
      }

      onSuccess();
      onClose();
    } catch (error: any) {
      console.error("Erreur lors de la sauvegarde de la promotion:", error);
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Une erreur est survenue lors de la sauvegarde.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const showJobTitleField =
    promotionType === "poste" || promotionType === "mixte";
  const showSalaryField =
    promotionType === "salaire" || promotionType === "mixte";
  const showStatutField =
    promotionType === "statut" || promotionType === "mixte";
  const showClassificationField =
    promotionType === "classification" || promotionType === "mixte";

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {promotion ? "Modifier la promotion" : "Créer une promotion"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* ID Employé (seulement en mode création si non pré-rempli) */}
          {!promotion && !initialEmployeeId && (
            <div className="space-y-2">
              <Label htmlFor="employeeId">ID Employé *</Label>
              <Input
                id="employeeId"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="ID de l'employé"
                required
              />
            </div>
          )}

          {/* Type de promotion */}
          <div className="space-y-2">
            <Label htmlFor="promotionType">Type de promotion *</Label>
            <Select value={promotionType} onValueChange={(v) => setPromotionType(v as PromotionType)}>
              <SelectTrigger id="promotionType">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROMOTION_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Nouveau poste */}
          {showJobTitleField && (
            <div className="space-y-2">
              <Label htmlFor="newJobTitle">Nouveau poste *</Label>
              <Input
                id="newJobTitle"
                value={newJobTitle}
                onChange={(e) => setNewJobTitle(e.target.value)}
                placeholder="Ex: Développeur Senior"
                required
              />
            </div>
          )}

          {/* Nouveau salaire */}
          {showSalaryField && (
            <div className="space-y-2">
              <Label htmlFor="newSalary">Nouveau salaire *</Label>
              <div className="flex gap-2">
                <Input
                  id="newSalary"
                  type="number"
                  step="0.01"
                  value={newSalaryValue}
                  onChange={(e) => setNewSalaryValue(e.target.value)}
                  placeholder="Montant"
                  required
                  className="flex-1"
                />
                <Select
                  value={newSalaryCurrency}
                  onValueChange={setNewSalaryCurrency}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="EUR">EUR</SelectItem>
                    <SelectItem value="USD">USD</SelectItem>
                    <SelectItem value="GBP">GBP</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Nouveau statut */}
          {showStatutField && (
            <div className="space-y-2">
              <Label htmlFor="newStatut">Nouveau statut *</Label>
              <Select value={newStatut} onValueChange={setNewStatut}>
                <SelectTrigger id="newStatut">
                  <SelectValue placeholder="Sélectionner un statut" />
                </SelectTrigger>
                <SelectContent>
                  {STATUT_OPTIONS.map((statut) => (
                    <SelectItem key={statut} value={statut}>
                      {statut}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Nouvelle classification */}
          {showClassificationField && (
            <div className="space-y-2">
              <Label>Nouvelle classification *</Label>
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-1">
                  <Label htmlFor="coefficient" className="text-xs text-muted-foreground">
                    Coefficient
                  </Label>
                  <Input
                    id="coefficient"
                    type="number"
                    value={newCoefficient}
                    onChange={(e) => setNewCoefficient(e.target.value)}
                    placeholder="Ex: 240"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="classeEmploi" className="text-xs text-muted-foreground">
                    Classe d'emploi
                  </Label>
                  <Input
                    id="classeEmploi"
                    type="number"
                    value={newClasseEmploi}
                    onChange={(e) => setNewClasseEmploi(e.target.value)}
                    placeholder="Ex: 6"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="groupeEmploi" className="text-xs text-muted-foreground">
                    Groupe d'emploi
                  </Label>
                  <Input
                    id="groupeEmploi"
                    value={newGroupeEmploi}
                    onChange={(e) => setNewGroupeEmploi(e.target.value)}
                    placeholder="Ex: C"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Date d'effet */}
          <div className="space-y-2">
            <Label htmlFor="effectiveDate">Date d'effet *</Label>
            <Input
              id="effectiveDate"
              type="date"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
              required
            />
          </div>

          {/* Raison */}
          <div className="space-y-2">
            <Label htmlFor="reason">Raison</Label>
            <Textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Raison de la promotion"
              rows={3}
            />
          </div>

          {/* Justification */}
          <div className="space-y-2">
            <Label htmlFor="justification">Justification</Label>
            <Textarea
              id="justification"
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              placeholder="Justification de la promotion"
              rows={3}
            />
          </div>

          {/* Accès RH */}
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="grantRhAccess"
                checked={grantRhAccess}
                onCheckedChange={(checked) => setGrantRhAccess(checked === true)}
              />
              <Label htmlFor="grantRhAccess" className="cursor-pointer">
                Accorder un accès RH
              </Label>
            </div>
            {grantRhAccess && (
              <div className="ml-6 space-y-2">
                <Label htmlFor="newRhAccess">Rôle d'accès RH *</Label>
                <Select
                  value={newRhAccess || ""}
                  onValueChange={(v) => setNewRhAccess(v as RhAccessRole)}
                >
                  <SelectTrigger id="newRhAccess">
                    <SelectValue placeholder="Sélectionner un rôle" />
                  </SelectTrigger>
                  <SelectContent>
                    {RH_ACCESS_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {promotion ? "Modifier" : "Créer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
