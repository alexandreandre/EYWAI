// src/pages/Login.tsx (VERSION CORRIGÉE)

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate, useLocation, Link, useSearchParams, Navigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import apiClient from '@/api/apiClient';
import { Loader2 } from 'lucide-react';
import { log } from '@/lib/logger';
import { messageEchecConnexion } from '@/lib/messageEchecConnexion';
import { resolvePostLoginPath, safeReturnPath } from '@/lib/routeAccess';

export default function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Connexion sans mot de passe : un lien envoyé par e-mail.
  const [modeLien, setModeLien] = useState(false);
  const [lienEnvoye, setLienEnvoye] = useState('');
  const { user, login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get('session') === 'expired';

  const from = safeReturnPath(location.state?.from?.pathname);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (user) {
    return (
      <Navigate
        to={resolvePostLoginPath(from, user)}
        replace
      />
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const params = new URLSearchParams();
      params.append('username', identifier);
      params.append('password', password);

      const response = await apiClient.post('/api/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const me = await login({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_in: response.data.expires_in,
        expires_at: response.data.expires_at,
      });

      navigate(
        resolvePostLoginPath(from, me),
        { replace: true },
      );
    } catch (err: unknown) {
      log.error(
        'Connexion échouée',
        err instanceof Error ? err.message : err,
      );
      // Une erreur distincte par cas : une panne ne dit plus « mot de passe incorrect ».
      setError(messageEchecConnexion(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const demanderUnLien = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const { data } = await apiClient.post('/api/auth/lien-de-connexion', { email: identifier.trim() });
      setLienEnvoye(data?.message ?? 'Si un compte existe pour cette adresse, un lien de connexion vient d’y être envoyé.');
    } catch (err: unknown) {
      setError(messageEchecConnexion(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (modeLien) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background p-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-2xl">Connexion par lien</CardTitle>
            <CardDescription>
              Recevez par e-mail un lien qui vous connecte, sans mot de passe.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {lienEnvoye ? (
              <div className="space-y-4">
                <p className="text-sm" role="status">
                  {lienEnvoye} Pensez à regarder dans les indésirables.
                </p>
                <Button variant="outline" className="w-full" onClick={() => setLienEnvoye('')}>
                  Renvoyer un lien
                </Button>
              </div>
            ) : (
              <form onSubmit={demanderUnLien} className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="lien-email">Adresse e-mail</Label>
                  <Input
                    id="lien-email"
                    type="email"
                    autoComplete="email"
                    placeholder="email@example.com"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    required
                  />
                </div>
                {error && (
                  <p className="text-sm text-destructive" role="alert">
                    {error}
                  </p>
                )}
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Recevoir le lien
                </Button>
              </form>
            )}
            <button
              type="button"
              className="mt-4 text-xs text-primary hover:underline"
              onClick={() => {
                setModeLien(false);
                setLienEnvoye('');
                setError('');
              }}
            >
              Se connecter avec un mot de passe
            </button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Connexion</CardTitle>
          <CardDescription>Entrez vos identifiants pour accéder à votre espace.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit}
            className="space-y-4"
            method="post"
            autoComplete="on"
          >
            {sessionExpired && (
              <p className="text-sm text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-2">
                Votre session a expiré après une longue période d&apos;inactivité.
                Reconnectez-vous pour reprendre là où vous en étiez.
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Email ou nom d&apos;utilisateur (ex. prenom.nom), puis votre mot de passe.
            </p>
            <div className="grid gap-2">
              <Label htmlFor="login-username">Email ou nom d&apos;utilisateur</Label>
              <Input
                id="login-username"
                name="username"
                type="text"
                inputMode="email"
                autoComplete="username"
                placeholder="prenom.nom ou email@example.com"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="login-password">Mot de passe</Label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                  Mot de passe oublié ?
                </Link>
              </div>
              <Input
                id="login-password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Se connecter
            </Button>
          </form>
          <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            ou
            <span className="h-px flex-1 bg-border" />
          </div>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              setModeLien(true);
              setError('');
            }}
          >
            Recevoir un lien de connexion par e-mail
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
