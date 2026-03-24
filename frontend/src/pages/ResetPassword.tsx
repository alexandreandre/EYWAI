// src/pages/ResetPassword.tsx

import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import apiClient from '@/api/apiClient';
import { Loader2, CheckCircle2, AlertCircle, Eye, EyeOff } from 'lucide-react';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isValidating, setIsValidating] = useState(true);
  const [isValidToken, setIsValidToken] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');

  // Valider le token au chargement de la page
  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setError('Token manquant. Le lien est invalide.');
        setIsValidating(false);
        return;
      }

      try {
        console.log('🔍 [RESET PASSWORD] Validation du token...');
        const response = await apiClient.post('/api/auth/verify-reset-token', null, {
          params: { token }
        });

        console.log('✅ [RESET PASSWORD] Token valide');
        setIsValidToken(true);
        setEmail(response.data.email);
      } catch (err: any) {
        console.error('❌ [RESET PASSWORD] Token invalide:', err);
        const message = err.response?.data?.detail || 'Le lien de réinitialisation est invalide ou a expiré.';
        setError(message);
        setIsValidToken(false);
      } finally {
        setIsValidating(false);
      }
    };

    validateToken();
  }, [token]);

  const validatePassword = (password: string): string | null => {
    if (password.length < 8) {
      return 'Le mot de passe doit contenir au moins 8 caractères';
    }
    if (!/[A-Z]/.test(password)) {
      return 'Le mot de passe doit contenir au moins une majuscule';
    }
    if (!/[a-z]/.test(password)) {
      return 'Le mot de passe doit contenir au moins une minuscule';
    }
    if (!/[0-9]/.test(password)) {
      return 'Le mot de passe doit contenir au moins un chiffre';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation des mots de passe
    const passwordError = validatePassword(newPassword);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }

    setIsSubmitting(true);

    try {
      console.log('🔐 [RESET PASSWORD] Réinitialisation du mot de passe...');

      await apiClient.post('/api/auth/reset-password', {
        token,
        new_password: newPassword
      });

      console.log('✅ [RESET PASSWORD] Mot de passe réinitialisé avec succès');
      setIsSuccess(true);

      // Rediriger vers la page de connexion après 3 secondes
      setTimeout(() => {
        navigate('/login');
      }, 3000);

    } catch (err: any) {
      console.error('❌ [RESET PASSWORD] Erreur:', err);
      const message = err.response?.data?.detail || 'Une erreur est survenue. Veuillez réessayer.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Écran de chargement pendant la validation du token
  if (isValidating) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center space-y-4">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">Vérification du lien...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Écran de succès
  if (isSuccess) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-green-100 p-3">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <CardTitle className="text-2xl text-center">Mot de passe réinitialisé !</CardTitle>
            <CardDescription className="text-center">
              Votre mot de passe a été mis à jour avec succès
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertDescription>
                Vous allez être redirigé vers la page de connexion...
              </AlertDescription>
            </Alert>
            <div className="mt-4">
              <Link to="/login">
                <Button className="w-full">
                  Se connecter maintenant
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Écran d'erreur si le token n'est pas valide
  if (!isValidToken) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-red-100 p-3">
                <AlertCircle className="h-8 w-8 text-red-600" />
              </div>
            </div>
            <CardTitle className="text-2xl text-center">Lien invalide</CardTitle>
            <CardDescription className="text-center">
              Ce lien de réinitialisation n'est plus valide
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>

            <div className="space-y-2 text-sm text-muted-foreground">
              <p>Le lien peut être invalide pour les raisons suivantes :</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Le lien a expiré (validité : 1 heure)</li>
                <li>Le lien a déjà été utilisé</li>
                <li>Le lien est mal formé</li>
              </ul>
            </div>

            <div className="space-y-2">
              <Link to="/forgot-password">
                <Button className="w-full">
                  Demander un nouveau lien
                </Button>
              </Link>
              <Link to="/login">
                <Button variant="outline" className="w-full">
                  Retour à la connexion
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Formulaire de réinitialisation
  return (
    <div className="flex items-center justify-center min-h-screen bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl">Nouveau mot de passe</CardTitle>
          <CardDescription>
            Créez un nouveau mot de passe pour votre compte <strong>{email}</strong>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="newPassword">Nouveau mot de passe</Label>
              <div className="relative">
                <Input
                  id="newPassword"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Entrez votre nouveau mot de passe"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  disabled={isSubmitting}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="confirmPassword">Confirmer le mot de passe</Label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Confirmez votre nouveau mot de passe"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="text-xs text-muted-foreground space-y-1">
              <p className="font-medium">Le mot de passe doit contenir :</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Au moins 8 caractères</li>
                <li>Une majuscule</li>
                <li>Une minuscule</li>
                <li>Un chiffre</li>
              </ul>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Réinitialiser le mot de passe
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
