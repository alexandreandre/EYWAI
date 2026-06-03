import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ExternalLink, Wrench } from 'lucide-react';

import { ScrapingRepairJob } from '@/api/scraping';

type RepairAgentTabProps = {
  jobs: ScrapingRepairJob[];
  activeCount: number;
};

const STATUS_LABELS: Record<string, string> = {
  queued: 'En file',
  running: 'En cours',
  tests_failed: 'Tests KO',
  tests_passed: 'Tests OK',
  merged: 'Fusionné',
  aborted: 'Abandonné',
};

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'merged' || status === 'tests_passed') return 'default';
  if (status === 'running' || status === 'queued') return 'secondary';
  if (status === 'tests_failed' || status === 'aborted') return 'destructive';
  return 'outline';
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString('fr-FR');
}

export function RepairAgentTab({ jobs, activeCount }: RepairAgentTabProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5" />
            Agent réparation autonome
          </CardTitle>
          <CardDescription>
            Réparation automatique du code scraping (parsers, URLs, fixtures). Les changements de
            taux restent soumis à validation humaine. Sources officielles vérifiées chaque mois.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            {activeCount > 0
              ? `${activeCount} job(s) actif(s) (file ou exécution).`
              : 'Aucun job actif.'}
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scraper</TableHead>
                <TableHead>Déclencheur</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Tentatives</TableHead>
                <TableHead>Créé</TableHead>
                <TableHead>PR</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    Aucun job de réparation.
                  </TableCell>
                </TableRow>
              ) : (
                jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-medium">{job.scraper_name}</TableCell>
                    <TableCell className="text-xs">{job.trigger}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(job.status)}>
                        {STATUS_LABELS[job.status] ?? job.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{job.attempts}</TableCell>
                    <TableCell className="text-xs">{formatDate(job.created_at)}</TableCell>
                    <TableCell>
                      {job.pr_url ? (
                        <a
                          href={job.pr_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <ExternalLink className="h-3 w-3" />
                          PR
                        </a>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
