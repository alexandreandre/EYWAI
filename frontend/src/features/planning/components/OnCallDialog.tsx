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
import type { PlanningEmployee } from "@/api/planning";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employees: PlanningEmployee[];
  employeeId: string;
  onEmployeeIdChange: (id: string) => void;
  date: string;
  onDateChange: (date: string) => void;
  start: string;
  onStartChange: (v: string) => void;
  end: string;
  onEndChange: (v: string) => void;
  onSubmit: () => void;
  isPending: boolean;
}

export function OnCallDialog(props: Props) {
  const {
    open,
    onOpenChange,
    employees,
    employeeId,
    onEmployeeIdChange,
    date,
    onDateChange,
    start,
    onStartChange,
    end,
    onEndChange,
    onSubmit,
    isPending,
  } = props;

  return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouvelle astreinte</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="oncall-employee">Employé</Label>
              <Select
                value={employeeId || undefined}
                onValueChange={onEmployeeIdChange}
              >
                <SelectTrigger id="oncall-employee">
                  <SelectValue placeholder="Choisir un salarié" />
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
              <Label htmlFor="oncall-date">Date</Label>
              <Input
                id="oncall-date"
                type="date"
                value={date}
                onChange={(e) => onDateChange(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="oncall-start">Heure début</Label>
                <Input
                  id="oncall-start"
                  type="time"
                  step={60}
                  value={start}
                  onChange={(e) => onStartChange(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="oncall-end">Heure fin</Label>
                <Input
                  id="oncall-end"
                  type="time"
                  step={60}
                  value={end}
                  onChange={(e) => onEndChange(e.target.value)}
                />
              </div>
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
