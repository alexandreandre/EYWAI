import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowLeft, FileText } from 'lucide-react';

import {
  bulletinStatusLabel,
  choiceLabel,
  listMyParticipationBulletins,
  respondParticipationBulletin,
  type ParticipationBulletin,
  type ParticipationChoiceType,
} from '@/api/participation';
import { openDocumentPreview } from '@/api/documents';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { useToast } from '@/hooks/use-toast';

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount);
}

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR');
}

function BulletinCard({ bulletin }: { bulletin: ParticipationBulletin }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [choice, setChoice] = useState<ParticipationChoiceType | ''>('');
  const [partialAmount, setPartialAmount] = useState('');
  const canRespond = bulletin.status === 'sent';

  const respondMut = useMutation({
    mutationFn: () =>
      respondParticipationBulletin(bulletin.id, {
        choice_type: choice as ParticipationChoiceType,
        choice_cash_amount:
          choice === 'partial_cash' ? parseFloat(partialAmount) || 0 : undefined,
      }),
    onSuccess: () => {
      toast({ title: 'Votre choix a bien été enregistré.' });
      void queryClient.invalidateQueries({ queryKey: ['my-participation-bulletins'] });
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Enregistrement impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
  });

  const previewPdf = async () => {
    if (!bulletin.generated_document_id) {
      toast({
        title: 'Document indisponible',
        description: 'Le PDF n’a pas encore été généré.',
        variant: 'destructive',
      });
      return;
    }
    try {
      await openDocumentPreview(bulletin.generated_document_id, {
        title: `Bulletin ${bulletin.dispositif_type}`,
      });
    } catch {
      toast({ title: 'Aperçu impossible', variant: 'destructive' });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg capitalize">
          {bulletin.exercise_label || bulletin.dispositif_type} — {bulletin.dispositif_type}
        </CardTitle>
        <CardDescription>
          Net à payer : {formatCurrency(bulletin.net_amount)} —{' '}
          {bulletinStatusLabel(bulletin.status)}
          {bulletin.deadline_at && canRespond && (
            <> — Répondre avant le {formatDate(bulletin.deadline_at)}</>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>
            <span className="text-muted-foreground">Brut</span>
            <p className="font-medium">{formatCurrency(bulletin.gross_amount)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">CSG</span>
            <p className="font-medium">
              {formatCurrency(bulletin.csg_non_deductible + bulletin.csg_deductible)}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Acompte</span>
            <p className="font-medium">{formatCurrency(bulletin.advance_amount)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Net</span>
            <p className="font-medium">{formatCurrency(bulletin.net_amount)}</p>
          </div>
        </div>

        {bulletin.generated_document_id && (
          <Button type="button" variant="outline" size="sm" onClick={() => void previewPdf()}>
            <FileText className="mr-2 h-4 w-4" />
            Voir le bulletin PDF
          </Button>
        )}

        {canRespond ? (
          <div className="space-y-4 rounded-lg border p-4">
            <p className="text-sm font-medium">Votre choix</p>
            <RadioGroup
              value={choice}
              onValueChange={(v) => setChoice(v as ParticipationChoiceType)}
            >
              <div className="flex items-start gap-2">
                <RadioGroupItem value="full_cash" id={`${bulletin.id}-cash`} />
                <Label htmlFor={`${bulletin.id}-cash`} className="font-normal">
                  Je perçois la totalité de la participation nette
                </Label>
              </div>
              <div className="flex items-start gap-2">
                <RadioGroupItem value="partial_cash" id={`${bulletin.id}-partial`} />
                <Label htmlFor={`${bulletin.id}-partial`} className="font-normal">
                  Je perçois un montant précis en numéraire
                </Label>
              </div>
              {choice === 'partial_cash' && (
                <Input
                  type="number"
                  min={0}
                  max={bulletin.net_amount}
                  step="0.01"
                  placeholder="Montant en €"
                  value={partialAmount}
                  onChange={(e) => setPartialAmount(e.target.value)}
                />
              )}
              <div className="flex items-start gap-2">
                <RadioGroupItem value="full_pee" id={`${bulletin.id}-pee`} />
                <Label htmlFor={`${bulletin.id}-pee`} className="font-normal">
                  Je place la totalité sur le PEE
                </Label>
              </div>
            </RadioGroup>
            <Button
              disabled={!choice || respondMut.isPending}
              onClick={() => respondMut.mutate()}
            >
              Valider mon choix
            </Button>
          </div>
        ) : (
          bulletin.choice_type && (
            <div className="rounded-md bg-muted/50 p-3 text-sm">
              <p>
                Choix enregistré : <strong>{choiceLabel(bulletin.choice_type)}</strong>
              </p>
              {bulletin.responded_at && (
                <p className="text-muted-foreground">Le {formatDate(bulletin.responded_at)}</p>
              )}
            </div>
          )
        )}
      </CardContent>
    </Card>
  );
}

export default function EmployeeParticipationPage() {
  const { data: bulletins = [], isLoading, isError } = useQuery({
    queryKey: ['my-participation-bulletins'],
    queryFn: listMyParticipationBulletins,
  });

  const pending = bulletins.filter((b) => b.status === 'sent');
  const history = bulletins.filter((b) => b.status !== 'sent');

  if (isLoading) {
    return <SharkFinLoader variant="fullPage" label="Chargement…" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Retour
          </Link>
        </Button>
      </div>

      <PageHeader
        title="Participation & intéressement"
        description="Consultez vos bulletins d'option et indiquez votre choix de placement."
      />

      {isError && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          Impossible de charger vos bulletins.
        </div>
      )}

      {pending.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">À compléter</h2>
          {pending.map((b) => (
            <BulletinCard key={b.id} bulletin={b} />
          ))}
        </section>
      )}

      {history.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Historique</h2>
          {history.map((b) => (
            <BulletinCard key={b.id} bulletin={b} />
          ))}
        </section>
      )}

      {bulletins.length === 0 && !isError && (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            Aucun bulletin d&apos;option pour le moment.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
