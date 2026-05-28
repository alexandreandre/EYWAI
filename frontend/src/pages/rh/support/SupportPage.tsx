// frontend/src/pages/support/SupportPage.tsx
// Assistant demande support (5 étapes)

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import axios from 'axios';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

import { createTicket } from '@/api/support';
import {
  clearSupportConfirmationTicket,
  persistSupportConfirmationTicket,
} from '@/lib/supportConfirmation';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { cn } from '@/lib/utils';

const MODULES = [
  { id: 'employees', label: 'Employés' },
  { id: 'payroll', label: 'Paie & Bulletins' },
  { id: 'absences', label: 'Absences & Congés' },
  { id: 'expenses', label: 'Notes de frais' },
  { id: 'schedules', label: 'Calendriers & Plannings' },
  { id: 'badgeuse', label: 'Badgeuse & pointage' },
  { id: 'offboarding', label: 'Sorties de salarié' },
  { id: 'simulation', label: 'Simulation de paie' },
  { id: 'collective_agreements', label: 'Conventions collectives' },
  { id: 'seizures', label: 'Saisies & Avances' },
  { id: 'residence_permits', label: 'Titres de séjour' },
  { id: 'annual_reviews', label: 'Entretiens annuels' },
  { id: 'promotions', label: 'Promotions' },
  { id: 'bonuses', label: 'Primes & Participation' },
  { id: 'mutual', label: 'Mutuelle' },
  { id: 'recruitment', label: 'Recrutement' },
  { id: 'cse', label: 'CSE & dialogue social' },
  { id: 'medical_follow_up', label: 'Suivi médical' },
  { id: 'account', label: 'Mon compte / Accès' },
  { id: 'copilot', label: 'Copilot IA' },
  { id: 'other', label: 'Autre' },
];

const COMMON_TYPES = [
  'Blocage',
  'Question fonctionnelle',
  'Anomalie',
  'Suggestion',
  'Document manquant',
  "Problème d'accès",
];

const EXTRA_TYPES: Record<string, string[]> = {
  payroll: ['Erreur de calcul', 'Bulletin non généré', 'Simulation incorrecte'],
  absences: ['Demande non validée', 'Solde incorrect'],
  account: ['Mot de passe oublié', 'Mauvaise entreprise', "Plus d'accès"],
};

const URGENCY_LEVELS = [
  {
    id: 'critique' as const,
    label: 'Critique',
    description: 'Bloquant, impact immédiat sur la paie ou les accès',
    color: 'red',
  },
  {
    id: 'elevee' as const,
    label: 'Élevée',
    description: 'Important, traitement prioritaire requis',
    color: 'orange',
  },
  {
    id: 'normale' as const,
    label: 'Normale',
    description: 'Demande standard',
    color: 'blue',
  },
  {
    id: 'faible' as const,
    label: 'Faible',
    description: 'Pas urgent, à traiter quand possible',
    color: 'gray',
  },
];

const MODULES_HAUTE_PRIORITE = ['payroll', 'offboarding', 'seizures'];

const MODULE_LABELS: Record<string, string> = Object.fromEntries(
  MODULES.map((m) => [m.id, m.label]),
);

const URGENCY_CARD_STYLES: Record<string, string> = {
  red: 'border-red-500/80 bg-red-50/60 dark:bg-red-950/20',
  orange: 'border-orange-500/80 bg-orange-50/60 dark:bg-orange-950/20',
  blue: 'border-blue-500/80 bg-blue-50/60 dark:bg-blue-950/20',
  gray: 'border-slate-400/80 bg-slate-50/80 dark:bg-slate-900/40',
};

