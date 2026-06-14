/**
 * Centralized HTTP client for the Just enough AI API. Every endpoint
 * module (scenarios, runners, runs) builds on `apiGet` / `apiPost` so
 * base URL, error handling, and logging stay in one place.
 */

import { logger } from '../lib/logger';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const method = init?.method ?? 'GET';
  const start = performance.now();

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    });
  } catch (err) {
    logger.error('API request network error', { method, url, error: String(err) });
    throw new ApiError('Network error — is the backend running?', 0);
  }

  const durationMs = Math.round(performance.now() - start);
  const requestId = response.headers.get('X-Request-ID') ?? undefined;

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail;
    } catch {
      // error body wasn't JSON — fall back to statusText below
    }
    logger.warn('API request failed', {
      method,
      url,
      status: response.status,
      durationMs,
      requestId,
      detail,
    });
    throw new ApiError(detail ?? response.statusText, response.status, detail);
  }

  logger.debug('API request succeeded', { method, url, status: response.status, durationMs, requestId });

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const apiGet = <T>(path: string): Promise<T> => request<T>(path);

export const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

export const apiDelete = <T>(path: string): Promise<T> =>
  request<T>(path, {
    method: 'DELETE',
  });
