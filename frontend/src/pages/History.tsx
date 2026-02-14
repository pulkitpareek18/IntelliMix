import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, ExternalLink, Eye, Music2, Sparkles, Video } from 'lucide-react';
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
  mediumGray: '#9AA0A6',
  success: '#1b8354',
  warning: '#7a5d1e',
  error: '#b42318',
};

const TYPE_LABELS: Record<string, string> = {
  ai_parody: 'AI Music Output',
  audio_mix: 'Audio Mixer Output',
  video_download: 'Downloaded Video',
  audio_download: 'Downloaded Audio',
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

function getOutputMeta(item: GenerationHistoryItem) {
  if (!item.output_url) {
    return null;
  }

  const url = getAuthenticatedFileUrl(item.output_url);
  const fileName = item.output_url.split('/').pop() || 'output-file';
  const loweredFileName = fileName.toLowerCase();
  const isVideo = loweredFileName.endsWith('.mp4') || loweredFileName.endsWith('.webm');
  const isAudio = loweredFileName.endsWith('.mp3') || loweredFileName.endsWith('.m4a') || loweredFileName.endsWith('.wav');

  return {
    url,
    fileName,
    isVideo,
    isAudio,
    canPreview: isVideo || isAudio,
  };
}

function getTypeIcon(type: string) {
  if (type === 'ai_parody') {
    return <Sparkles className="h-4 w-4" />;
  }
  if (type === 'video_download') {
    return <Video className="h-4 w-4" />;
  }
  return <Music2 className="h-4 w-4" />;
}

export default function HistoryPage() {
  const [items, setItems] = useState<GenerationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const limit = 12;
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [viewerItemId, setViewerItemId] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const query = new URLSearchParams({ limit: String(limit), page: String(page) });
      if (filter !== 'all') {
        query.set('type', filter);
      }

      const response = await apiRequest<HistoryResponse>(`${ENDPOINTS.HISTORY}?${query.toString()}`, {
        method: 'GET',
      });

      setItems(response.items);
      setTotal(response.total);
      setPages(Math.max(1, response.pages));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load media generations';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    setPage(1);
  }, [filter]);

  useEffect(() => {
    if (viewerItemId && !items.some((item) => item.id === viewerItemId)) {
      setViewerItemId(null);
    }
  }, [items, viewerItemId]);

  const pageStats = useMemo(() => {
    const outputsOnPage = items.filter((item) => item.output_url).length;
    const downloadsOnPage = items.filter(
      (item) => item.generation_type === 'video_download' || item.generation_type === 'audio_download'
    ).length;
    return { outputsOnPage, downloadsOnPage };
  }, [items]);

  const downloadOutput = (item: GenerationHistoryItem) => {
    const outputMeta = getOutputMeta(item);
    if (!outputMeta) {
      return;
    }

    const link = document.createElement('a');
    link.href = outputMeta.url;
    link.download = outputMeta.fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDelete = async (jobId: string) => {
    try {
      await apiRequest<{ message: string }>(`${ENDPOINTS.HISTORY}/${jobId}`, {
        method: 'DELETE',
      });

      const remainingCountOnPage = items.filter((item) => item.id !== jobId).length;
      if (remainingCountOnPage === 0 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      } else {
        await loadHistory();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      setError(message);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="rounded-2xl border bg-white/95 p-5 shadow-sm" style={{ borderColor: `${colors.deepRed}18` }}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold" style={{ color: colors.deepRed }}>
              Media Generations
            </h1>
            <p className="mt-1 text-sm" style={{ color: colors.textDark }}>
              Account-wide media library for generated mixes and downloaded files.
            </p>
          </div>

          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="rounded-lg border border-red-100 px-3 py-2 text-sm"
            style={{ color: colors.textDark }}
          >
            <option value="all">All media</option>
            <option value="ai_parody">AI Music Studio</option>
            <option value="audio_mix">Audio Mixer</option>
            <option value="video_download">Video downloads</option>
            <option value="audio_download">Audio downloads</option>
          </select>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border p-3" style={{ borderColor: `${colors.deepRed}16`, backgroundColor: '#fff9f3' }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
              Total media
            </p>
            <p className="mt-1 text-2xl font-semibold" style={{ color: colors.textDark }}>
              {total}
            </p>
          </div>
          <div className="rounded-lg border p-3" style={{ borderColor: `${colors.deepRed}16`, backgroundColor: '#fff9f3' }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
              Outputs on this page
            </p>
            <p className="mt-1 text-2xl font-semibold" style={{ color: colors.textDark }}>
              {pageStats.outputsOnPage}
            </p>
          </div>
          <div className="rounded-lg border p-3" style={{ borderColor: `${colors.deepRed}16`, backgroundColor: '#fff9f3' }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
              Downloads on this page
            </p>
            <p className="mt-1 text-2xl font-semibold" style={{ color: colors.textDark }}>
              {pageStats.downloadsOnPage}
            </p>
          </div>
        </div>
      </div>

      {loading && <p style={{ color: colors.textDark }}>Loading media...</p>}

      {error && (
        <p className="rounded-md px-3 py-2 text-sm" style={{ backgroundColor: colors.softRed, color: colors.error }}>
          {error}
        </p>
      )}

      {!loading && items.length === 0 && (
        <div className="rounded-xl border border-red-100 bg-white p-6 text-sm" style={{ color: colors.textDark }}>
          No media yet. Create a mix or download media to populate this library.
        </div>
      )}

      <div className="space-y-4">
        {items.map((item) => {
          const statusColor =
            item.status === 'success' ? colors.success : item.status === 'processing' ? colors.warning : colors.error;
          const viewerOpen = viewerItemId === item.id;
          const outputMeta = getOutputMeta(item);

          return (
            <div key={item.id} className="rounded-xl border border-red-100 bg-white p-5 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-flex h-8 w-8 items-center justify-center rounded-full"
                    style={{ backgroundColor: '#fff2eb', color: colors.deepRed }}
                  >
                    {getTypeIcon(item.generation_type)}
                  </span>
                  <div>
                    <h2 className="font-semibold" style={{ color: colors.deepRed }}>
                      {TYPE_LABELS[item.generation_type] || item.generation_type}
                    </h2>
                    <p className="text-xs" style={{ color: colors.textDark }}>
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                <span
                  className="rounded-full px-3 py-1 text-xs font-semibold"
                  style={{ backgroundColor: `${statusColor}22`, color: statusColor }}
                >
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

              <div className="flex flex-wrap gap-2">
                {outputMeta && item.status === 'success' && (
                  <>
                    <button
                      type="button"
                      onClick={() => setViewerItemId((current) => (current === item.id ? null : item.id))}
                      className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold text-white"
                      style={{ backgroundColor: colors.deepRed }}
                    >
                      <Eye className="h-4 w-4" />
                      {viewerOpen ? 'Hide Preview' : 'Preview'}
                    </button>
                    <a
                      href={outputMeta.url}
                      className="inline-flex items-center gap-2 rounded-md border border-red-100 px-3 py-2 text-sm"
                      style={{ color: colors.textDark }}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Open
                    </a>
                  </>
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

              {viewerOpen && outputMeta && (
                <div className="mt-4 rounded-lg border border-red-100 bg-red-50/40 p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs uppercase tracking-wide" style={{ color: colors.textDark }}>
                      Media Preview
                    </p>
                    <p className="text-xs" style={{ color: colors.textDark }}>
                      {outputMeta.fileName}
                    </p>
                  </div>

                  {outputMeta.canPreview ? (
                    outputMeta.isVideo ? (
                      <video src={outputMeta.url} controls className="w-full rounded-lg border border-red-100 bg-black" />
                    ) : (
                      <audio src={outputMeta.url} controls className="w-full" />
                    )
                  ) : (
                    <div className="rounded-lg border border-red-100 bg-white p-3 text-sm" style={{ color: colors.textDark }}>
                      Preview unavailable for this file type. Use Open or Download.
                    </div>
                  )}

                  <div className="mt-3 flex flex-wrap gap-2">
                    <a
                      href={outputMeta.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold text-white"
                      style={{ backgroundColor: colors.deepRed }}
                    >
                      <ExternalLink className="h-4 w-4" />
                      Open in New Tab
                    </a>
                    <button
                      type="button"
                      onClick={() => downloadOutput(item)}
                      className="inline-flex items-center gap-2 rounded-md border border-red-100 px-3 py-2 text-sm"
                      style={{ color: colors.textDark }}
                    >
                      <Download className="h-4 w-4" />
                      Download
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!loading && items.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-100 bg-white p-4">
          <p className="text-sm" style={{ color: colors.textDark }}>
            Showing page {page} of {pages} ({total} total records)
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1 || loading}
              className="inline-flex items-center gap-1 rounded-md border border-red-100 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              style={{ color: colors.textDark }}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((current) => Math.min(pages, current + 1))}
              disabled={page >= pages || loading}
              className="inline-flex items-center gap-1 rounded-md border border-red-100 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              style={{ color: colors.textDark }}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
