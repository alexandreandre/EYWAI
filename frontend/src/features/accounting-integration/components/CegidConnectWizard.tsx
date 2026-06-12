import { useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  HelpCircle,
  KeyRound,
  Link2,
} from 'lucide-react';
import { ProviderLogo } from '@/components/integrations/ProviderLogo';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

const CEGID_LIFE_URL = 'https://www.cegidlife.com';
const CEGID_DEVELOPERS_URL = 'https://developers.cegid.com/';
const CEGID_DOC_API_KEY =
  'https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/Getapikey.html';
const CEGID_DOC_SUBSCRIPTION =
  'https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/Subscription.html';
const CEGID_DOC_LOOP_HUB =
  'https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/LoopHub.html';

type WizardPhase = 'intro' | 'guide' | 'paste';

type CegidConnectWizardProps = {
  loopApiKey: string;
  apimSubscriptionKey: string;
  codeDossier: string;
  cegidBaseUrl: string;
  onLoopApiKeyChange: (v: string) => void;
  onApimSubscriptionKeyChange: (v: string) => void;
  onCodeDossierChange: (v: string) => void;
  onCegidBaseUrlChange: (v: string) => void;
  onBack: () => void;
  onFinalize: () => void;
  isSaving: boolean;
  isTesting: boolean;
  /** Reprendre directement au collage des identifiants (ex. modification). */
  initialPhase?: WizardPhase;
  /** Masquer les boutons Retour/Annuler (ex. panneau super-admin embarqué). */
  hideBackActions?: boolean;
};

function openExternal(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer');
}

const GUIDE_STEPS = [
  {
    id: 'apikey',
    title: 'Clé API (APIKey)',
    description:
      'Sur Cegid Life : Mon profil → catalogue des services (« VOIR LA LISTE ») → « Loop APIKey Standard (P04448) » → GÉNÉRER UNE CLÉ D’API. Copiez la clé ET le secret (format clé:secret) : ils ne sont plus affichés ensuite.',
    actionLabel: 'Guide clé API',
    actionUrl: CEGID_DOC_API_KEY,
  },
  {
    id: 'subscription',
    title: 'Clé d’abonnement (subscription key)',
    description:
      'Abonnez-vous au service « Cegid Developers - APIs Cegid Loop » sur Cegid Life, puis sur developers.cegid.com → menu Subscription → « create primary and secondary keys ». Copiez la subscription key.',
    actionLabel: 'Guide abonnement',
    actionUrl: CEGID_DOC_SUBSCRIPTION,
  },
  {
    id: 'loophub',
    title: 'Activer la clé dans Loop Hub',
    description:
      'Étape indispensable : un administrateur du cabinet doit activer la clé API dans le Loop Hub de Cegid Loop. Sans cette activation, l’API refuse les appels même avec des clés valides.',
    actionLabel: 'Guide Loop Hub',
    actionUrl: CEGID_DOC_LOOP_HUB,
  },
  {
    id: 'dossier',
    title: 'Code dossier (codeIbs)',
    description:
      'Le code du dossier comptable dans Loop (codeIbs). Votre expert-comptable le connaît — c’est l’identifiant de votre entreprise côté cabinet.',
    actionLabel: null,
    actionUrl: null,
  },
] as const;

