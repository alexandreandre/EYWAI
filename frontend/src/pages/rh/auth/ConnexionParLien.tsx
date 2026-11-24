import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

import apiClient from '@/api/apiClient';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { messageEchecConnexion } from '@/lib/messageEchecConnexion';
import { resolvePostLoginPath } from '@/lib/routeAccess';

const MESSAGE_LIEN_PERIME =
  'Ce lien de connexion n’est plus valable : il a déjà servi ou il a expiré. Demandez-en un nouveau sur la page de connexion.';

/** Message d'un lien refusé : servi, expiré ou inconnu (code `lien_invalide` du serveur). */
function messageDuRefus(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail as { code?: string; message?: string } | undefined;
    if (detail?.code === 'lien_invalide' && detail.message) return detail.message;
  }
  return messageEchecConnexion(err);
}

type Etat =
  | { etape: 'verification' }
  | { etape: 'pret'; prenom: string | null }
  | { etape: 'connexion' }
  | { etape: 'erreur'; message: string };

/**
 * Page de connexion d'un lien sans mot de passe : /connexion?jeton=…
 * Ouvrir le lien ne connecte pas : la page vérifie qu'il est valable et propose
 * « Me connecter ». Seul ce clic sert le lien (usage unique) ; un aperçu de
 * messagerie ou un antivirus qui ouvre l'adresse ne le consomme donc pas.
 */
export default function ConnexionParLienPage() {
  const [searchParams] = useSearchParams();
  const jeton = searchParams.get('jeton') ?? '';
  const { login } = useAuth();
  const navigate = useNavigate();
  const [etat, setEtat] = useState<Etat>({ etape: 'verification' });

  useEffect(() => {
    if (!jeton) {
      setEtat({ etape: 'erreur', message: 'Ce lien de connexion est incomplet. Demandez-en un nouveau sur la page de connexion.' });
      return;
    }
    let annule = false;
    apiClient
      .post('/api/auth/lien-de-connexion/verifier', { jeton })
      .then(({ data }) => {
        if (annule) return;
        setEtat(data?.valide ? { etape: 'pret', prenom: data.prenom ?? null } : { etape: 'erreur', message: MESSAGE_LIEN_PERIME });
      })
      .catch((err) => {
        if (!annule) setEtat({ etape: 'erreur', message: messageDuRefus(err) });
      });
    return () => {
      annule = true;
    };
  }, [jeton]);

  const seConnecter = async () => {
    setEtat({ etape: 'connexion' });
    try {
      const { data } = await apiClient.post('/api/auth/lien-de-connexion/ouvrir', { jeton });
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
      setEtat({ etape: 'erreur', message: messageDuRefus(err) });
    }
  };

  const titre = etat.etape === 'pret' && etat.prenom ? `Bonjour ${etat.prenom}` : 'Connexion';

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">{titre}</CardTitle>
          <CardDescription>
            {etat.etape === 'erreur'
              ? 'Ce lien ne peut pas vous connecter.'
              : 'Connectez-vous à Martine, sans mot de passe.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {etat.etape === 'verification' && (
            <div className="flex justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}
          {(etat.etape === 'pret' || etat.etape === 'connexion') && (
            <>
              <Button className="w-full" onClick={seConnecter} disabled={etat.etape === 'connexion'}>
                {etat.etape === 'connexion' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Me connecter
              </Button>
              <p className="text-xs text-muted-foreground">
                Ce lien ne sert qu’une fois. Les fois suivantes, demandez un lien sur la page de connexion.
              </p>
            </>
          )}
          {etat.etape === 'erreur' && (
            <>
              <p className="text-sm text-destructive" role="alert">
                {etat.message}
              </p>
              <Link to="/login" className="text-sm text-primary hover:underline">
                Aller à la page de connexion
              </Link>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
