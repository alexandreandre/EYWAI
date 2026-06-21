import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileSpreadsheet } from 'lucide-react';
import {
  getIjssImportProfiles,
  updateIjssImportProfile,
  type IjssImportProfile,
} from '@/api/ijssTracking';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';

const BATCH_LABELS: Record<string, string> = {
  bank_recap: 'Relevé banque (virements CPAM)',
  cpam_decompte_file: 'Fichier décompte CPAM',
};

function mappingToText(mapping: Record<string, unknown>): string {
  try {
    return JSON.stringify(mapping, null, 2);
  } catch {
    return '{}';
  }
}

export default function IjssImportProfileCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['ijss-import-profiles', activeCompanyId],
    queryFn: getIjssImportProfiles,
    enabled: Boolean(activeCompanyId),
  });

  const [bankText, setBankText] = useState('{}');
  const [cpamText, setCpamText] = useState('{}');

  useEffect(() => {
    const bank = profiles.find((p) => p.batch_type === 'bank_recap');
    const cpam = profiles.find((p) => p.batch_type === 'cpam_decompte_file');
    setBankText(mappingToText(bank?.column_mapping ?? {}));
    setCpamText(mappingToText(cpam?.column_mapping ?? {}));
  }, [profiles]);

  const saveBank = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(bankText) as Record<string, string>;
      return updateIjssImportProfile('bank_recap', parsed);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ijss-import-profiles', activeCompanyId] });
      toast({ title: 'Profil banque enregistré' });
    },
    onError: () => {
      toast({ title: 'JSON invalide ou erreur serveur', variant: 'destructive' });
    },
  });

  const saveCpam = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(cpamText) as Record<string, string>;
      return updateIjssImportProfile('cpam_decompte_file', parsed);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ijss-import-profiles', activeCompanyId] });
      toast({ title: 'Profil CPAM enregistré' });
    },
    onError: () => {
      toast({ title: 'JSON invalide ou erreur serveur', variant: 'destructive' });
    },
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-muted-foreground">Chargement…</CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileSpreadsheet className="h-4 w-4" />
          Profils import IJSS
        </CardTitle>
        <CardDescription>
          Mapping colonnes pour les imports récurrents (Suivi IJSS). JSON : clé champ métier → nom colonne fichier.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-2">
          <Label>{BATCH_LABELS.bank_recap}</Label>
          <Textarea
            rows={8}
            className="font-mono text-xs"
            value={bankText}
            disabled={!canEdit}
            onChange={(e) => setBankText(e.target.value)}
          />
          {canEdit && (
            <Button
              size="sm"
              disabled={saveBank.isPending}
              onClick={() => saveBank.mutate()}
            >
              Enregistrer banque
            </Button>
          )}
        </div>
        <div className="space-y-2">
          <Label>{BATCH_LABELS.cpam_decompte_file}</Label>
          <Textarea
            rows={8}
            className="font-mono text-xs"
            value={cpamText}
            disabled={!canEdit}
            onChange={(e) => setCpamText(e.target.value)}
          />
          {canEdit && (
            <Button
              size="sm"
              disabled={saveCpam.isPending}
              onClick={() => saveCpam.mutate()}
            >
              Enregistrer CPAM
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
