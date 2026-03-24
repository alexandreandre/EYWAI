// frontend/src/api/scraping.ts
import apiClient from './apiClient';

export interface ScrapingSource {
  id: string;
  source_key: string;
  source_name: string;
  source_type: string;
  description?: string;
  target_table?: string;
  target_field?: string;
  primary_url?: string;
  alternative_urls?: any;
  available_scrapers?: string[];
  orchestrator_path?: string;
  requires_company_context: boolean;
  scraping_frequency: string;
  is_critical: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Stats enrichies
  last_job?: ScrapingJob;
  success_rate_30d?: number;
  unresolved_alerts_count?: number;
  jobs_history?: ScrapingJob[];
  schedules?: ScrapingSchedule[];
  recent_alerts?: ScrapingAlert[];
}

export interface ScrapingJob {
  id: string;
  source_id: string;
  job_type: string;
  scraper_used?: string;
  triggered_by?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  success?: boolean;
  data_extracted?: any;
  data_before?: any;
  data_after?: any;
  changes_detected?: any;
  execution_logs?: string[];
  error_message?: string;
  error_stack?: string;
  warnings?: string[];
  validation_results?: any;
  sources_agreement?: boolean;
  discrepancies?: any;
  created_at: string;
  scraping_sources?: {
    source_name: string;
    source_key: string;
  };
}

export interface ScrapingSchedule {
  id: string;
  source_id: string;
  schedule_type: string;
  cron_expression?: string;
  interval_days?: number;
  is_enabled: boolean;
  last_run_at?: string;
  last_run_job_id?: string;
  next_run_at?: string;
  notify_on_success: boolean;
  notify_on_failure: boolean;
  notification_emails?: string[];
  created_at: string;
  created_by?: string;
  updated_at: string;
  scraping_sources?: {
    source_name: string;
    source_key: string;
  };
}

export interface ScrapingAlert {
  id: string;
  job_id?: string;
  source_id: string;
  alert_type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string;
  details?: any;
  is_read: boolean;
  is_resolved: boolean;
  resolved_at?: string;
  resolved_by?: string;
  resolution_note?: string;
  created_at: string;
  scraping_sources?: {
    source_name: string;
    source_key: string;
  };
}

export interface ScrapingDashboardStats {
  stats: {
    total_sources: number;
    active_sources: number;
    critical_sources: number;
    total_jobs: number;
    jobs_last_24h: number;
    success_rate_last_30d: number;
    pending_alerts: number;
    active_schedules: number;
  };
  recent_jobs: ScrapingJob[];
  unread_alerts: ScrapingAlert[];
  critical_sources: ScrapingSource[];
}

export interface ExecuteScraperRequest {
  source_key: string;
  scraper_name?: string;
  use_orchestrator?: boolean;
}

export interface CreateScheduleRequest {
  source_id: string;
  schedule_type: 'cron' | 'interval';
  cron_expression?: string;
  interval_days?: number;
  notify_on_success?: boolean;
  notify_on_failure?: boolean;
  notification_emails?: string[];
}

export interface UpdateScheduleRequest {
  is_enabled?: boolean;
  cron_expression?: string;
  interval_days?: number;
  notify_on_success?: boolean;
  notify_on_failure?: boolean;
  notification_emails?: string[];
}

// =====================================================
// API DASHBOARD
// =====================================================

export async function getScrapingDashboard(): Promise<ScrapingDashboardStats> {
  const response = await apiClient.get('/api/scraping/dashboard');
  return response.data;
}

// =====================================================
// API SOURCES
// =====================================================

export async function listSources(params?: {
  source_type?: string;
  is_critical?: boolean;
  is_active?: boolean;
}): Promise<{ sources: ScrapingSource[]; total: number }> {
  const response = await apiClient.get('/api/scraping/sources', { params });
  return response.data;
}

export async function getSourceDetails(sourceId: string): Promise<ScrapingSource> {
  const response = await apiClient.get(`/api/scraping/sources/${sourceId}`);
  return response.data;
}

// =====================================================
// API EXÉCUTION
// =====================================================

export async function executeScraper(
  request: ExecuteScraperRequest
): Promise<{ message: string; source: string; source_key: string; job_id?: string }> {
  const response = await apiClient.post('/api/scraping/execute', request);
  return response.data;
}

// =====================================================
// API JOBS
// =====================================================

export async function getJobLogs(jobId: string): Promise<{
  job_id: string;
  status: string;
  logs: string[];
  success?: boolean;
  error_message?: string;
  completed_at?: string;
}> {
  const response = await apiClient.get(`/api/scraping/jobs/${jobId}/logs`);
  return response.data;
}

export async function listJobs(params?: {
  source_id?: string;
  status?: string;
  success?: boolean;
  limit?: number;
  offset?: number;
}): Promise<{ jobs: ScrapingJob[]; total: number }> {
  const response = await apiClient.get('/api/scraping/jobs', { params });
  return response.data;
}

export async function getJobDetails(jobId: string): Promise<ScrapingJob> {
  const response = await apiClient.get(`/api/scraping/jobs/${jobId}`);
  return response.data;
}

// =====================================================
// API SCHEDULES
// =====================================================

export async function listSchedules(params?: {
  is_enabled?: boolean;
}): Promise<{ schedules: ScrapingSchedule[]; total: number }> {
  const response = await apiClient.get('/api/scraping/schedules', { params });
  return response.data;
}

export async function createSchedule(
  schedule: CreateScheduleRequest
): Promise<{ success: boolean; schedule: ScrapingSchedule }> {
  const response = await apiClient.post('/api/scraping/schedules', schedule);
  return response.data;
}

export async function updateSchedule(
  scheduleId: string,
  update: UpdateScheduleRequest
): Promise<{ success: boolean; schedule: ScrapingSchedule }> {
  const response = await apiClient.patch(`/api/scraping/schedules/${scheduleId}`, update);
  return response.data;
}

export async function deleteSchedule(scheduleId: string): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete(`/api/scraping/schedules/${scheduleId}`);
  return response.data;
}

// =====================================================
// API ALERTES
// =====================================================

export async function listAlerts(params?: {
  is_read?: boolean;
  is_resolved?: boolean;
  severity?: string;
  limit?: number;
}): Promise<{ alerts: ScrapingAlert[]; total: number }> {
  const response = await apiClient.get('/api/scraping/alerts', { params });
  return response.data;
}

export async function markAlertAsRead(alertId: string): Promise<{ success: boolean }> {
  const response = await apiClient.patch(`/api/scraping/alerts/${alertId}/read`);
  return response.data;
}

export async function resolveAlert(
  alertId: string,
  resolutionNote?: string
): Promise<{ success: boolean }> {
  const response = await apiClient.patch(`/api/scraping/alerts/${alertId}/resolve`, {
    resolution_note: resolutionNote,
  });
  return response.data;
}
