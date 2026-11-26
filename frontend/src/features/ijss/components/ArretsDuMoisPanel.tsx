/**
 * Écran « Arrêts & IJ » (retour d'Elsa du 16/11) : un arrêt par ligne.
 *
 * Le parcours : enregistrer l'arrêt (subrogation cochée ou non), joindre si on
 * veut les preuves (virement CPAM, IJ transmises par le salarié, décompte),
 * dire « IJ reçues » (un clic sur le montant estimé, ou un autre montant) ;
 * Martine verse alors le maintien.
 */
import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Loader2, Paperclip, Trash2 } from 'lucide-react';
import {
  ajouterJustificatifArret,
  enregistrerIjRecues,
  LIBELLES_JUSTIFICATIF_ARRET,
  listerArretsDuMois,
  supprimerJustificatifArret,
  type ArretDuMois,
  type TypeJustificatifArret,
} from '@/api/ijssTracking';
import * as absencesApi from '@/api/absences';
import { listerSignalements } from '@/api/exports';
import { AbsenceSignalementBadge } from '@/components/absences/AbsenceSignalementBadge';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ControleIndisponible } from '@/features/payroll/components/ControleIndisponible';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { useToast } from '@/hooks/use-toast';
import { libelleTypeArret } from '@/lib/employeeAbsencesUtils';
import { getUserErrorMessage } from '@/lib/errorMessages';

const LIBELLES_NATURE: Record<string, string> = {
  arret_maladie: 'Arrêt maladie',
  arret_at: 'Accident du travail',
  arret_maladie_pro: 'Maladie professionnelle',
  arret_maternite: 'Congé maternité',
  arret_paternite: 'Congé paternité',
};