export function CegidConnectWizard({
  loopApiKey,
  apimSubscriptionKey,
  codeDossier,
  cegidBaseUrl,
  onLoopApiKeyChange,
  onApimSubscriptionKeyChange,
  onCodeDossierChange,
  onCegidBaseUrlChange,
  onBack,
  onFinalize,
  isSaving,
  isTesting,
  initialPhase = 'intro',
  hideBackActions = false,
}: CegidConnectWizardProps) {
  const [phase, setPhase] = useState<WizardPhase>(initialPhase);
  const [checkedSteps, setCheckedSteps] = useState<Record<string, boolean>>({});

  const apiKeyFormatValid = (() => {
    const v = loopApiKey.trim();
    if (v.length === 0) return true;
    const [key, ...rest] = v.split(':');
    return Boolean(key) && rest.join(':').trim().length > 0;
  })();

  const canFinalize =
    loopApiKey.trim().length > 0 &&
    apiKeyFormatValid &&
    apimSubscriptionKey.trim().length > 0 &&
    codeDossier.trim().length > 0;

  const toggleCheck = (id: string) => {
    setCheckedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (phase === 'intro') {
    return (
      <div className="space-y-5 rounded-lg border bg-muted/20 p-5">
        <div className="flex items-start gap-4">
          <ProviderLogo providerKey="cegid_quadra" size="lg" />
          <div className="min-w-0 flex-1 space-y-1">
            <h3 className="text-base font-semibold">Connecter Cegid Loop</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Envoyez vos écritures de paie (FEC) directement dans le logiciel comptable
              de votre cabinet. La configuration prend environ 5 minutes.
            </p>
          </div>
        </div>

        <Alert>
          <HelpCircle className="h-4 w-4" />
          <AlertTitle>Pas accès à Cegid Life ?</AlertTitle>
          <AlertDescription>
            Demandez à votre expert-comptable de générer les identifiants, ou partagez-lui
            le guide Cegid. Aucun partenariat EYWAI/Cegid n’est nécessaire — ce sont les
            clés de votre cabinet.
          </AlertDescription>
        </Alert>

        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => setPhase('guide')}>
            Configurer Cegid Loop
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          {!hideBackActions ? (
            <Button type="button" variant="ghost" onClick={onBack}>
              Retour
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  if (phase === 'guide') {
    return (
      <div className="space-y-5 rounded-lg border bg-muted/20 p-5">
        <div className="flex items-center gap-3">
          <ProviderLogo providerKey="cegid_quadra" size="md" />
          <div>
            <p className="font-medium">Étape 1 — Récupérer vos identifiants</p>
            <p className="text-muted-foreground text-xs">
              Ouvrez Cegid Life dans un nouvel onglet, puis cochez chaque élément obtenu.
            </p>
          </div>
        </div>

        <Button
          type="button"
          className="w-full sm:w-auto"
          onClick={() => openExternal(CEGID_LIFE_URL)}
        >
          <ExternalLink className="mr-2 h-4 w-4" />
          Ouvrir Cegid Life
        </Button>

        <ol className="space-y-3">
          {GUIDE_STEPS.map((item, index) => (
            <li
              key={item.id}
              className={cn(
                'rounded-lg border bg-background p-3 transition-colors',
                checkedSteps[item.id] && 'border-green-600/40 bg-green-50/50 dark:bg-green-950/20',
              )}
            >
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => toggleCheck(item.id)}
                  className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
                  aria-label={`Marquer ${item.title} comme fait`}
                >
                  {checkedSteps[item.id] ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  ) : (
                    <span className="flex h-5 w-5 items-center justify-center rounded-full border text-xs font-medium">
                      {index + 1}
                    </span>
                  )}
                </button>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-muted-foreground text-xs leading-relaxed">
                    {item.description}
                  </p>
                  {item.actionUrl && (
                    <Button
                      type="button"
                      variant="link"
                      className="h-auto p-0 text-xs"
                      onClick={() => openExternal(item.actionUrl!)}
                    >
                      {item.actionLabel}
                      <ExternalLink className="ml-1 h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => openExternal(CEGID_DEVELOPERS_URL)}
        >
          <Link2 className="mr-2 h-3.5 w-3.5" />
          Ouvrir Cegid Developers (clé d’abonnement)
        </Button>

        <div className="flex flex-wrap gap-2 border-t pt-4">
          <Button type="button" onClick={() => setPhase('paste')}>
            J’ai mes identifiants
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          {!hideBackActions ? (
            <Button type="button" variant="ghost" onClick={() => setPhase('intro')}>
              Retour
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 rounded-lg border bg-muted/20 p-5">
      <div className="flex items-center gap-3">
        <ProviderLogo providerKey="cegid_quadra" size="md" />
        <div>
          <p className="font-medium">Étape 2 — Coller vos identifiants</p>
          <p className="text-muted-foreground text-xs">
            Ces informations ne seront plus affichées après enregistrement (stockage sécurisé).
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="cegid-loop-apikey" className="flex items-center gap-1.5">
            <KeyRound className="h-3.5 w-3.5 text-muted-foreground" />
            Identifiant API Loop
          </Label>
          <Input
            id="cegid-loop-apikey"
            type="password"
            value={loopApiKey}
            onChange={(e) => onLoopApiKeyChange(e.target.value)}
            placeholder="Collez la clé au format clé:secret"
            autoComplete="off"
          />
          <p className="text-muted-foreground text-xs">
            Depuis Cegid Life → catalogue des services → Loop APIKey Standard (format clé:secret)
          </p>
          {!apiKeyFormatValid ? (
            <p className="text-destructive text-xs">
              Format attendu : clé:secret (les deux parties séparées par « : »).
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="cegid-subscription-key">Clé d’abonnement API</Label>
          <Input
            id="cegid-subscription-key"
            type="password"
            value={apimSubscriptionKey}
            onChange={(e) => onApimSubscriptionKeyChange(e.target.value)}
            placeholder="Collez la subscription key"
            autoComplete="off"
          />
          <p className="text-muted-foreground text-xs">
            Depuis Cegid Developers → Subscription
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="cegid-code-dossier">Code dossier comptable</Label>
          <Input
            id="cegid-code-dossier"
            value={codeDossier}
            onChange={(e) => onCodeDossierChange(e.target.value)}
            placeholder="Ex. le code IBS de votre dossier Loop"
          />
          <p className="text-muted-foreground text-xs">
            Fourni par votre expert-comptable ou visible dans Loop
          </p>
        </div>

        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-xs">
              Options avancées
              <ChevronDown className="ml-1 h-3.5 w-3.5" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="cegid-base-url">URL API (optionnel)</Label>
              <Input
                id="cegid-base-url"
                value={cegidBaseUrl}
                onChange={(e) => onCegidBaseUrlChange(e.target.value)}
                placeholder="https://loop-publicapi.cegid.com"
              />
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      <div className="flex flex-wrap gap-2 border-t pt-4">
        <Button
          type="button"
          disabled={!canFinalize || isSaving || isTesting}
          onClick={onFinalize}
        >
          {isTesting ? 'Connexion en cours…' : 'Finaliser la connexion'}
        </Button>
        <Button type="button" variant="outline" onClick={() => setPhase('guide')}>
          Revoir le guide
        </Button>
        {!hideBackActions ? (
          <Button type="button" variant="ghost" onClick={onBack}>
            Annuler
          </Button>
        ) : null}
      </div>
    </div>
  );
}
