import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, Loader2 } from 'lucide-react';

import apiClient from '@/api/apiClient';
import { JaugeMotDePasse } from '@/components/auth/JaugeMotDePasse';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/contexts/AuthContext';
import { isPasswordAcceptable, raisonActivationImpossible } from '@/lib/activationUtils';
import { messageEchecConnexion } from '@/lib/messageEchecConnexion';
import { resolvePostLoginPath } from '@/lib/routeAccess';

const MESSAGE_LIEN_PERIME =
  'Ce lien d’invitation n’est plus valable : il a déjà servi ou il a expiré. Demandez-en un nouveau à la personne qui vous l’a envoyé.';

/** Message d'un refus du serveur : lien périmé, mot de passe refusé, ou panne. */
function messageDuRefus(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail as { code?: string; message?: string } | undefined;
    if ((detail?.code === 'lien_invalide' || detail?.code === 'mot_de_passe_invalide') && detail.message) {
      return detail.message;
    }
  }
  return messageEchecConnexion(err);
}

type Etat =
  | { etape: 'verification' }
  | { etape: 'formulaire'; prenom: string | null; email: string }
  | { etape: 'perime'; message: string };

/**
 * Lien d'invitation : /connexion?jeton=…
 * La personne invitée arrive ici, crée son mot de passe, puis elle est connectée.
 * Ouvrir le lien ne le consomme pas (un aperçu de messagerie ne le grille pas) : il ne sert
 * qu'à l'enregistrement du mot de passe. Ensuite, connexion normale (adresse et mot de passe).
 */
export default function ConnexionParLienPage() {
  const [searchParams] = useSearchParams();
  const jeton = searchParams.get('jeton') ?? '';
  const { login } = useAuth();
  const navigate = useNavigate();
  const [etat, setEtat] = useState<Etat>({ etape: 'verification' });
  const [motDePasse, setMotDePasse] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [voir, setVoir] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    if (!jeton) {
      setEtat({ etape: 'perime', message: 'Ce lien d’invitation est incomplet. Demandez-en un nouveau à la personne qui vous l’a envoyé.' });
      return;
    }
    let annule = false;
    apiClient
      .post('/api/auth/lien-de-connexion/verifier', { jeton })
      .then(({ data }) => {
        if (annule) return;
        setEtat(
          data?.valide
            ? { etape: 'formulaire', prenom: data.prenom ?? null, email: data.email ?? '' }
            : { etape: 'perime', message: MESSAGE_LIEN_PERIME },
        );
      })
      .catch((err) => {
        if (!annule) setEtat({ etape: 'perime', message: messageDuRefus(err) });
      });
    return () => {
      annule = true;
    };
  }, [jeton]);

  const raison = raisonActivationImpossible(motDePasse, confirmation);

  const creer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (raison) {
      setErreur(raison);
      return;
    }
    setErreur('');
    setEnvoi(true);
    try {
      const { data } = await apiClient.post('/api/auth/lien-de-connexion/activer', {
        jeton,
        mot_de_passe: motDePasse,
      });
      // Le jeton ne reste pas dans l'adresse ni dans l'historique.
      window.history.replaceState(null, '', '/connexion');
      const me = await login({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_in: data.expires_in,
        expires_at: data.expires_at,
      });
      navigate(resolvePostLoginPath(undefined, me), { replace: true });
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
      if (detail?.code === 'lien_invalide') {
        setEtat({ etape: 'perime', message: messageDuRefus(err) });
      } else {
        setErreur(messageDuRefus(err));
      }
      setEnvoi(false);
    }
  };

  if (etat.etape === 'verification') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (etat.etape === 'perime') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-2xl">Lien expiré</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-destructive" role="alert">
              {etat.message}
            </p>
            <Link to="/login" className="text-sm text-primary hover:underline">
              Aller à la page de connexion
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">{etat.prenom ? `Bienvenue ${etat.prenom}` : 'Bienvenue'}</CardTitle>
          <CardDescription>
            Créez votre mot de passe pour accéder à Martine. Vous vous connecterez ensuite avec votre
            adresse e-mail et ce mot de passe.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={creer} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="invitation-email">Adresse e-mail</Label>
              <Input id="invitation-email" type="email" value={etat.email} readOnly autoComplete="username" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="invitation-mot-de-passe">Mot de passe</Label>
              <div className="relative">
                <Input
                  id="invitation-mot-de-passe"
                  type={voir ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={motDePasse}
                  onChange={(e) => setMotDePasse(e.target.value)}
                  required
                  disabled={envoi}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setVoir(!voir)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={voir ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                >
                  {voir ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <JaugeMotDePasse password={motDePasse} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="invitation-confirmation">Confirmez le mot de passe</Label>
              <Input
                id="invitation-confirmation"
                type={voir ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                required
                disabled={envoi}
              />
            </div>
            {erreur && (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={envoi || !isPasswordAcceptable(motDePasse) || motDePasse !== confirmation}
            >
              {envoi && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer mon mot de passe et me connecter
            </Button>
            {raison && !envoi && <p className="text-center text-sm text-muted-foreground">{raison}</p>}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