export default function SupportPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const { activeCompany } = useCompany();

  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedUrgency, setSelectedUrgency] = useState<
    'critique' | 'elevee' | 'normale' | 'faible' | null
  >(null);
  const [description, setDescription] = useState('');
  const [context, setContext] = useState('');
  const [is503Error, setIs503Error] = useState(false);

  const displayName = useMemo(() => {
    const parts = [user?.first_name, user?.last_name].filter(Boolean);
    if (parts.length) return parts.join(' ');
    return user?.email ?? '—';
  }, [user]);

  const companyName = activeCompany?.company_name ?? '—';
  const userEmail = user?.email ?? '—';

  useEffect(() => {
    clearSupportConfirmationTicket();
  }, []);

  useEffect(() => {
    setSelectedType(null);
  }, [selectedModuleId]);

  useEffect(() => {
    if (selectedModuleId && MODULES_HAUTE_PRIORITE.includes(selectedModuleId)) {
      setSelectedUrgency('elevee');
    }
  }, [selectedModuleId]);

  const requestTypes = useMemo(() => {
    const extra = selectedModuleId ? (EXTRA_TYPES[selectedModuleId] ?? []) : [];
    return [...COMMON_TYPES, ...extra];
  }, [selectedModuleId]);

  const canGoNext = useMemo(() => {
    switch (currentStep) {
      case 1:
        return selectedModuleId !== null;
      case 2:
        return selectedType !== null;
      case 3:
        return selectedUrgency !== null;
      case 4:
        return description.length >= 30 && description.length <= 2000;
      default:
        return false;
    }
  }, [currentStep, selectedModuleId, selectedType, selectedUrgency, description.length]);

  const goNext = () => {
    if (currentStep < 5 && canGoNext) {
      setCurrentStep((s) => (s + 1) as 1 | 2 | 3 | 4 | 5);
    }
  };

  const goPrev = () => {
    if (currentStep > 1) {
      setCurrentStep((s) => (s - 1) as 1 | 2 | 3 | 4 | 5);
    }
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createTicket({
        module: MODULE_LABELS[selectedModuleId!],
        request_type: selectedType!,
        urgency: selectedUrgency!,
        description,
        ...(context.trim() ? { context: context.trim() } : {}),
      }),
    onMutate: () => setIs503Error(false),
    onSuccess: (ticket) => {
      persistSupportConfirmationTicket(ticket.id);
      navigate('/support/confirmation', {
        state: { ticketId: ticket.id },
        replace: true,
      });
    },
    onError: (error: unknown) => {
      if (axios.isAxiosError(error) && error.response?.status === 503) {
        setIs503Error(true);
        return;
      }
      toast({
        title: 'Erreur',
        description:
          axios.isAxiosError(error) && error.response?.data?.detail
            ? String(error.response.data.detail)
            : "Une erreur s'est produite. Réessayez plus tard.",
        variant: 'destructive',
      });
    },
  });

  const handleSubmit = () => {
    if (
      !selectedModuleId ||
      !selectedType ||
      !selectedUrgency ||
      description.length < 30
    ) {
      return;
    }
    createMutation.mutate();
  };

  return (
    <EmployeePageShell className="pb-6">
      <EmployeePageHeader
        title="Contacter le support"
        description="Décrivez votre besoin en quelques étapes. Réponse habituelle sous 24 à 48 h ouvrées."
      />

      <div className="mx-auto flex max-w-3xl flex-col gap-8">
      <div className="flex gap-2" aria-hidden>
        {([1, 2, 3, 4, 5] as const).map((step) => (
          <div
            key={step}
            className={cn(
              'h-2 flex-1 rounded-full transition-colors',
              step <= currentStep ? 'bg-primary' : 'bg-muted',
            )}
          />
        ))}
      </div>
      <p className="text-muted-foreground text-center text-xs">
        Étape {currentStep} sur 5
      </p>

      <Card>
        <CardHeader>
          <CardTitle>
            {currentStep === 1 && 'Quel module concerne votre demande ?'}
            {currentStep === 2 && 'Type de demande'}
            {currentStep === 3 && "Niveau d'urgence"}
            {currentStep === 4 && 'Détails'}
            {currentStep === 5 && 'Récapitulatif'}
          </CardTitle>
          {currentStep === 1 && (
            <CardDescription>Sélectionnez un seul domaine.</CardDescription>
          )}
          {currentStep === 2 && (
            <CardDescription>Choisissez la catégorie la plus proche.</CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          {currentStep === 1 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {MODULES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setSelectedModuleId(m.id)}
                  className={cn(
                    'rounded-lg border bg-card p-4 text-left text-sm font-medium transition-all hover:bg-accent/50',
                    selectedModuleId === m.id &&
                      'border-primary ring-2 ring-primary ring-offset-2 ring-offset-background',
                  )}
                >
                  {m.label}
                </button>
              ))}
            </div>
          )}

          {currentStep === 2 && (
            <div className="flex flex-col gap-2">
              {requestTypes.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSelectedType(t)}
                  className={cn(
                    'rounded-lg border bg-card px-4 py-3 text-left text-sm transition-all hover:bg-accent/50',
                    selectedType === t &&
                      'border-primary ring-2 ring-primary ring-offset-2 ring-offset-background',
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {URGENCY_LEVELS.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => setSelectedUrgency(u.id)}
                    className={cn(
                      'rounded-lg border-2 p-4 text-left transition-all hover:opacity-95',
                      URGENCY_CARD_STYLES[u.color] ?? '',
                      selectedUrgency === u.id &&
                        'ring-2 ring-primary ring-offset-2 ring-offset-background',
                    )}
                  >
                    <div className="font-semibold">{u.label}</div>
                    <p className="text-muted-foreground mt-1 text-xs">{u.description}</p>
                  </button>
                ))}
              </div>
              {selectedUrgency === 'critique' && (
                <p className="text-sm text-red-700 dark:text-red-400">
                  Les demandes critiques liées à la paie sont traitées en priorité absolue.
                </p>
              )}
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="support-description" className="text-sm font-medium">
                  Description <span className="text-destructive">*</span>
                </label>
                <Textarea
                  id="support-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  minLength={30}
                  maxLength={2000}
                  rows={8}
                  placeholder="Décrivez la situation en au moins 30 caractères…"
                  className="resize-y"
                />
                <p className="text-muted-foreground text-right text-xs">
                  {description.length} / 2000
                  {description.length > 0 && description.length < 30 && (
                    <span className="text-destructive"> — minimum 30 caractères</span>
                  )}
                </p>
              </div>
              <div className="space-y-2">
                <label htmlFor="support-context" className="text-sm font-medium">
                  Contexte complémentaire <span className="text-muted-foreground">(optionnel)</span>
                </label>
                <Input
                  id="support-context"
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  placeholder="Référence, écran, période…"
                />
              </div>
            </div>
          )}

          {currentStep === 5 && (
            <div className="space-y-4 text-sm">
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                <div>
                  <span className="text-muted-foreground">Nom</span>
                  <p className="font-medium">{displayName}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">E-mail</span>
                  <p className="font-medium">{userEmail}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Entreprise</span>
                  <p className="font-medium">{companyName}</p>
                </div>
              </div>
              <dl className="grid gap-3 rounded-lg border p-4">
                <div>
                  <dt className="text-muted-foreground text-xs uppercase">Module</dt>
                  <dd className="font-medium">
                    {selectedModuleId ? MODULE_LABELS[selectedModuleId] : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs uppercase">Type</dt>
                  <dd className="font-medium">{selectedType ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs uppercase">Urgence</dt>
                  <dd>
                    <Badge variant="secondary">{selectedUrgency ?? '—'}</Badge>
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs uppercase">Description</dt>
                  <dd className="whitespace-pre-wrap font-normal">{description}</dd>
                </div>
                {context.trim() ? (
                  <div>
                    <dt className="text-muted-foreground text-xs uppercase">Contexte</dt>
                    <dd className="font-normal">{context.trim()}</dd>
                  </div>
                ) : null}
              </dl>

              {is503Error && (
                <div
                  className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm"
                  role="alert"
                >
                  <p>
                    {`L'envoi de votre demande a échoué. Vous pouvez contacter directement notre équipe à `}
                    <a
                      href="mailto:contact@eywai.fr"
                      className="font-medium text-primary underline underline-offset-2"
                    >
                      contact@eywai.fr
                    </a>
                    .
                  </p>
                </div>
              )}

              <Button
                type="button"
                className="w-full sm:w-auto"
                disabled={createMutation.isPending}
                onClick={handleSubmit}
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Envoi en cours…
                  </>
                ) : (
                  'Envoyer ma demande'
                )}
              </Button>
            </div>
          )}

          {currentStep < 5 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-6">
              <Button
                type="button"
                variant="outline"
                onClick={goPrev}
                disabled={currentStep === 1}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Précédent
              </Button>
              <Button type="button" onClick={goNext} disabled={!canGoNext}>
                Suivant
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
      </div>
    </EmployeePageShell>
  );
}
