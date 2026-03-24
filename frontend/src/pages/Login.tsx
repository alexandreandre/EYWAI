// src/pages/Login.tsx (VERSION CORRIGÉE)

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate, useLocation, Link } from 'react-router-dom';
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

      // 2. On passe le token à la fonction login du contexte, qui s'occupe du reste
      await login(response.data.access_token);

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
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="identifier">Email ou Nom d'utilisateur</Label>
              <Input
                id="identifier"
                type="text"
                placeholder="prenom.nom ou email@example.com"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                Vous pouvez vous connecter avec votre email ou votre nom d'utilisateur (prenom.nom)
              </p>
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Mot de passe</Label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                  Mot de passe oublié ?
                </Link>
              </div>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
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