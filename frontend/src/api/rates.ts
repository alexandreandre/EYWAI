import apiClient from '@/api/apiClient';

export type RateCategory = {
  config_data: Record<string, unknown>;
  version: number;
  last_checked_at: string | null;
  comment: string | null;
  source_links: string[] | null;
};

export type RatesResponse = Record<string, RateCategory>;

export type RatesSyncSourceUnit = {
  source_key: string;
  source_name: string;
  /** URL canonique de la source (scraping_sources.primary_url) */
  primary_url?: string | null;
  is_running: boolean;
  /** Présent lorsque is_running — permet de reprendre le suivi après rechargement */
  sync_id?: string | null;
};

export type RatesSyncCotisationUnit = {
  cotisation_id: string;
  sources: RatesSyncSourceUnit[];
};

export type RatesSyncRateCategory = {
  rate_key: string;
  sources: RatesSyncSourceUnit[];
  cotisation_units?: RatesSyncCotisationUnit[];
};

export type RatesSyncSourcesManifest = {
  rate_categories: RatesSyncRateCategory[];
  all_critical_count: number;
};

export type RatesSyncRequest = {
  rate_keys?: string[];
  source_keys?: string[];
  cotisation_ids?: string[];
};

export type RatesSyncJob = {
  source_key: string;
  source_name: string;
  job_id: string | null;
  status: string;
  success?: boolean | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  execution_logs?: string[];
  progress_fraction?: number;
  current_step?: string;
  last_log_line?: string;
  rate_keys?: string[];
  cotisation_ids?: string[];
};

export type RatesSyncStartResponse = {
  sync_id: string;
  jobs: RatesSyncJob[];
  total: number;
  message: string;
};

export type RatesSyncStatusResponse = {
  sync_id: string;
  status: 'running' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled';
  progress: {
    total: number;
    completed: number;
    failed: number;
    running: number;
    pending?: number;
    done: number;
    percent: number;
    percent_exact?: number;
    current_source?: string | null;
    current_step?: string;
    eta_seconds?: number | null;
    avg_job_duration_sec?: number;
  };
  jobs: RatesSyncJob[];
  created_at: string;
  target?: RatesSyncRequest;
};

export async function fetchAllRates(): Promise<RatesResponse> {
  const res = await apiClient.get<RatesResponse>('/api/rates/all');
  return res.data;
}

export async function fetchRatesSyncSources(): Promise<RatesSyncSourcesManifest> {
  const res = await apiClient.get<RatesSyncSourcesManifest>('/api/rates/sync/sources');
  return res.data;
}

export async function startRatesSync(
  request: RatesSyncRequest = {},
): Promise<RatesSyncStartResponse> {
  const res = await apiClient.post<RatesSyncStartResponse>('/api/rates/sync', request);
  return res.data;
}

export async function getRatesSyncStatus(syncId: string): Promise<RatesSyncStatusResponse> {
  const res = await apiClient.get<RatesSyncStatusResponse>(`/api/rates/sync/${syncId}/status`);
  return res.data;
}

export async function cancelRatesSync(syncId: string): Promise<RatesSyncStatusResponse> {
  const res = await apiClient.post<RatesSyncStatusResponse>(`/api/rates/sync/${syncId}/cancel`);
  return res.data;
}
