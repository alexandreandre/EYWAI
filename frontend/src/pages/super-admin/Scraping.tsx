// frontend/src/pages/super-admin/Scraping.tsx
import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Loader2, AlertTriangle, RefreshCw, CheckCircle2, XCircle, Clock,
  Play, Calendar, Bell, Database, TrendingUp, AlertCircle
} from 'lucide-react';
import apiClient from '@/api/apiClient';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  getScrapingDashboard,
  executeScraper,
  listSources,
  listJobs,
  listAlerts,
  markAlertAsRead,
  resolveAlert,
  getJobLogs,
  ScrapingSource,
  ScrapingJob,
  ScrapingAlert,
  ScrapingDashboardStats,
} from '@/api/scraping';

// Types pour les données scrapées
type RateCategory = {
  config_data: any;
  version: number;
  last_checked_at: string | null;
  comment: string | null;
  source_links: string[] | null;
};

type RatesResponse = Record<string, RateCategory>;

export default function ScrapingPage() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dashboardStats, setDashboardStats] = useState<ScrapingDashboardStats | null>(null);
  const [sources, setSources] = useState<ScrapingSource[]>([]);
  const [jobs, setJobs] = useState<ScrapingJob[]>([]);
  const [alerts, setAlerts] = useState<ScrapingAlert[]>([]);
  const [ratesData, setRatesData] = useState<RatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState<Record<string, boolean>>({});
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobLogs, setJobLogs] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [logPollingInterval, setLogPollingInterval] = useState<NodeJS.Timeout | null>(null);

  // Mapping entre source keys et rate keys
  const sourceToRateMapping: Record<string, string> = {
    'SMIC': 'smic',
    'PSS': 'pss',
    'AGIRC-ARRCO': 'cotisations',
    'PAS': 'pas',
    'FRAIS_PRO': 'frais_pro',
    'CSG': 'csg',
    'ALLOCATIONS_FAMILIALES': 'allocations_familiales',
    'FNAL': 'fnal',
    'ASSURANCE_CHOMAGE': 'assurance_chomage',
    'VIEILLESSE_PATRONAL': 'vieillesse_patronal',
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Refresh toutes les 10 secondes
    return () => {
      clearInterval(interval);
      stopLogPolling();
    };
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [dashData, sourcesData, jobsData, alertsData, ratesResp] = await Promise.all([
        getScrapingDashboard(),
        listSources({ is_active: true }),
        listJobs({ limit: 20 }),
        listAlerts({ is_read: false, limit: 10 }),
        apiClient.get<RatesResponse>('/api/rates/all'),
      ]);

      setDashboardStats(dashData);
      setSources(sourcesData.sources);
      setJobs(jobsData.jobs);
      setAlerts(alertsData.alerts);
      setRatesData(ratesResp.data);
    } catch (e: any) {
      console.error('Erreur lors du chargement des données:', e);
      setError(e.response?.data?.detail || e.message || 'Une erreur est survenue.');
    } finally {
      setLoading(false);
    }
  };

  const startLogPolling = (jobId: string) => {
    // Arrêter le polling précédent s'il existe
    if (logPollingInterval) {
      clearInterval(logPollingInterval);
    }

    // Démarrer le nouveau polling
    const interval = setInterval(async () => {
      try {
        const logsData = await getJobLogs(jobId);
        setJobLogs(logsData.logs || []);
        setJobStatus(logsData.status);

        // Arrêter le polling si le job est terminé
        if (logsData.status === 'completed' || logsData.status === 'failed') {
          clearInterval(interval);
          setLogPollingInterval(null);
          // Recharger les données après 2 secondes
          setTimeout(loadData, 2000);
        }
      } catch (error) {
        console.error('Erreur lors de la récupération des logs:', error);
      }
    }, 1000); // Polling toutes les secondes

    setLogPollingInterval(interval);
  };

  const stopLogPolling = () => {
    if (logPollingInterval) {
      clearInterval(logPollingInterval);
      setLogPollingInterval(null);
    }
  };

  const handleExecuteScraper = async (sourceKey: string) => {
    setExecuting(prev => ({ ...prev, [sourceKey]: true }));
    try {
      const source = sources.find(s => s.source_key === sourceKey);
      const response = await executeScraper({
        source_key: sourceKey,
        use_orchestrator: !!source?.orchestrator_path,
      });

      // Si un job_id est retourné, démarrer le suivi des logs
      if (response.job_id) {
        setActiveJobId(response.job_id);
        setJobLogs([]);
        setJobStatus('running');
        startLogPolling(response.job_id);
        // Ne pas réinitialiser executing ici car on affiche le dialog avec les logs
      } else {
        // Fallback si pas de job_id (ancienne version)
        alert(`✅ Scraping lancé pour "${source?.source_name}". Les données seront actualisées automatiquement.`);
        setTimeout(loadData, 5000);
      }
    } catch (error: any) {
      console.error('Erreur lors du lancement du scraping:', error);
      alert('❌ Erreur: ' + (error.response?.data?.detail || error.message));
    } finally {
      // Réinitialiser executing après un court délai pour laisser le temps au dialog de s'ouvrir
      setTimeout(() => {
        setExecuting(prev => ({ ...prev, [sourceKey]: false }));
      }, 500);
    }
  };

  const handleCloseLogs = () => {
    stopLogPolling();
    setActiveJobId(null);
    setJobLogs([]);
    setJobStatus(null);
  };

  const handleMarkAsRead = async (alertId: string) => {
    try {
      await markAlertAsRead(alertId);
      loadData();
    } catch (error: any) {
      console.error('Erreur:', error);
      alert('❌ Erreur: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleResolveAlert = async (alertId: string, note?: string) => {
    try {
      await resolveAlert(alertId, note);
      loadData();
    } catch (error: any) {
      console.error('Erreur:', error);
      alert('❌ Erreur: ' + (error.response?.data?.detail || error.message));
    }
  };

  const formatDate = (d?: string | null) => {
    if (!d) return 'Jamais';
    return new Date(d).toLocaleString('fr-FR', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '-';
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const renderJobStatus = (job: ScrapingJob) => {
    if (job.status === 'running') {
      return <Badge variant="outline" className="text-blue-600 border-blue-600"><Clock className="w-3 h-3 mr-1" />En cours</Badge>;
    }
    if (job.success) {
      return <Badge variant="outline" className="text-green-600 border-green-600"><CheckCircle2 className="w-3 h-3 mr-1" />Succès</Badge>;
    }
    return <Badge variant="outline" className="text-red-600 border-red-600"><XCircle className="w-3 h-3 mr-1" />Échec</Badge>;
  };

  const renderSeverityBadge = (severity: string) => {
    const colors = {
      info: 'bg-blue-100 text-blue-800',
      warning: 'bg-yellow-100 text-yellow-800',
      error: 'bg-red-100 text-red-800',
      critical: 'bg-purple-100 text-purple-800',
    };
    return <Badge className={colors[severity as keyof typeof colors] || ''}>{severity}</Badge>;
  };

  // Fonction pour obtenir les données d'une source
  const getSourceData = (sourceKey: string): any => {
    const rateKey = sourceToRateMapping[sourceKey];
    if (!rateKey || !ratesData) return null;
    return ratesData[rateKey];
  };

  // Fonction pour formater les données scrapées de manière compacte
  const renderDataPreview = (data: any): string => {
    if (!data || !data.config_data) return 'Aucune donnée';

    const config = data.config_data;

    // SMIC
    if (config.smic_horaire) {
      return `SMIC: ${config.smic_horaire.smic_horaire_2025 || config.smic_horaire.smic_horaire} €/h`;
    }

    // PSS
    if (config.pss) {
      return `PSS: ${config.pss.annuel_2025 || config.pss.annuel} €`;
    }

    // Cotisations
    if (config.cotisations && Array.isArray(config.cotisations)) {
      return `${config.cotisations.length} cotisations`;
    }

    // PAS
    if (config.baremes && Array.isArray(config.baremes)) {
      return `${config.baremes.length} barèmes`;
    }

    return 'Données disponibles';
  };

  if (loading && !dashboardStats) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">Chargement du système de scraping...</span>
      </div>
    );
  }

  if (error && !dashboardStats) {
    return (
      <Card className="border-red-500/50 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center text-red-600">
            <AlertTriangle className="mr-2 h-5 w-5" />
            Erreur de chargement
          </CardTitle>
        </CardHeader>
        <CardContent className="text-red-500">
          <p>{error}</p>
          <Button onClick={loadData} className="mt-4">
            <RefreshCw className="mr-2 h-4 w-4" />
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Système de Scraping</h1>
          <p className="text-muted-foreground mt-1">
            Gestion et pilotage du scraping des données de paie
          </p>
        </div>
        <Button onClick={loadData} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Actualiser
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="dashboard">
            <TrendingUp className="h-4 w-4 mr-2" />
            Dashboard
          </TabsTrigger>
          <TabsTrigger value="sources">
            <Database className="h-4 w-4 mr-2" />
            Sources ({sources.length})
          </TabsTrigger>
          <TabsTrigger value="jobs">
            <Play className="h-4 w-4 mr-2" />
            Jobs ({jobs.length})
          </TabsTrigger>
          <TabsTrigger value="alerts">
            <Bell className="h-4 w-4 mr-2" />
            Alertes ({alerts.filter(a => !a.is_read).length})
          </TabsTrigger>
        </TabsList>

        {/* ONGLET DASHBOARD */}
        <TabsContent value="dashboard" className="space-y-6">
          {dashboardStats && (
            <>
              {/* Stats Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Sources actives</CardDescription>
                    <CardTitle className="text-3xl">{dashboardStats.stats.active_sources}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-muted-foreground">
                      Sur {dashboardStats.stats.total_sources} sources
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Jobs (24h)</CardDescription>
                    <CardTitle className="text-3xl">{dashboardStats.stats.jobs_last_24h}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-muted-foreground">
                      Total: {dashboardStats.stats.total_jobs}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Taux de succès (30j)</CardDescription>
                    <CardTitle className="text-3xl">
                      {dashboardStats.stats.success_rate_last_30d?.toFixed(0) || 0}%
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-muted-foreground">Derniers 30 jours</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Alertes non résolues</CardDescription>
                    <CardTitle className="text-3xl">{dashboardStats.stats.pending_alerts}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-muted-foreground">À traiter</p>
                  </CardContent>
                </Card>
              </div>

              {/* Jobs récents */}
              <Card>
                <CardHeader>
                  <CardTitle>Jobs récents</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Source</TableHead>
                        <TableHead>Statut</TableHead>
                        <TableHead>Début</TableHead>
                        <TableHead>Durée</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dashboardStats.recent_jobs.slice(0, 5).map((job) => (
                        <TableRow key={job.id}>
                          <TableCell className="font-medium">
                            {job.scraping_sources?.source_name || job.source_id}
                          </TableCell>
                          <TableCell>{renderJobStatus(job)}</TableCell>
                          <TableCell className="text-sm">{formatDate(job.created_at)}</TableCell>
                          <TableCell className="text-sm">{formatDuration(job.duration_ms)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* ONGLET SOURCES */}
        <TabsContent value="sources" className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {sources.map((source) => {
              const isExecuting = executing[source.source_key];
              const lastJob = jobs.find(j => j.source_id === source.id);
              const sourceData = getSourceData(source.source_key);

              return (
                <Card key={source.id} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <CardTitle className="text-xl">{source.source_name}</CardTitle>
                          {source.is_critical && (
                            <Badge variant="destructive">Critique</Badge>
                          )}
                          {lastJob && renderJobStatus(lastJob)}
                        </div>
                        <CardDescription className="mt-1">
                          {source.description || source.source_key}
                        </CardDescription>

                        {/* Affichage des données scrapées */}
                        {sourceData && (
                          <div className="mt-3 p-3 bg-muted rounded-md">
                            <p className="text-sm font-medium text-muted-foreground mb-1">
                              Dernières données:
                            </p>
                            <p className="text-sm">
                              {renderDataPreview(sourceData)}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              Contrôlé le: {formatDate(sourceData.last_checked_at)}
                            </p>
                          </div>
                        )}

                        {lastJob && lastJob.completed_at && (
                          <p className="text-xs text-muted-foreground mt-2">
                            Dernier scraping: {formatDate(lastJob.completed_at)}
                          </p>
                        )}
                      </div>

                      <Button
                        onClick={() => handleExecuteScraper(source.source_key)}
                        disabled={isExecuting}
                        variant="default"
                      >
                        {isExecuting ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            En cours...
                          </>
                        ) : (
                          <>
                            <Play className="mr-2 h-4 w-4" />
                            Exécuter
                          </>
                        )}
                      </Button>
                    </div>
                  </CardHeader>

                  {lastJob && lastJob.error_message && (
                    <CardContent>
                      <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                        <p className="text-sm font-medium text-red-800 flex items-center">
                          <AlertCircle className="h-4 w-4 mr-2" />
                          Erreur
                        </p>
                        <p className="text-xs text-red-700 mt-1">{lastJob.error_message}</p>
                      </div>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* ONGLET JOBS */}
        <TabsContent value="jobs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Historique des jobs</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Début</TableHead>
                    <TableHead>Fin</TableHead>
                    <TableHead>Durée</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="font-medium">
                        {job.scraping_sources?.source_name || job.source_id}
                      </TableCell>
                      <TableCell>{job.job_type}</TableCell>
                      <TableCell>{renderJobStatus(job)}</TableCell>
                      <TableCell className="text-sm">{formatDate(job.created_at)}</TableCell>
                      <TableCell className="text-sm">{formatDate(job.completed_at)}</TableCell>
                      <TableCell className="text-sm">{formatDuration(job.duration_ms)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ONGLET ALERTES */}
        <TabsContent value="alerts" className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {alerts.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Aucune alerte non lue</p>
                </CardContent>
              </Card>
            ) : (
              alerts.map((alert) => (
                <Card key={alert.id} className={alert.is_read ? 'opacity-60' : ''}>
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {renderSeverityBadge(alert.severity)}
                          <span className="text-sm text-muted-foreground">
                            {formatDate(alert.created_at)}
                          </span>
                        </div>
                        <CardTitle className="text-lg">{alert.title}</CardTitle>
                        <CardDescription className="mt-1">{alert.message}</CardDescription>
                        {alert.scraping_sources && (
                          <p className="text-sm text-muted-foreground mt-2">
                            Source: {alert.scraping_sources.source_name}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {!alert.is_read && (
                          <Button
                            onClick={() => handleMarkAsRead(alert.id)}
                            variant="outline"
                            size="sm"
                          >
                            Marquer lu
                          </Button>
                        )}
                        {!alert.is_resolved && (
                          <Button
                            onClick={() => handleResolveAlert(alert.id)}
                            variant="default"
                            size="sm"
                          >
                            Résoudre
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Dialog pour afficher les logs en temps réel */}
      <Dialog open={!!activeJobId} onOpenChange={(open) => !open && handleCloseLogs()}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {jobStatus === 'running' && <Loader2 className="h-5 w-5 animate-spin text-blue-600" />}
              {jobStatus === 'completed' && <CheckCircle2 className="h-5 w-5 text-green-600" />}
              {jobStatus === 'failed' && <XCircle className="h-5 w-5 text-red-600" />}
              Logs du scraping
            </DialogTitle>
            <DialogDescription>
              {jobStatus === 'running' && 'Le scraping est en cours...'}
              {jobStatus === 'completed' && 'Le scraping s\'est terminé avec succès'}
              {jobStatus === 'failed' && 'Le scraping a échoué'}
            </DialogDescription>
          </DialogHeader>
          <div className="h-[60vh] w-full rounded-md border overflow-auto p-4 font-mono text-sm bg-slate-950 text-slate-100">
            {jobLogs.length === 0 ? (
              <div className="text-muted-foreground">En attente des logs...</div>
            ) : (
              <>
                {jobLogs.map((log, index) => {
                  const isError = log.includes('[ERREUR]') || log.includes('ERROR') || log.includes('CRITICAL');
                  const isWarning = log.includes('[WARNING]') || log.includes('WARNING');
                  const isSuccess = log.includes('[SUCCÈS]') || log.includes('SUCCESS');
                  const isInfo = log.includes('[INFO]') || log.includes('INFO');

                  let className = 'text-slate-100';
                  if (isError) className = 'text-red-400';
                  else if (isWarning) className = 'text-yellow-400';
                  else if (isSuccess) className = 'text-green-400';
                  else if (isInfo) className = 'text-blue-400';

                  return (
                    <div key={index} className={className} ref={(el) => {
                      // Auto-scroll vers le bas lorsque de nouveaux logs arrivent
                      if (index === jobLogs.length - 1 && el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                      }
                    }}>
                      {log || '\u00A0'}
                    </div>
                  );
                })}
                {jobStatus === 'running' && (
                  <div className="flex items-center gap-2 text-slate-400 mt-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>En cours...</span>
                  </div>
                )}
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
