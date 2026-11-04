// Aperçu d'un signalement DSN avant tout envoi : le fichier en clair, bloc par
// bloc, et son texte brut. Rien n'est enregistré ni déposé.
import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { apercuSignalement, type SignalementApercu, type SignalementLigne } from "@/api/exports";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { libelleSignalement } from "./signalementsArret";
import {
  detailErreurApercu,
  grouperParPartie,
  masquerNir,
  masquerNirDansBrut,
  PHRASE_BRUT,
  PHRASE_TETE,
  RUBRIQUE_NIR,
} from "./signalementApercu";

export type OngletApercu = "clair" | "brut";

function EnClair({ apercu }: { apercu: SignalementApercu }) {
  const parties = grouperParPartie(apercu.blocs);
  if (parties.length === 0) {
    return <p className="text-sm text-muted-foreground">Le fichier ne porte aucun bloc lisible.</p>;
  }
  return (
    <div className="space-y-5">
      {parties.map((partie, i) => (
        <section key={`${partie.partie}-${i}`} className="space-y-3">
          <h3 className="text-base font-semibold">{partie.libelle}</h3>
          {partie.blocs.map((bloc, j) => (
            <div key={`${bloc.code}-${j}`} className="rounded-md border">
              <p className="border-b bg-muted/50 px-3 py-2 text-sm font-medium">
                <span className="font-mono text-xs text-muted-foreground">{bloc.code}</span> · {bloc.libelle}
              </p>
              <Table className="text-sm">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-40">Rubrique</TableHead>
                    <TableHead>Libellé</TableHead>
                    <TableHead>Valeur</TableHead>
                    <TableHead>Signifie</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bloc.rubriques.map((r, k) => (
                    <TableRow key={`${r.code}-${k}`}>
                      <TableCell className="py-1.5 font-mono text-xs">{r.code}</TableCell>
                      <TableCell className="py-1.5">{r.libelle}</TableCell>
                      <TableCell className="py-1.5 font-mono text-xs break-all">
                        {r.code === RUBRIQUE_NIR ? masquerNir(r.valeur) : r.valeur}
                      </TableCell>
                      <TableCell className="py-1.5">{r.traduction ?? ""}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

/** Le corps de la fenêtre, sans état : testable sans navigateur. */
export function ApercuCorps({
  apercu,
  chargement,
  erreur,
  onReessayer,
  onValider,
  onglet = "clair",
}: {
  apercu: SignalementApercu | undefined;
  chargement: boolean;
  erreur: unknown;
  onReessayer: () => void;
  onValider: () => void;
  onglet?: OngletApercu;
}) {
  return (
    <>
      <div
        role="note"
        className="flex items-start gap-2 rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-100"
      >
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{PHRASE_TETE}</p>
      </div>

      {chargement && <p className="text-sm text-muted-foreground">Préparation de l'aperçu…</p>}

      {!chargement && !!erreur && (
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-destructive/40 p-3 text-sm">
          <span className="text-destructive">{detailErreurApercu(erreur)}</span>
          <Button size="sm" variant="outline" onClick={onReessayer}>
            Réessayer
          </Button>
        </div>
      )}

      {!chargement && !erreur && apercu && (
        <Tabs defaultValue={onglet} className="w-full">
          <TabsList>
            <TabsTrigger value="clair">En clair</TabsTrigger>
            <TabsTrigger value="brut">Fichier brut</TabsTrigger>
          </TabsList>
          <TabsContent value="clair" className="mt-3 max-h-[60vh] overflow-auto pr-1">
            <p className="mb-3 text-sm text-muted-foreground">
              {apercu.libelle_nature} ({apercu.essai ? "fichier d'essai" : "fichier réel"}).
            </p>
            <EnClair apercu={apercu} />
          </TabsContent>
          <TabsContent value="brut" className="mt-3 space-y-2">
            <p className="text-sm text-muted-foreground">{PHRASE_BRUT}</p>
            <pre
              data-testid="apercu-brut"
              className="max-h-[55vh] overflow-auto whitespace-pre rounded-md border bg-muted/40 p-3 font-mono text-xs"
            >
              {masquerNirDansBrut(apercu.brut)}
            </pre>
          </TabsContent>
        </Tabs>
      )}

      <DialogFooter>
        <Button onClick={onValider}>Valider le format</Button>
      </DialogFooter>
    </>
  );
}

export function SignalementApercuDialog({
  ligne,
  onClose,
}: {
  ligne: SignalementLigne | null;
  onClose: () => void;
}) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const ouvert = !!ligne;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dsn-signalement-apercu", companyId, ligne?.employee_id, ligne?.nature, ligne?.debut],
    queryFn: () =>
      apercuSignalement({
        employee_id: ligne!.employee_id,
        nature: ligne!.nature,
        debut: ligne!.debut,
      }),
    enabled: ouvert && !!companyId,
    staleTime: 0,
    retry: false,
  });

  return (
    <Dialog open={ouvert} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto [&>*]:min-w-0">
        <DialogHeader>
          <DialogTitle>Aperçu du signalement</DialogTitle>
          <DialogDescription>
            {ligne ? [ligne.salarie, libelleSignalement(ligne)].filter(Boolean).join(" · ") : ""}
          </DialogDescription>
        </DialogHeader>
        <ApercuCorps
          apercu={data}
          chargement={isLoading}
          erreur={error}
          onReessayer={() => refetch()}
          onValider={onClose}
        />
      </DialogContent>
    </Dialog>
  );
}
