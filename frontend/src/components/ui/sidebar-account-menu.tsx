import { useEffect, useState } from "react";
import { KeyRound, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { ChangePasswordModal } from "@/components/ChangePasswordModal";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

type SidebarAccountMenuProps = {
  collapsed?: boolean;
  className?: string;
};

export function SidebarAccountMenu({ collapsed = false, className }: SidebarAccountMenuProps) {
  const { logout, user } = useAuth();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const passwordChangeRequired = Boolean(user?.must_change_password);

  useEffect(() => {
    if (passwordChangeRequired) setShowChangePassword(true);
  }, [passwordChangeRequired]);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "h-8 w-8 shrink-0 text-muted-foreground hover:bg-primary/10 hover:text-primary",
              className,
            )}
            aria-label="Réglages du compte"
          >
            <Settings className="h-4 w-4 shrink-0" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side={collapsed ? "right" : "top"} align="end" className="w-56">
          <DropdownMenuItem
            onSelect={() => {
              setShowChangePassword(true);
            }}
          >
            <KeyRound className="mr-2 h-4 w-4" />
            Modifier mon mot de passe
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onSelect={() => {
              setShowLogoutConfirm(true);
            }}
          >
            <LogOut className="mr-2 h-4 w-4" />
            Déconnexion
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ChangePasswordModal
        open={showChangePassword}
        onOpenChange={setShowChangePassword}
        required={passwordChangeRequired}
      />

      <AlertDialog open={showLogoutConfirm} onOpenChange={setShowLogoutConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Se déconnecter ?</AlertDialogTitle>
            <AlertDialogDescription>
              Êtes-vous sûr de vouloir mettre fin à votre session ?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                logout();
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Se déconnecter
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
