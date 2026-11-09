// Signalements DSN d'arrêt et de reprise anticipée : la liste à déposer, avec la
// date limite, et la génération du fichier à déposer sur net-entreprises.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, FileWarning } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { useToast } from "@/hooks/use-toast";
import { genererSignalement, listerSignalements, type SignalementLigne } from "@/api/exports";
import { updateAbsenceDateAccident } from "@/api/absences";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { echeance, libelleFait, libelleSignalement } from "./signalementsArret";
import { SignalementApercuDialog } from "./SignalementApercuDialog";

function detailErreur(err: unknown, repli = "Le signalement n'a pas été généré : réessayez."): string {
  const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return detail || repli;
}

const MOTIFS_ACCIDENT = new Set(["04", "05", "06"]);

export function SignalementsArretCard() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const { toast } = useToast();
  const qc = useQueryClient();
  const cle = ["dsn-signalements", companyId];
  // Aperçu en lecture seule : la ligne dont on montre le fichier, sinon null.
  const [apercu, setApercu] = useState<SignalementLigne | null>(null);

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

  const saisieAccident = useMutation({
    mutationFn: (args: { absenceId: string; date: string | null }) =>
      updateAbsenceDateAccident(args.absenceId, args.date),
    onSuccess: () => {
      toast({ title: "Date de l'accident enregistrée" });
      qc.invalidateQueries({ queryKey: cle });
    },
    onError: (err) => {
      toast({
        title: "Date non enregistrée",
        description: detailErreur(err, "La date de l'accident n'a pas été enregistrée : réessayez."),
        variant: "destructive",
      });
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
                {ligne.avis && (
                  <p className="text-sm text-amber-700 dark:text-amber-400">Attention : {ligne.avis}</p>
                )}
                {MOTIFS_ACCIDENT.has(ligne.motif) && ligne.absence_id && (
                  <label className="flex flex-wrap items-center gap-2 text-sm">
                    <span>Date de l&apos;accident ou de la première constatation</span>
                    <Input
                      type="date"
                      className="h-8 w-[160px]"
                      defaultValue={ligne.date_accident ?? ""}
                      disabled={saisieAccident.isPending}
                      onBlur={(e) => {
                        const valeur = e.target.value || null;
                        if (valeur !== (ligne.date_accident ?? null) && ligne.absence_id) {
                          saisieAccident.mutate({ absenceId: ligne.absence_id, date: valeur });
                        }
                      }}
                    />
                  </label>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={enAttente}
                  onClick={() => setApercu(ligne)}
                >
                  <Eye className="mr-1 h-4 w-4" />
                  Aperçu
                </Button>
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
      <SignalementApercuDialog ligne={apercu} onClose={() => setApercu(null)} />
    </Card>
  );
}