function eur(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

function jourFr(iso: string | null): string {
  if (!iso) return '—';
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
}

export function libelleArret(arret: Pick<ArretDuMois, 'type' | 'arret_type'>): string {
  const nature = LIBELLES_NATURE[arret.type] ?? arret.type;
  if (arret.arret_type && arret.type === 'arret_maladie' && arret.arret_type !== 'maladie_simple') {
    return libelleTypeArret(arret.arret_type);
  }
  if (arret.arret_type === 'conge_supplementaire_naissance') return libelleTypeArret(arret.arret_type);
  return nature;
}

/** Ce que la colonne « Maintien » dit, en clair, sans état silencieux. */
const NOMS_DES_MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

/** « de septembre », « d'octobre » : le bulletin d'un mois, élision comprise. */
function duMois(month: number): string {
  const nom = NOMS_DES_MOIS[(((month - 1) % 12) + 12) % 12];
  return /^[aeiouéâ]/.test(nom) ? `d'${nom}` : `de ${nom}`;
}

export function phraseMaintien(
  arret: ArretDuMois,
  mois?: { year: number; month: number },
): { texte: string; ton: 'ok' | 'attente' | 'neutre' } {
  const m = arret.maintien;
  switch (m.etat) {
    case 'bulletin_a_faire':
      return { texte: 'Bulletin du mois pas encore fait', ton: 'neutre' };
    case 'bulletin_a_recalculer':
      // Arrêt enregistré après le calcul du bulletin (MAJI, 17/11 : « 0 jour indemnisé »).
      return {
        texte: "Bulletin calculé avant l'arrêt : régénérez-le pour qu'il compte l'arrêt",
        ton: 'attente',
      };
    // Retour d'Elsa du 26/11 : un arrêt arrivé après la validation du bulletin de
    // son mois passe sur le bulletin suivant, à ses dates, comme chez Quadra.
    case 'reporte_sur_le_bulletin_suivant':
      return {
        texte: mois ? `Reporté sur le bulletin ${duMois(mois.month + 1)}` : 'Reporté sur le bulletin suivant',
        ton: 'ok',
      };
    case 'report_au_prochain_calcul':
      return {
        texte:
          `${mois ? `Bulletin ${duMois(mois.month)}` : 'Bulletin du mois'} validé avant l'arrêt : ` +
          `${mois ? `le bulletin ${duMois(mois.month + 1)}` : 'le bulletin suivant'} le reprendra à son calcul`,
        ton: 'attente',
      };
    case 'report_a_recalculer':
      return {
        texte:
          `${mois ? `Bulletin ${duMois(mois.month)}` : 'Bulletin du mois'} validé avant l'arrêt : ` +
          `recalculez ${mois ? `le bulletin ${duMois(mois.month + 1)}` : 'le bulletin suivant'} pour qu'il le reprenne`,
        ton: 'attente',
      };
    case 'bulletin_remis_avant_l_arret': {
      // Le bulletin suivant était déjà validé lui aussi : Martine ne remonte pas
      // plus loin, l'arrêt se porte à la main.
      const deux = mois
        ? `Bulletins ${duMois(mois.month)} et ${duMois(mois.month + 1)}`
        : 'Bulletin du mois et bulletin suivant';
      const apres = mois ? `le bulletin ${duMois(mois.month + 2)}` : 'le prochain bulletin';
      return {
        texte:
          `${deux} validés avant la saisie de l'arrêt : Martine ne le reporte pas seule. ` +
          `À porter sur ${apres} (onglet « Corriger »)`,
        ton: 'attente',
      };
    }
    case 'en_attente_des_ij':
      return {
        texte: `En attente des IJ : ${eur(m.montant_en_attente)} retenus`,
        ton: 'attente',
      };
    case 'verse':
      return { texte: `Versé : ${eur(m.montant_verse)}`, ton: 'ok' };
    default:
      return {
        texte: m.motif
          ? `Pas de maintien (${m.motif})`
          : 'Pas de maintien sur le bulletin de ce mois (ouvrez le bulletin pour le détail)',
        ton: 'neutre',
      };
  }
}

interface Props {
  year: number;
  month: number;
  libelleMois: string;
}

export function ArretsDuMoisPanel({ year, month, libelleMois }: Props) {
  const companyId = useActiveCompanyId();
  const [ouvert, setOuvert] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ['arrets-du-mois', companyId, year, month],
    queryFn: () => listerArretsDuMois(year, month),
    enabled: Boolean(companyId),
  });
  const { data: signalements } = useQuery({
    queryKey: ['dsn-signalements'],
    queryFn: listerSignalements,
    staleTime: 60_000,
  });

  const arrets = query.data?.arrets ?? [];
  const selection = arrets.find((a) => a.absence_id === ouvert) ?? null;
  const cloture = Boolean(query.data?.periode_cloturee);
  const { toast } = useToast();
  const queryClient = useQueryClient();
  // « IJ reçues » en un clic (retour d'Elsa du 16/11 : « la RH coche ok,
  // reçu ») : le montant estimé par Martine est retenu ; un autre montant se
  // saisit dans la fiche de l'arrêt.
  const recuesMut = useMutation({
    mutationFn: (a: ArretDuMois) =>
      enregistrerIjRecues(a.absence_id, { year, month, montant: a.ij_estimees ?? 0 }),
    onSuccess: (res, a) => {
      toast({ title: `IJ reçues : ${a.employee_name}`, description: res.message });
      void queryClient.invalidateQueries({ queryKey: ['arrets-du-mois', companyId, year, month] });
      void queryClient.invalidateQueries({ queryKey: ['ijss-dashboard', companyId, year, month] });
    },
    onError: (e: unknown) =>
      toast({ variant: 'destructive', title: 'IJ non enregistrées', description: getUserErrorMessage(e) }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Arrêts de {libelleMois}</CardTitle>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <TableSkeleton rows={4} columns={6} />
        ) : query.isError ? (
          <ControleIndisponible
            titre="Les arrêts de ce mois n'ont pas pu être lus"
            description={getUserErrorMessage(query.error)}
            onRetry={() => void query.refetch()}
            isRetrying={query.isFetching}
          />
        ) : arrets.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucun arrêt ce mois-ci. Un nouvel arrêt s&apos;enregistre avec le bouton « Enregistrer un arrêt ».
          </p>
        ) : (
          <div className="w-full overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Arrêt</TableHead>
                  <TableHead>Subrogation</TableHead>
                  <TableHead className="text-right">IJ du mois</TableHead>
                  <TableHead>Maintien</TableHead>
                  <TableHead>Pièces</TableHead>
                  <TableHead>DSN</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {arrets.map((a) => {
                  const maintien = phraseMaintien(a, { year, month });
                  return (
                    <TableRow
                      key={a.absence_id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setOuvert(a.absence_id)}
                      data-testid="ligne-arret"
                    >
                      <TableCell className="font-medium">{a.employee_name}</TableCell>
                      <TableCell>
                        <p>{libelleArret(a)}</p>
                        <p className="text-xs text-muted-foreground">
                          Du {jourFr(a.date_debut)} au {jourFr(a.date_fin)} · {a.jours_dans_le_mois} j ce mois
                        </p>
                      </TableCell>
                      <TableCell>
                        {a.subrogation_active ? (
                          <Badge variant="default">Oui</Badge>
                        ) : (
                          <Badge variant="outline">Non</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {a.ij_recues != null ? (
                          <span>
                            {eur(a.ij_recues)}
                            <span className="block text-xs text-muted-foreground">reçues</span>
                          </span>
                        ) : a.ij_estimees != null && a.ij_estimees > 0 && !cloture ? (
                          <span className="inline-flex flex-col items-end gap-1">
                            <span className="text-muted-foreground">{eur(a.ij_estimees)} estimées</span>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7"
                              data-testid="ij-recues-un-clic"
                              disabled={recuesMut.isPending}
                              onClick={(e) => {
                                e.stopPropagation();
                                recuesMut.mutate(a);
                              }}
                            >
                              {recuesMut.isPending && recuesMut.variables?.absence_id === a.absence_id && (
                                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                              )}
                              Reçues
                            </Button>
                          </span>
                        ) : (
                          <span className="text-muted-foreground">
                            {a.ij_estimees != null && a.ij_estimees > 0
                              ? `${eur(a.ij_estimees)} estimées`
                              : 'À saisir (ouvrir la ligne)'}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span
                          className={
                            maintien.ton === 'attente'
                              ? 'text-amber-700 font-medium'
                              : maintien.ton === 'ok'
                                ? 'text-success'
                                : 'text-muted-foreground'
                          }
                        >
                          {maintien.texte}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {a.justificatifs.length + (a.certificat_url ? 1 : 0) || '—'}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <AbsenceSignalementBadge
                          arret={{
                            employee_id: a.employee_id,
                            selected_days: [a.date_debut, a.date_fin].filter(Boolean) as string[],
                          }}
                          signalements={signalements}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      <FicheArret
        arret={selection}
        year={year}
        month={month}
        libelleMois={libelleMois}
        cloture={cloture}
        onClose={() => setOuvert(null)}
      />
    </Card>
  );
}

function FicheArret({
  arret,
  year,
  month,
  libelleMois,
  cloture,
  onClose,
}: {
  arret: ArretDuMois | null;
  year: number;
  month: number;
  libelleMois: string;
  cloture: boolean;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();
  const [montant, setMontant] = useState('');
  const [resultat, setResultat] = useState<string | null>(null);
  const [typePiece, setTypePiece] = useState<TypeJustificatifArret>('ij_salarie');
  const fichierRef = useRef<HTMLInputElement>(null);
  const [envoiPiece, setEnvoiPiece] = useState(false);

  const rafraichir = () => {
    void queryClient.invalidateQueries({ queryKey: ['arrets-du-mois', companyId, year, month] });
    void queryClient.invalidateQueries({ queryKey: ['ijss-dashboard', companyId, year, month] });
  };

  const ijMut = useMutation({
    mutationFn: (valeur: number) =>
      enregistrerIjRecues(arret!.absence_id, { year, month, montant: valeur }),
    onSuccess: (res) => {
      setResultat(res.message);
      setMontant('');
      toast({ title: 'IJ enregistrées', description: res.message });
      rafraichir();
    },
    onError: (e: unknown) =>
      toast({ variant: 'destructive', title: 'IJ non enregistrées', description: getUserErrorMessage(e) }),
  });

  const annulerMut = useMutation({
    mutationFn: () => absencesApi.updateAbsenceRequestStatus(arret!.absence_id, 'cancelled'),
    onSuccess: () => {
      toast({ title: 'Arrêt annulé', description: 'Les jours sont rendus au planning.' });
      rafraichir();
      onClose();
    },
    onError: (e: unknown) =>
      toast({ variant: 'destructive', title: "L'arrêt n'a pas été annulé", description: getUserErrorMessage(e) }),
  });

  const supprimerPieceMut = useMutation({
    mutationFn: (id: string) => supprimerJustificatifArret(id),
    onSuccess: rafraichir,
    onError: (e: unknown) =>
      toast({ variant: 'destructive', title: 'Pièce non retirée', description: getUserErrorMessage(e) }),
  });

  const envoyerPiece = async (fichier: File) => {
    if (!arret) return;
    setEnvoiPiece(true);
    try {
      const { path, signedURL } = await absencesApi.getUploadUrl(fichier.name);
      await absencesApi.uploadFile(signedURL, fichier);
      await ajouterJustificatifArret(arret.absence_id, {
        kind: typePiece,
        storage_path: path,
        filename: fichier.name,
      });
      toast({ title: 'Pièce jointe', description: fichier.name });
      rafraichir();
    } catch (e) {
      toast({ variant: 'destructive', title: 'Pièce non jointe', description: getUserErrorMessage(e) });
    } finally {
      setEnvoiPiece(false);
    }
  };

  const valeur = Number.parseFloat(montant.replace(/\s/g, '').replace(',', '.'));
  const montantValide = montant.trim() !== '' && Number.isFinite(valeur) && valeur >= 0;
  const maintien = arret ? phraseMaintien(arret, { year, month }) : null;

  return (
    <Sheet
      open={arret !== null}
      onOpenChange={(o) => {
        if (!o) {
          setResultat(null);
          setMontant('');
          onClose();
        }
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {arret && (
          <>
            <SheetHeader>
              <SheetTitle>{arret.employee_name}</SheetTitle>
              <SheetDescription>
                {libelleArret(arret)} du {jourFr(arret.date_debut)} au {jourFr(arret.date_fin)}
              </SheetDescription>
            </SheetHeader>

            <section className="mt-6 space-y-1 text-sm">
              <p>
                <span className="text-muted-foreground">Subrogation : </span>
                {arret.subrogation_active
                  ? 'oui, la CPAM verse les IJ à la société, qui maintient le salaire.'
                  : 'non, la CPAM verse les IJ au salarié.'}
              </p>
              <p>
                <span className="text-muted-foreground">Maintien en {libelleMois} : </span>
                {maintien?.texte}
              </p>
            </section>

            <section className="mt-6 space-y-3 rounded-md border p-4">
              <h3 className="font-medium">IJ reçues pour {libelleMois}</h3>
              <p className="text-sm text-muted-foreground">
                {arret.subrogation_active
                  ? 'Le montant brut des IJ versées par la CPAM à la société pour les jours de ce mois (virement ou décompte).'
                  : 'Le montant brut des IJ que le salarié a reçues de la CPAM pour les jours de ce mois (il vous transmet son relevé).'}
                {arret.ij_estimees != null && ` Martine les estime à ${eur(arret.ij_estimees)}.`}
              </p>
              {arret.ij_recues != null && (
                <p className="text-sm">
                  Déjà saisi : <strong>{eur(arret.ij_recues)}</strong>
                  {arret.ij_appliquees_le ? ', porté au bulletin.' : '.'}
                </p>
              )}
              {arret.ij_estimees != null && arret.ij_estimees > 0 && arret.ij_recues == null && !cloture && (
                <Button
                  className="w-full"
                  data-testid="ij-recues-estimees"
                  onClick={() => ijMut.mutate(arret.ij_estimees ?? 0)}
                  disabled={ijMut.isPending}
                >
                  {ijMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  IJ reçues : {eur(arret.ij_estimees)}
                </Button>
              )}
              <div className="flex items-end gap-2">
                <div className="grid flex-1 gap-1">
                  <Label htmlFor="montant-ij">
                    {arret.ij_estimees != null && arret.ij_estimees > 0 ? 'Autre montant brut (€)' : 'Montant brut (€)'}
                  </Label>
                  <Input
                    id="montant-ij"
                    inputMode="decimal"
                    placeholder="ex. 412,50"
                    value={montant}
                    onChange={(e) => setMontant(e.target.value)}
                    disabled={cloture}
                  />
                </div>
                <Button
                  onClick={() => ijMut.mutate(valeur)}
                  disabled={!montantValide || ijMut.isPending || cloture}
                >
                  {ijMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Enregistrer
                </Button>
              </div>
              {cloture && (
                <p className="text-sm text-amber-700">Le suivi de ce mois est clôturé : plus de saisie possible.</p>
              )}
              {resultat && <p className="text-sm text-success">{resultat}</p>}
            </section>

            <section className="mt-6 space-y-3">
              <h3 className="font-medium">Pièces (facultatives)</h3>
              <ul className="space-y-2 text-sm">
                {arret.certificat_url && (
                  <li className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <a href={arret.certificat_url} target="_blank" rel="noopener noreferrer" className="underline">
                      Arrêt de travail{arret.certificat_filename ? ` — ${arret.certificat_filename}` : ''}
                    </a>
                  </li>
                )}
                {arret.justificatifs.map((p) => (
                  <li key={p.id} className="flex items-center gap-2">
                    <Paperclip className="h-4 w-4 text-muted-foreground" />
                    {p.url ? (
                      <a href={p.url} target="_blank" rel="noopener noreferrer" className="underline">
                        {LIBELLES_JUSTIFICATIF_ARRET[p.kind]}
                        {p.filename ? ` — ${p.filename}` : ''}
                      </a>
                    ) : (
                      <span>
                        {LIBELLES_JUSTIFICATIF_ARRET[p.kind]}
                        {p.filename ? ` — ${p.filename}` : ''} (lien indisponible)
                      </span>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="ml-auto h-7 w-7"
                      title="Retirer cette pièce"
                      onClick={() => supprimerPieceMut.mutate(p.id)}
                      disabled={supprimerPieceMut.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
                {!arret.certificat_url && arret.justificatifs.length === 0 && (
                  <li className="text-muted-foreground">Aucune pièce jointe.</li>
                )}
              </ul>
              <div className="flex flex-wrap items-end gap-2">
                <div className="grid gap-1">
                  <Label>Type de pièce</Label>
                  <Select value={typePiece} onValueChange={(v) => setTypePiece(v as TypeJustificatifArret)}>
                    <SelectTrigger className="w-[260px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(LIBELLES_JUSTIFICATIF_ARRET) as TypeJustificatifArret[]).map((k) => (
                        <SelectItem key={k} value={k}>
                          {LIBELLES_JUSTIFICATIF_ARRET[k]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button variant="outline" onClick={() => fichierRef.current?.click()} disabled={envoiPiece}>
                  {envoiPiece && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Joindre un fichier
                </Button>
                <input
                  ref={fichierRef}
                  type="file"
                  accept="image/*,application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void envoyerPiece(f);
                    e.target.value = '';
                  }}
                />
              </div>
            </section>

            <section className="mt-8 border-t pt-4">
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="ghost" className="text-muted-foreground">
                    Annuler cet arrêt
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Annuler cet arrêt ?</AlertDialogTitle>
                    <AlertDialogDescription>
                      L&apos;arrêt est annulé et ses jours rendus au planning. Les bulletins déjà faits ne
                      changent pas tant qu&apos;ils ne sont pas recalculés.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Retour</AlertDialogCancel>
                    <AlertDialogAction onClick={() => annulerMut.mutate()}>Annuler l&apos;arrêt</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </section>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
