// Signalements DSN d'arrêt et de reprise anticipée : la liste à déposer, avec la
// date limite, et la génération du fichier à déposer sur net-entreprises.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileWarning } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { useToast } from "@/hooks/use-toast";
import { genererSignalement, listerSignalements, type SignalementLigne } from "@/api/exports";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { echeance, libelleFait, libelleSignalement } from "./signalementsArret";

function detailErreur(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return detail || "Le signalement n'a pas été généré : réessayez.";
}

export function SignalementsArretCard() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const { toast } = useToast();
  const qc = useQueryClient();
  const cle = ["dsn-signalements", companyId];

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: cle,
    queryFn: listerSignalements,
    enabled: !!companyId,
  });

  const generation = useMutation({
    mutationFn: (args: { ligne: SignalementLigne; essai: boolean }) =>
      genererSignalement({
        employee_id: args.ligne.employee_id,
        nature: args.ligne.nature,
        debut: args.ligne.debut,
        essai: args.essai,
      }),
    onSuccess: (resultat) => {
      window.open(resultat.download_url, "_blank", "noopener");
      toast({ title: "Signalement généré", description: resultat.message });
      qc.invalidateQueries({ queryKey: cle });
    },
    onError: (err) => {
      toast({ title: "Signalement non généré", description: detailErreur(err), variant: "destructive" });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileWarning className="h-5 w-5" />
          Signalements DSN
        </CardTitle>
        <CardDescription>
          À déposer sur net-entreprises : chaque nouvel arrêt dans les 5 jours (avec la DSN du mois en
          cas de subrogation) ; chaque fin de contrat dans les 5 jours ouvrés, une fois le bulletin de
          sortie calculé. Une prolongation ne se signale pas : elle part dans la DSN mensuelle.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {isError && (
          <div className="flex items-center gap-3 text-sm">
            <span>La liste des signalements n'a pas pu être lue : réessayez.</span>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Réessayer
            </Button>
          </div>
        )}
        {data && data.a_faire.length === 0 && (
          <p className="text-sm text-muted-foreground">Rien à signaler.</p>
        )}
        {data?.a_faire.map((ligne) => {
          const limite = echeance(ligne);
          // Une fin de contrat attend sa sortie et son bulletin : rien à générer avant.
          const enAttente = ligne.nature === "07" && !!ligne.a_verifier;
          return (
            <div
              key={`${ligne.employee_id}-${ligne.nature}-${ligne.debut}`}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3"
            >
              <div className="space-y-0.5">
                <p className="font-medium">{ligne.salarie}</p>
                <p className="text-sm">{libelleSignalement(ligne)}</p>
                <p className={limite.urgent ? "text-sm font-medium text-destructive" : "text-sm text-muted-foreground"}>
                  {limite.texte}
                </p>
                {ligne.a_verifier && (
                  <p className="text-sm text-amber-700 dark:text-amber-400">À vérifier : {ligne.a_verifier}</p>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={generation.isPending || enAttente}
                  onClick={() => generation.mutate({ ligne, essai: true })}
                >
                  Fichier d'essai
                </Button>
                <Button
                  size="sm"
                  disabled={generation.isPending || enAttente}
                  onClick={() => generation.mutate({ ligne, essai: false })}
                >
                  Fichier réel
                </Button>
              </div>
            </div>
          );
        })}
        {data && data.faits.length > 0 && (
          <div className="space-y-1 pt-2">
            <p className="text-sm font-medium">Derniers signalements générés</p>
            {data.faits.slice(0, 5).map((fait) => (
              <p key={`${fait.employee_id}-${fait.nature}-${fait.debut}-${fait.genere_le}`} className="text-sm text-muted-foreground">
                {fait.salarie} · {libelleFait(fait)}
              </p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
