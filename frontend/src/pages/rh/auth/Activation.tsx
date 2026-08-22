// src/pages/rh/auth/Activation.tsx
// Page PUBLIQUE d'activation de compte salarié : le lien reçu par e-mail
// porte ?token=… ; on vérifie le jeton, la personne choisit son mot de
// passe, puis on la renvoie vers la connexion. Toute erreur de jeton
// affiche le même message générique.

import { log } from '@/lib/logger';
import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  completeActivation,
  verifyActivationToken,
  type ActivationVerifyResult,
} from '@/api/activation';
import {
  getPasswordChecks,
  getPasswordStrength,
  isPasswordAcceptable,
} from '@/lib/activationUtils';
import { cn } from '@/lib/utils';
import { Loader2, CheckCircle2, AlertCircle, Eye, EyeOff } from 'lucide-react';

const GENERIC_LINK_ERROR =
  'Lien invalide ou expiré, demandez un nouveau lien à votre RH.';

const STRENGTH_LABELS = ['', 'Trop faible', 'Faible', 'Presque', 'Correct'];

function PasswordGauge({ password }: { password: string }) {
  const strength = getPasswordStrength(password);
  const checks = getPasswordChecks(password);
  return (
    <div className="space-y-2">
      <div className="flex gap-1" aria-hidden>
        {[1, 2, 3, 4].map((step) => (
          <div
            key={step}
            className={cn(
              'h-1.5 flex-1 rounded-full bg-muted',
              strength >= step &&
                (strength === 4 ? 'bg-green-500' : 'bg-amber-500'),
            )}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {password
          ? STRENGTH_LABELS[strength] || 'Trop faible'
          : 'Au moins 8 caractères, avec majuscule, minuscule et chiffre.'}
        {password && !checks.longueur ? ' — 8 caractères minimum' : null}
      </p>
    </div>
  );
}

export default function ActivationPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isValidating, setIsValidating] = useState(true);
  const [welcome, setWelcome] = useState<ActivationVerifyResult | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setIsValidating(false);
        return;
      }
      try {
        const result = await verifyActivationToken(token);
        setWelcome(result);
      } catch (err) {
        log.error('[ACTIVATION] Lien refusé:', err);
        setWelcome(null);
      } finally {
        setIsValidating(false);
      }
    };
    validateToken();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!isPasswordAcceptable(password)) {
      setError(
        'Le mot de passe doit contenir au moins 8 caractères, dont une majuscule, une minuscule et un chiffre.',
      );
      return;
    }
    if (password !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }

    setIsSubmitting(true);
    try {
      await completeActivation(token ?? '', password);
      setIsSuccess(true);
    } catch (err: unknown) {
      log.error('[ACTIVATION] Échec:', err);
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      if (typeof detail === 'object' && detail !== null && 'message' in detail) {
        setError(String((detail as { message?: unknown }).message ?? ''));
      } else {
        setError(GENERIC_LINK_ERROR);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isValidating) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center space-y-4">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                Vérification du lien...
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

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
            <CardTitle className="text-2xl text-center">
              Compte activé !
            </CardTitle>
            <CardDescription className="text-center">
              Votre espace EYWAI est prêt.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/login">
              <Button className="w-full">Se connecter</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!welcome) {
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
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive">
              <AlertDescription>{GENERIC_LINK_ERROR}</AlertDescription>
            </Alert>
            <p className="text-sm text-muted-foreground">
              Chaque lien d&apos;activation ne peut servir qu&apos;une fois et
              expire au bout de 7 jours. Votre service RH peut vous en envoyer
              un nouveau à tout moment.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl">Bonjour {welcome.prenom} !</CardTitle>
          <CardDescription>
            <strong>{welcome.societe}</strong> vous invite à activer votre
            espace EYWAI. Choisissez votre mot de passe pour terminer.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="password">Mot de passe</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Choisissez votre mot de passe"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isSubmitting}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={
                    showPassword
                      ? 'Masquer le mot de passe'
                      : 'Afficher le mot de passe'
                  }
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              <PasswordGauge password={password} />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="confirmPassword">Confirmez le mot de passe</Label>
              <Input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                placeholder="Confirmez votre mot de passe"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={isSubmitting}
              />
            </div>

            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <Button
              type="submit"
              className="w-full"
              disabled={
                isSubmitting ||
                !isPasswordAcceptable(password) ||
                password !== confirmPassword
              }
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Activation en cours...
                </>
              ) : (
                'Activer mon compte'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
