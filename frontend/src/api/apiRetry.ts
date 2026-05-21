import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504]);
const MAX_RETRIES = 2;

export type RetryAxiosRequestConfig = InternalAxiosRequestConfig & {
  __retryCount?: number;
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function isIdempotentMethod(method: string | undefined): boolean {
  const m = (method ?? 'get').toLowerCase();
  return m === 'get' || m === 'head' || m === 'options';
}

export function shouldRetryRequest(error: AxiosError): boolean {
  const config = error.config as RetryAxiosRequestConfig | undefined;
  if (!config || !isIdempotentMethod(config.method)) return false;

  const retryCount = config.__retryCount ?? 0;
  if (retryCount >= MAX_RETRIES) return false;

  if (!error.response) return true;
  return RETRYABLE_STATUSES.has(error.response.status);
}

export async function retryAxiosRequest<T>(
  request: (config: RetryAxiosRequestConfig) => Promise<T>,
  config: RetryAxiosRequestConfig,
): Promise<T> {
  const retryCount = (config.__retryCount ?? 0) + 1;
  const next: RetryAxiosRequestConfig = {
    ...config,
    __retryCount: retryCount,
  };
  await sleep(350 * retryCount);
  return request(next);
}
