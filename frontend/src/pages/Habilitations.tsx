import HabilitationsTab from "@/pages/formation/tabs/HabilitationsTab";

/**
 * Écran minimal : le ticket demande uniquement le composant onglet ;
 * cette page sert de cible de route /habilitations (sidebar).
 */
export default function HabilitationsPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Habilitations</h1>
        <p className="text-sm text-muted-foreground">
          Référentiel, habilitations collaborateurs et certificats.
        </p>
      </div>
      <HabilitationsTab />
    </div>
  );
}
