import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import apiClient from '@/api/apiClient';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/use-toast';
import { generateDocument, openDocumentPreview, type GeneratedDocument } from '@/api/documents';
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from '@/api/documentLibrary';
import {
  ATTESTATION_COURANTE_TYPES,
  NOMBRE_MOIS_MAX,
  NOMBRE_MOIS_PAR_DEFAUT,
  payloadAttestation,
  type AttestationType,
} from '@/lib/documentGenerationConfig';
import { rhCanViewEmployeeDocuments } from '@/lib/employeeExitDocumentsAccess';

interface Salarie {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  employment_status?: string | null;
  exit_last_working_day?: string | null;
}

export interface AttestationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Sur la fiche, le salarié est connu ; ailleurs la fenêtre propose la liste. */
  employee?: Salarie | null;
  onGenerated?: (doc: GeneratedDocument) => void;
}

const AIDE: Record<AttestationType, string> = {
  attestation_emploi:
    "Poste, contrat, date d'entrée, ancienneté et rémunération : ce que demandent une banque ou un bailleur.",
  attestation_salaire:
    'Salaire brut et net avant impôt, repris des derniers bulletins remis au salarié.',
};

const nomDe = (e?: Salarie | null) => `${e?.first_name ?? ''} ${e?.last_name ?? ''}`.trim();

function detailDeLErreur(e: unknown): string {
  const detail =
    e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      : undefined;
  return typeof detail === 'string' && detail.trim()
    ? detail
    : "Le serveur n'a pas pu produire la lettre. Réessayez dans un instant.";
}

/**
 * La seule fenêtre « Générer une attestation » (05/11/2026) : fiche du salarié
 * (mode paie compris), page Documents, et Exports > Déclarations.
 */
export function AttestationDialog({ open, onOpenChange, employee, onGenerated }: AttestationDialogProps) {
  const [employeeId, setEmployeeId] = useState(employee?.id ?? '');
  const [type, setType] = useState<AttestationType | ''>('');
  const [nombreMois, setNombreMois] = useState(String(NOMBRE_MOIS_PAR_DEFAUT));
  const [templateId, setTemplateId] = useState('__martine__');
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setEmployeeId(employee?.id ?? '');
    setType('');
    setNombreMois(String(NOMBRE_MOIS_PAR_DEFAUT));
    setTemplateId('__martine__');
    setErreur(null);
  }, [open, employee?.id]);

  const { data: salaries = [] } = useQuery({
    queryKey: ['employees', 'attestation-dialog'],
    queryFn: async () => {
      const r = await apiClient.get<Salarie[]>('/api/employees', { params: { limit: 500 } });
      return r.data ?? [];
    },
    enabled: open && !employee,
  });

  const choix = useMemo(
    () =>
      salaries
        .filter(
          (e) =>
            (e.employment_status || 'actif').toLowerCase() !== 'parti' && rhCanViewEmployeeDocuments(e),
        )
        .sort((a, b) => nomDe(a).localeCompare(nomDe(b), 'fr')),
    [salaries],
  );

  const salarie = employee ?? choix.find((e) => e.id === employeeId) ?? null;
  const nom = nomDe(salarie);

  const { data: modeles = [] } = useQuery({
    queryKey: ['document-library', 'templates', 'active', 'attestation-dialog'],
    queryFn: () => getTemplates('active'),
    enabled: open && !!type,
  });
  const modelesDuType = useMemo(
    () => modeles.filter((t: DocumentTemplate) => t.document_type === type && t.status === 'active'),
    [modeles, type],
  );

  const mois = Number(nombreMois);
  const moisValide = Number.isInteger(mois) && mois >= 1 && mois <= NOMBRE_MOIS_MAX;
  const pret = !!employeeId && !!type && (type !== 'attestation_salaire' || moisValide);

  const generation = useMutation({
    mutationFn: generateDocument,
    onSuccess: async (doc) => {
      const libelle = DOCUMENT_TYPE_LABELS[doc.document_type] ?? 'Attestation';
      toast({
        title: `${libelle} de ${nom} prête`,
        description: 'Elle est rangée dans les documents du salarié.',
      });
      onGenerated?.(doc);
      onOpenChange(false);
      try {
        await openDocumentPreview(doc.id, { title: libelle, subtitle: nom });
      } catch {
        toast({
          title: 'Aperçu impossible',
          description: 'La lettre est bien générée : ouvrez-la depuis les documents du salarié.',
          variant: 'destructive',
        });
      }
    },
    onError: (e: unknown) => {
      const message = detailDeLErreur(e);
      setErreur(message);
      toast({ title: 'Attestation non générée', description: message, variant: 'destructive' });
    },
  });

  const generer = () => {
    if (!pret || !type) return;
    setErreur(null);
    generation.mutate(
      payloadAttestation({ employeeId, documentType: type, nombreMois: mois, templateId }),
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Générer une attestation</DialogTitle>
          <DialogDescription>{nom || 'Choisissez le salarié.'}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {!employee ? (
            <div className="space-y-2">
              <Label htmlFor="attestation-salarie">Salarié</Label>
              <Select
                value={employeeId || undefined}
                onValueChange={(v) => {
                  setEmployeeId(v);
                  setErreur(null);
                }}
              >
                <SelectTrigger id="attestation-salarie">
                  <SelectValue placeholder="Choisir un salarié…" />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  {choix.map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {nomDe(e)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="attestation-type">Type d&apos;attestation</Label>
            <Select
              value={type || undefined}
              onValueChange={(v) => {
                setType(v as AttestationType);
                setTemplateId('__martine__');
                setErreur(null);
              }}
            >
              <SelectTrigger id="attestation-type">
                <SelectValue placeholder="Choisir…" />
              </SelectTrigger>
              <SelectContent>
                {ATTESTATION_COURANTE_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {DOCUMENT_TYPE_LABELS[t] ?? t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {type ? <p className="text-xs text-muted-foreground">{AIDE[type]}</p> : null}
          </div>

          {type === 'attestation_salaire' ? (
            <div className="space-y-2">
              <Label htmlFor="attestation-mois">Nombre de mois</Label>
              <Input
                id="attestation-mois"
                type="number"
                inputMode="numeric"
                min={1}
                max={NOMBRE_MOIS_MAX}
                value={nombreMois}
                onChange={(e) => {
                  setNombreMois(e.target.value);
                  setErreur(null);
                }}
                className="w-24"
              />
              {!moisValide ? (
                <p className="text-xs text-destructive">Entre 1 et {NOMBRE_MOIS_MAX} mois.</p>
              ) : null}
            </div>
          ) : null}

          {type ? (
            <div className="space-y-2">
              <Label htmlFor="attestation-modele">Modèle</Label>
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger id="attestation-modele">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__martine__">Standard Martine</SelectItem>
                  {modelesDuType.map((tpl) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <p className="text-xs text-muted-foreground">
            Signée au nom du signataire réglé dans Entreprise &gt; Fiche.
          </p>

          {erreur ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {erreur}
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={generer} disabled={!pret || generation.isPending}>
            {generation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Générer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
