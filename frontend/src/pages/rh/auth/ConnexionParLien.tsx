import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

import apiClient from '@/api/apiClient';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { messageEchecConnexion } from '@/lib/messageEchecConnexion';
import { resolvePostLoginPath } from '@/lib/routeAccess';

/** Message d'un lien refusé : servi, expiré ou inconnu (code `lien_invalide` du serveur). */
function messageDuRefus(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail as { code?: string; message?: string } | undefined;
    if (detail?.code === 'lien_invalide' && detail.message) return detail.message;
  }
  return messageEchecConnexion(err);
}

/**
 * Connexion par lien, sans mot de passe : /connexion?jeton=…
 * Le lien sert une fois ; la session s'ouvre comme après un mot de passe.
 */
export default function ConnexionParLienPage() {
  const [searchParams] = useSearchParams();
  const jeton = searchParams.get('jeton') ?? '';
  const { login } = useAuth();
  const navigate = useNavigate();
  const [erreur, setErreur] = useState('');
  // Le lien ne sert qu'une fois : jamais deux appels, même si l'écran se monte deux fois.
  const dejaOuvert = useRef(false);

  useEffect(() => {
    if (dejaOuvert.current) return;
    dejaOuvert.current = true;
    if (!jeton) {
      setErreur('Ce lien de connexion est incomplet. Demandez-en un nouveau sur la page de connexion.');
      return;
    }
    (async () => {
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
        setErreur(messageDuRefus(err));
      }
    })();
  }, [jeton, login, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Connexion</CardTitle>
          <CardDescription>
            {erreur ? 'Le lien n’a pas pu vous connecter.' : 'Connexion en cours…'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {erreur ? (
            <>
              <p className="text-sm text-destructive" role="alert">
                {erreur}
              </p>
              <Link to="/login" className="text-sm text-primary hover:underline">
                Aller à la page de connexion
              </Link>
            </>
          ) : (
            <div className="flex justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
