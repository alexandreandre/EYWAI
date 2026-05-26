import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { scanBadgeQr } from "@/api/badgeuse";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

type Props = {
  companyId: string;
  onSuccess?: () => void;
  trigger?: React.ReactNode;
};

export function ManualPunchDialog({ companyId, onSuccess, trigger }: Props) {
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState("");

  const mutation = useMutation({
    mutationFn: () => scanBadgeQr(companyId, { username: username.trim() }),
    onSuccess: (result) => {
      toast.success(`${result.status_label} — ${result.employee_name}`);
      setOpen(false);
      setUsername("");
      onSuccess?.();
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Pointage impossible";
      toast.error(String(message));
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" type="button">
            Saisie manuelle
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Badgeage manuel</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Saisissez l&apos;identifiant de connexion de l&apos;employé (carte oubliée ou QR illisible).
        </p>
        <div className="space-y-2">
          <Label htmlFor="badge-username">Identifiant employé</Label>
          <Input
            id="badge-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="nom.utilisateur"
            autoComplete="off"
          />
        </div>
        <Button
          className="w-full"
          disabled={!username.trim() || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "Enregistrement…" : "Badger"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
