import ObjectivesTab from "@/pages/formation/tabs/ObjectivesTab";

export default function ObjectivesPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Objectifs & KPI</h1>
        <p className="text-sm text-muted-foreground">
          Définition, suivi et évaluation des objectifs individuels et d&apos;équipe.
        </p>
      </div>
      <ObjectivesTab />
    </div>
  );
}
