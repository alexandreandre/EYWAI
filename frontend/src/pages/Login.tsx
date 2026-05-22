// src/pages/Login.tsx (VERSION CORRIGÉE)

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate, useLocation, Link, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import apiClient from '@/api/apiClient';
import { Loader2 } from 'lucide-react';

export default function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get('session') === 'expired';

  const from = location.state?.from?.pathname || "/";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    console.log('\n' + '='.repeat(80));
    console.log('🔐 [FRONTEND LOGIN DEBUG] TENTATIVE DE CONNEXION');
    console.log('='.repeat(80));
    console.log('📥 [FRONTEND] Identifier saisi (brut):', `'${identifier}'`);
    console.log('📥 [FRONTEND] Type:', typeof identifier);
    console.log('📥 [FRONTEND] Longueur:', identifier.length);
    console.log('📥 [FRONTEND] Password longueur:', password.length);

    try {
      // On prépare les données au format 'form-urlencoded'
      const params = new URLSearchParams();
      params.append('username', identifier);
      params.append('password', password);

      console.log('📦 [FRONTEND] URLSearchParams créé:');
      console.log('   - username:', params.get('username'));
      console.log('   - password longueur:', params.get('password')?.length);
      console.log('📤 [FRONTEND] Envoi de la requête POST à /api/auth/login');

      // 1. On obtient le token
      const response = await apiClient.post('/api/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      console.log('✅ [FRONTEND] Réponse reçue:', response.status);
      console.log('🔑 [FRONTEND] Token reçu (30 premiers car.):', response.data.access_token?.substring(0, 30));
      console.log('👤 [FRONTEND] Utilisateur:', response.data.user);
      console.log('👑 [FRONTEND] Super admin:', response.data.user?.is_super_admin);

      // 2. Session complète (access + refresh) pour renouvellement silencieux
      await login({
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
        expires_in: response.data.expires_in,
        expires_at: response.data.expires_at,
      });

      console.log('✅ [FRONTEND] Login contexte terminé, redirection...');

      // 3. Redirection automatique pour les super admins
      if (response.data.user?.is_super_admin) {
        console.log('👑 [FRONTEND] Super admin détecté -> Redirection vers /super-admin');
        navigate('/super-admin', { replace: true });
      } else {
        console.log('👤 [FRONTEND] Utilisateur normal -> Redirection vers', from);
        navigate(from, { replace: true });
      }

      console.log('='.repeat(80) + '\n');

    } catch (err: any) {
      console.error('❌ [FRONTEND] ERREUR lors de la connexion:');
      console.error('   - Type:', err?.constructor?.name);
      console.error('   - Message:', err?.message);
      console.error('   - Response status:', err?.response?.status);
      console.error('   - Response data:', err?.response?.data);
      console.error('   - Stack:', err?.stack);
      console.log('='.repeat(80) + '\n');
      setError('Identifiant ou mot de passe incorrect.');
    } finally {
      setIsSubmitting(false);
    }
  };

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
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Se connecter
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}