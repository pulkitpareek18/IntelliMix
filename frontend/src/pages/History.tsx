import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ENDPOINTS, apiRequest, getAuthenticatedFileUrl } from '../utils/api';

interface GenerationHistoryItem {
  id: string;
  generation_type: 'ai_parody' | 'audio_mix' | 'video_download' | 'audio_download' | string;
  status: 'success' | 'failed' | 'processing' | string;
  input_payload: Record<string, unknown>;
  output_url: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

interface HistoryResponse {
  items: GenerationHistoryItem[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

const colors = {
  deepRed: '#d24d34',
  softRed: '#fee2e1',
  textDark: '#444444',
  success: '#1b8354',
  warning: '#7a5d1e',
  error: '#b42318',
};

const TYPE_LABELS: Record<string, string> = {
  ai_parody: 'AI Music Studio',
  audio_mix: 'Audio Mixer',
  video_download: 'Video Download',
  audio_download: 'Audio Download',
};

function summarizeInput(item: GenerationHistoryItem): string {
  if (item.generation_type === 'ai_parody') {
    const prompt = item.input_payload?.prompt;
    return typeof prompt === 'string' ? prompt : 'AI generation request';
  }

  if (item.generation_type === 'audio_mix') {
    if (typeof item.input_payload?.filename === 'string') {
      return `CSV: ${item.input_payload.filename}`;
    }

    const urls = item.input_payload?.urls;
    if (Array.isArray(urls)) {
      return `${urls.length} clip(s) requested`;
    }

    return 'Audio mix request';
  }

  const url = item.input_payload?.url;
  if (typeof url === 'string' && url) {
    return url;
  }

  return 'Request submitted';
}

export default function HistoryPage() {
  const [items, setItems] = useState<GenerationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const query = new URLSearchParams({ limit: '50' });
      if (filter !== 'all') {
        query.set('type', filter);
      }

      const response = await apiRequest<HistoryResponse>(`${ENDPOINTS.HISTORY}?${query.toString()}`, {
        method: 'GET',
      });

      setItems(response.items);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load history';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const filteredItems = useMemo(() => items, [items]);

  const handleDelete = async (jobId: string) => {
    try {
      await apiRequest<{ message: string }>(`${ENDPOINTS.HISTORY}/${jobId}`, {
        method: 'DELETE',
      });
      setItems((current) => current.filter((item) => item.id !== jobId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      setError(message);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: colors.deepRed }}>
            Generation History
          </h1>
          <p className="text-sm" style={{ color: colors.textDark }}>
            Every generation for your account is stored and available here.
          </p>
        </div>

        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="rounded-lg border border-red-100 px-3 py-2 text-sm"
          style={{ color: colors.textDark }}
        >
          <option value="all">All</option>
          <option value="ai_parody">AI Music</option>
          <option value="audio_mix">Audio Mixer</option>
          <option value="video_download">Video Downloads</option>
          <option value="audio_download">Audio Downloads</option>
        </select>
      </div>

      {loading && <p style={{ color: colors.textDark }}>Loading history...</p>}

      {error && (
        <p className="rounded-md px-3 py-2 text-sm" style={{ backgroundColor: colors.softRed, color: colors.error }}>
          {error}
        </p>
      )}

      {!loading && filteredItems.length === 0 && (
        <div className="rounded-xl border border-red-100 bg-white p-6 text-sm" style={{ color: colors.textDark }}>
          No history yet. Start with AI Music Studio, Audio Mixer, or Downloader.
        </div>
      )}

      <div className="space-y-4">
        {filteredItems.map((item) => {
          const statusColor =
            item.status === 'success' ? colors.success : item.status === 'processing' ? colors.warning : colors.error;

          return (
            <div key={item.id} className="rounded-xl border border-red-100 bg-white p-5 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold" style={{ color: colors.deepRed }}>
                    {TYPE_LABELS[item.generation_type] || item.generation_type}
                  </h2>
                  <p className="text-xs" style={{ color: colors.textDark }}>
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>

                <span className="rounded-full px-3 py-1 text-xs font-semibold" style={{ backgroundColor: `${statusColor}22`, color: statusColor }}>
                  {item.status}
                </span>
              </div>

              <p className="mb-3 text-sm" style={{ color: colors.textDark }}>
                {summarizeInput(item)}
              </p>

              {item.error_message && (
                <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ backgroundColor: colors.softRed, color: colors.error }}>
                  {item.error_message}
                </p>
              )}

              <div className="flex flex-wrap gap-3">
                {item.output_url && item.status === 'success' && (
                  <a
                    href={getAuthenticatedFileUrl(item.output_url)}
                    className="rounded-md px-3 py-2 text-sm font-semibold text-white"
                    style={{ backgroundColor: colors.deepRed }}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open Output
                  </a>
                )}

                <button
                  type="button"
                  onClick={() => handleDelete(item.id)}
                  className="rounded-md border border-red-100 px-3 py-2 text-sm"
                  style={{ color: colors.textDark }}
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
