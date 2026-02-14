const runtimeApiUrl =
  typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:5000';

export const API_URL = import.meta.env.VITE_API_URL || runtimeApiUrl;
const API_PREFIX = '/api/v1';

export const ENDPOINTS = {
  HEALTH: '/health',
  AUTH_REGISTER: '/auth/register',
  AUTH_LOGIN: '/auth/login',
  AUTH_ME: '/auth/me',
  AUTH_REFRESH: '/auth/refresh',
  AUTH_LOGOUT: '/auth/logout',
  HISTORY: '/history',
  PROCESS_ARRAY: '/process-array',
  PROCESS_CSV: '/process-csv',
  DOWNLOAD_VIDEO: '/download-video',
  DOWNLOAD_AUDIO: '/download-audio',
  GENERATE_AI: '/generate-ai',
  MIX_SESSIONS: '/mix-sessions',
  MIX_SESSION_PLAN: '/mix-sessions/plan',
  MIX_CHATS: '/mix-chats',
  MIX_CHAT_RUNS: '/mix-chat-runs',
};

export function getMixChatVersionEditRunsEndpoint(threadId: string, versionId: string): string {
  return `${ENDPOINTS.MIX_CHATS}/${threadId}/versions/${versionId}/edit-runs`;
}

export function getMixChatPlanDraftEndpoint(threadId: string, draftId: string): string {
  return `${ENDPOINTS.MIX_CHATS}/${threadId}/plan-drafts/${draftId}`;
}

export function getMixChatRunEventsUrl(runId: string): string {
  const endpoint = `${ENDPOINTS.MIX_CHAT_RUNS}/${runId}/events`;
  const base =
    typeof window !== 'undefined' ? window.location.origin : API_URL;
  const url = new URL(getApiEndpoint(endpoint), base);
  const token = getAccessToken();
  if (token) {
    url.searchParams.set('token', token);
  }
  return url.toString();
}

const ACCESS_TOKEN_KEY = 'intellimix.access_token';
const REFRESH_TOKEN_KEY = 'intellimix.refresh_token';

export interface ApiRequestConfig {
  auth?: boolean;
  retryOnUnauthorized?: boolean;
}

export class ApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export function getApiEndpoint(path: string): string {
  return `${API_URL}${API_PREFIX}${path}`;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setAuthTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearAuthTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function parseErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    const value = (payload as { error?: unknown }).error;
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }

  if (typeof payload === 'object' && payload !== null && 'message' in payload) {
    const value = (payload as { message?: unknown }).message;
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }

  return fallback;
}

function normalizeHeaders(initHeaders?: HeadersInit): Headers {
  const headers = new Headers(initHeaders);
  return headers;
}

export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  const response = await fetch(getApiEndpoint(ENDPOINTS.AUTH_REFRESH), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    clearAuthTokens();
    return null;
  }

  const payload = (await response.json()) as { access_token?: string };
  if (!payload.access_token) {
    clearAuthTokens();
    return null;
  }

  localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  return payload.access_token;
}

export async function apiRequest<T>(
  endpoint: string,
  init: RequestInit = {},
  config: ApiRequestConfig = {}
): Promise<T> {
  const auth = config.auth ?? true;
  const retryOnUnauthorized = config.retryOnUnauthorized ?? true;

  const headers = normalizeHeaders(init.headers);
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData;

  if (!isFormData && init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (auth) {
    const accessToken = getAccessToken();
    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`);
    }
  }

  const response = await fetch(getApiEndpoint(endpoint), {
    ...init,
    headers,
  });

  if (response.status === 401 && auth && retryOnUnauthorized) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      const retryHeaders = normalizeHeaders(init.headers);
      if (!isFormData && init.body && !retryHeaders.has('Content-Type')) {
        retryHeaders.set('Content-Type', 'application/json');
      }
      retryHeaders.set('Authorization', `Bearer ${newToken}`);

      const retryResponse = await fetch(getApiEndpoint(endpoint), {
        ...init,
        headers: retryHeaders,
      });

      if (!retryResponse.ok) {
        let retryPayload: unknown = null;
        try {
          retryPayload = await retryResponse.json();
        } catch {
          retryPayload = null;
        }

        throw new ApiError(
          parseErrorMessage(retryPayload, `Request failed with status ${retryResponse.status}`),
          retryResponse.status,
          retryPayload
        );
      }

      if (retryResponse.status === 204) {
        return undefined as T;
      }
      return (await retryResponse.json()) as T;
    }
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    throw new ApiError(parseErrorMessage(payload, `Request failed with status ${response.status}`), response.status, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getAuthenticatedFileUrl(rawUrl: string): string {
  if (!rawUrl) {
    return rawUrl;
  }

  const token = getAccessToken();
  const apiBase = new URL(API_URL, window.location.origin);
  const filesBase = `${apiBase.protocol}//${apiBase.host}`;
  let url = new URL(rawUrl, filesBase);

  // Force all generated file paths to resolve against backend host.
  // This avoids legacy/wrong-host absolute URLs (e.g. localhost without backend port).
  if (url.pathname.startsWith('/files/')) {
    url = new URL(`${url.pathname}${url.search}`, filesBase);
  }

  if (token) {
    url.searchParams.set('token', token);
  }

  return url.toString();
}
