import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { toggleMyBadge, type BadgeuseStatusToday } from "@/api/badgeuse";
import { Button } from "@/components/ui/button";
import { resolveSelfPunchState } from "@/lib/badgeuseSelfPunch";

type Props = {
  data: BadgeuseStatusToday;
};

/**
 * Bouton de badgeage du salarié depuis son propre téléphone.
 *
 * L'action est une bascule : le serveur décide seul s'il s'agit d'une entrée
 * ou d'une sortie. `next_action` n'est qu'un libellé d'affichage.
 */
export function BadgeuseSelfPunchButton({ data }: Props) {
  const queryClient = useQueryClient();
  const { isEntry, label, lastPunchLabel } = resolveSelfPunchState(
    data.next_action,
    data.events
  );

  const mutation = useMutation({
    mutationFn: toggleMyBadge,
    onSuccess: (result) => {
      toast.success(result.status_label ?? "Pointage enregistré");
      void queryClient.invalidateQueries({ queryKey: ["badgeuse"] });
      void queryClient.invalidateQueries({ queryKey: ["employee-dashboard"] });
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Pointage impossible";
      toast.error(String(message));
    },
  });

  return (
    <div className="space-y-2">
      <Button
        type="button"
        size="lg"
        className="h-20 w-full text-lg font-semibold"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? (
          <Loader2 className="mr-2 h-6 w-6 animate-spin" />
        ) : isEntry ? (
          <LogIn className="mr-2 h-6 w-6" />
        ) : (
          <LogOut className="mr-2 h-6 w-6" />
        )}
        {label}
      </Button>
      {lastPunchLabel && (
        <p className="text-center text-sm text-muted-foreground">
          Dernier pointage à {lastPunchLabel}
        </p>
      )}
    </div>
  );
}
