import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDateFR } from "@/lib/careerFormat";

type SalaryReviewApplyDialogsProps = {
  applyOpen: boolean;
  onApplyOpenChange: (open: boolean) => void;
  applySuccessContext: { nb_appliques: number; appliedIds: string[] } | null;
  selectedCount: number;
  applyMotif: string;
  onApplyMotifChange: (value: string) => void;
  effectiveDate: string;
  applySubmitting: boolean;
  onConfirmApply: () => void;
  onCloseApplyFlow: () => void;
  onOpenLotFromSuccess: () => void;
  lotGenOpen: boolean;
  onLotGenOpenChange: (open: boolean) => void;
  lotEmployeeCount: number;
  lotEffectiveDateInput: string;
  onLotEffectiveDateChange: (value: string) => void;
  lotMotifInput: string;
  onLotMotifChange: (value: string) => void;
  lotSubmitting: boolean;
  onLotGenerate: () => void;
};

export function SalaryReviewApplyDialogs({
  applyOpen,
  onApplyOpenChange,
  applySuccessContext,
  selectedCount,
  applyMotif,
  onApplyMotifChange,
  effectiveDate,
  applySubmitting,
  onConfirmApply,
  onCloseApplyFlow,
  onOpenLotFromSuccess,
  lotGenOpen,
  onLotGenOpenChange,
  lotEmployeeCount,
  lotEffectiveDateInput,
  onLotEffectiveDateChange,
  lotMotifInput,
  onLotMotifChange,
  lotSubmitting,
  onLotGenerate,
}: SalaryReviewApplyDialogsProps) {
  return (
    <>
      <Dialog open={applyOpen} onOpenChange={onApplyOpenChange}>
        <DialogContent>
          {!applySuccessContext ? (
            <>
              <DialogHeader>
                <DialogTitle>Confirmer l&apos;application</DialogTitle>
                <DialogDescription>
                  Appliquer une augmentation à {selectedCount} salarié(s) sélectionné(s) ?
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 py-2">
                <Label htmlFor="motif-drawer">Motif (optionnel, commun)</Label>
                <Input
                  id="motif-drawer"
                  value={applyMotif}
                  onChange={(e) => onApplyMotifChange(e.target.value)}
                  placeholder="Ex. augmentation annuelle"
                />
                <p className="text-xs text-muted-foreground">
                  Date d&apos;effet : {formatDateFR(effectiveDate)}
                </p>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button variant="outline" onClick={() => onApplyOpenChange(false)}>
                  Annuler
                </Button>
                <Button
                  onClick={onConfirmApply}
                  disabled={applySubmitting || !selectedCount}
                >
                  {applySubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Confirmer
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Augmentations enregistrées</DialogTitle>
                <DialogDescription>
                  {applySuccessContext.nb_appliques} augmentation(s) ont été appliquée(s) avec
                  succès.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-end">
                <Button variant="outline" onClick={onCloseApplyFlow}>
                  Fermer
                </Button>
                {applySuccessContext.nb_appliques > 0 ? (
                  <Button type="button" onClick={onOpenLotFromSuccess}>
                    Générer les avenants salaire
                  </Button>
                ) : null}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={lotGenOpen} onOpenChange={onLotGenOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Générer les avenants en lot</DialogTitle>
            <DialogDescription>
              Générer un avenant salaire pour {lotEmployeeCount} salarié(s).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="lot-date-drawer">Date d&apos;effet</Label>
              <Input
                id="lot-date-drawer"
                type="date"
                value={lotEffectiveDateInput}
                onChange={(e) => onLotEffectiveDateChange(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lot-motif-drawer">Motif (optionnel)</Label>
              <Input
                id="lot-motif-drawer"
                value={lotMotifInput}
                onChange={(e) => onLotMotifChange(e.target.value)}
                placeholder="Commun à tous les avenants"
              />
            </div>
            <p className="rounded-md border border-muted bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              Les avenants seront disponibles dans Documents RH pour signature.
            </p>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => onLotGenOpenChange(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              onClick={onLotGenerate}
              disabled={
                lotSubmitting || !lotEmployeeCount || !lotEffectiveDateInput.trim()
              }
            >
              {lotSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
