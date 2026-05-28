import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { PlanningEmployee, ShiftType } from "@/api/planning";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employees: PlanningEmployee[];
  shiftTypes: ShiftType[];
  originalId: string;
  onOriginalIdChange: (id: string) => void;
  replacingId: string;
  onReplacingIdChange: (id: string) => void;
  date: string;
  onDateChange: (date: string) => void;
  start: string;
  onStartChange: (v: string) => void;
  end: string;
  onEndChange: (v: string) => void;
  reason: string;
  onReasonChange: (v: string) => void;
  shiftTypeId: string;
  onShiftTypeIdChange: (id: string) => void;
  onSubmit: () => void;
  isPending: boolean;
}

export function ReplacementDialog(props: Props) {
  const {
    open,
    onOpenChange,
    employees,
    shiftTypes,
    originalId,
    onOriginalIdChange,
    replacingId,
    onReplacingIdChange,
    date,
    onDateChange,
    start,
    onStartChange,
    end,
    onEndChange,
    reason,
    onReasonChange,
    shiftTypeId,
    onShiftTypeIdChange,
    onSubmit,
    isPending,
  } = props;

  return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Planifier un remplacement</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="rep-original">Salarié remplacé</Label>
              <Select value={originalId || undefined} onValueChange={onOriginalIdChange}>
                <SelectTrigger id="rep-original">
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {(employees ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.last_name} {e.first_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-replacing">Salarié remplaçant</Label>
              <Select value={replacingId || undefined} onValueChange={onReplacingIdChange}>
                <SelectTrigger id="rep-replacing">
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {(employees ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.last_name} {e.first_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-type">Type de shift</Label>
              <Select value={shiftTypeId || undefined} onValueChange={onShiftTypeIdChange}>
                <SelectTrigger id="rep-type">
                  <SelectValue placeholder="Choisir un type" />
                </SelectTrigger>
                <SelectContent>
                  {(shiftTypes ?? []).map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-date">Date</Label>
              <Input
                id="rep-date"
                type="date"
                value={date}
                onChange={(e) => onDateChange(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="rep-start">Heure début</Label>
                <Input
                  id="rep-start"
                  type="time"
                  step={60}
                  value={start}
                  onChange={(e) => onStartChange(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rep-end">Heure fin</Label>
                <Input
                  id="rep-end"
                  type="time"
                  step={60}
                  value={end}
                  onChange={(e) => onEndChange(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-reason">Motif (optionnel)</Label>
              <Input
                id="rep-reason"
                value={reason}
                onChange={(e) => onReasonChange(e.target.value)}
                placeholder="Ex. absence, formation…"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Annuler
            </Button>
            <Button
              type="button"
              onClick={onSubmit}
              disabled={isPending}
            >
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

  );
}
