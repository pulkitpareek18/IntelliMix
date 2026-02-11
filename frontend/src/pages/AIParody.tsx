import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Brain,
  Download,
  History,
  Loader,
  Music,
  Play,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { ENDPOINTS, apiRequest, getAuthenticatedFileUrl } from '../utils/api';

const colors = {
  brightRed: '#f4483a',
  deepRed: '#d24d34',
  vibrantYellow: '#ffb92b',
  white: '#FFFFFF',
  softRed: '#fee2e1',
  softerRed: '#fbeae9',
  textDark: '#444444',
};

const customAudioStyles = `
  .custom-audio-player::-webkit-media-controls-panel {
    background-color: ${colors.softerRed};
  }
`;

interface GeneratedAudio {
  filePath: string;
  status: string;
}

interface HistoryItem {
  id: string;
  generation_type: string;
  status: string;
  input_payload: Record<string, unknown>;
  created_at: string;
}

interface HistoryResponse {
  items: HistoryItem[];
}

export default function AIParody() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedAudio, setGeneratedAudio] = useState<GeneratedAudio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const response = await apiRequest<HistoryResponse>(`${ENDPOINTS.HISTORY}?type=ai_parody&limit=20`, {
        method: 'GET',
      });
      setHistoryItems(response.items);
    } catch {
      // If history fails, the primary generation workflow should still be usable.
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!prompt.trim()) {
      setError('Please enter a prompt for the AI');
      return;
    }

    setLoading(true);
    setError(null);
    setGeneratedAudio(null);

    try {
      const data = await apiRequest<{ filepath: string; message: string }>(
        ENDPOINTS.GENERATE_AI,
        {
          method: 'POST',
          body: JSON.stringify({ prompt }),
        }
      );

      setGeneratedAudio({
        filePath: data.filepath,
        status: 'success',
      });

      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate audio');
    } finally {
      setLoading(false);
    }
  };

  const downloadAudio = () => {
    if (!generatedAudio?.filePath) {
      return;
    }

    const securedUrl = getAuthenticatedFileUrl(generatedAudio.filePath);
    const link = document.createElement('a');
    link.href = securedUrl;
    link.download = generatedAudio.filePath.split('/').pop() || 'generated-parody.mp3';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const mappedHistory = useMemo(() => {
    return historyItems
      .filter((item) => item.generation_type === 'ai_parody')
      .map((item) => {
        const promptValue = item.input_payload?.prompt;
        return {
          id: item.id,
          prompt: typeof promptValue === 'string' ? promptValue : 'AI generation',
          date: new Date(item.created_at).toLocaleString(),
          status: item.status,
        };
      });
  }, [historyItems]);

  const playableAudioUrl = generatedAudio?.filePath ? getAuthenticatedFileUrl(generatedAudio.filePath) : '';

  return (
    <div className="mx-auto h-full max-w-6xl">
      <style dangerouslySetInnerHTML={{ __html: customAudioStyles }} />

      <div className="mb-12 text-center">
        <div className="relative inline-block">
          <div
            className="absolute -inset-1 animate-pulse rounded-full opacity-30 blur"
            style={{ background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})` }}
          />
          <Music className="relative mx-auto mb-4 h-20 w-20" style={{ color: colors.brightRed }} />
        </div>

        <h1 className="mb-2 text-4xl font-bold" style={{ color: colors.deepRed }}>
          AI Music Transformation Studio
        </h1>
        <p className="text-lg" style={{ color: colors.textDark }}>
          Generate mashups and parodies with persistent account history.
        </p>
      </div>

      <div className="grid gap-4 sm:gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
            <div
              className="rounded-2xl bg-white p-4 shadow-sm sm:p-8"
              style={{ borderColor: colors.softRed, borderWidth: '1px', boxShadow: '0 4px 8px rgba(0,0,0,0.05)' }}
            >
              <div className="mb-4 flex items-center">
                <Brain className="mr-2 h-6 w-6" style={{ color: colors.brightRed }} />
                <label className="text-lg font-medium" style={{ color: colors.deepRed }}>
                  Describe Your Vision
                </label>
              </div>

              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                className="h-40 w-full resize-none rounded-xl border px-4 py-3 focus:outline-none focus:ring-2"
                placeholder="Describe your musical vision"
                style={{
                  backgroundColor: colors.white,
                  borderColor: colors.softRed,
                  color: colors.textDark,
                }}
              />

              {error && (
                <div className="mt-2 flex items-center text-sm" style={{ color: colors.brightRed }}>
                  <AlertCircle className="mr-1 h-4 w-4" />
                  {error}
                </div>
              )}

              <div className="mt-6 flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex items-center gap-2 rounded-xl px-6 py-3 font-medium text-white shadow-sm transition-all disabled:opacity-50"
                  style={{ backgroundColor: colors.deepRed }}
                >
                  {loading ? (
                    <>
                      <Loader className="h-5 w-5 animate-spin" />
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="h-5 w-5" />
                      <span>Generate Music</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          <div
            className="mt-6 rounded-2xl bg-white p-4 shadow-sm sm:mt-8 sm:p-8"
            style={{ borderColor: colors.softRed, borderWidth: '1px', boxShadow: '0 4px 8px rgba(0,0,0,0.05)' }}
          >
            <h2 className="mb-6 flex items-center text-2xl font-semibold" style={{ color: colors.deepRed }}>
              <Sparkles className="mr-2 h-6 w-6" style={{ color: colors.brightRed }} />
              Generated Music
            </h2>

            {loading ? (
              <div className="rounded-xl p-6" style={{ backgroundColor: colors.softerRed }}>
                <div className="flex flex-col items-center justify-center space-y-4">
                  <Loader className="h-12 w-12 animate-spin" style={{ color: colors.deepRed }} />
                  <p style={{ color: colors.textDark }}>Creating your parody...</p>
                </div>
              </div>
            ) : generatedAudio?.filePath ? (
              <div className="rounded-xl p-4 sm:p-6" style={{ backgroundColor: colors.softerRed }}>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div
                      className="flex h-10 w-10 items-center justify-center rounded-full"
                      style={{ backgroundColor: colors.deepRed }}
                    >
                      <Music className="h-5 w-5" style={{ color: colors.white }} />
                    </div>
                    <div>
                      <h3 className="font-medium" style={{ color: colors.deepRed }}>
                        Your AI Parody
                      </h3>
                      <p className="text-xs" style={{ color: colors.textDark }}>
                        Saved to your account history
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={downloadAudio}
                    className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-white"
                    style={{ backgroundColor: colors.deepRed }}
                  >
                    <Download className="h-4 w-4" />
                    <span>Download</span>
                  </button>
                </div>

                <div className="w-full rounded-xl border p-2 sm:p-4" style={{ backgroundColor: colors.white, borderColor: colors.softRed }}>
                  <div className="mb-3 flex items-center gap-2 sm:gap-3">
                    <div
                      className="flex h-8 w-8 animate-pulse items-center justify-center rounded-full"
                      style={{ background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})` }}
                    >
                      <Play className="h-4 w-4" style={{ color: colors.white }} />
                    </div>
                    <div className="h-1 flex-grow rounded-full" style={{ backgroundColor: colors.softRed }} />
                  </div>

                  <audio ref={audioRef} controls className="custom-audio-player w-full" src={playableAudioUrl} autoPlay>
                    Your browser does not support the audio element.
                  </audio>
                </div>
              </div>
            ) : (
              <div className="rounded-xl p-8 text-center" style={{ backgroundColor: colors.softerRed }}>
                <Music className="mx-auto mb-3 h-12 w-12 opacity-50" style={{ color: colors.deepRed }} />
                <p style={{ color: colors.textDark }}>No audio generated yet</p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-8">
          <div
            className="rounded-2xl bg-white p-6 shadow-sm"
            style={{ borderColor: colors.softRed, borderWidth: '1px', boxShadow: '0 4px 8px rgba(0,0,0,0.05)' }}
          >
            <h3 className="mb-4 flex items-center text-xl font-semibold" style={{ color: colors.deepRed }}>
              <History className="mr-2 h-5 w-5" style={{ color: colors.brightRed }} />
              Recent Creations
            </h3>

            {historyLoading ? (
              <p className="text-sm" style={{ color: colors.textDark }}>
                Loading history...
              </p>
            ) : (
              <div className="space-y-4">
                {mappedHistory.length === 0 && (
                  <p className="text-sm" style={{ color: colors.textDark }}>
                    No saved prompts yet.
                  </p>
                )}

                {mappedHistory.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="w-full rounded-xl p-4 text-left transition-colors"
                    style={{ backgroundColor: colors.softerRed }}
                    onClick={() => setPrompt(item.prompt)}
                  >
                    <p className="mb-1 text-sm" style={{ color: colors.textDark }}>
                      {item.prompt}
                    </p>
                    <p className="text-xs" style={{ color: '#666666' }}>
                      {item.date}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div
            className="rounded-2xl bg-white p-6 shadow-sm"
            style={{ borderColor: colors.softRed, borderWidth: '1px', boxShadow: '0 4px 8px rgba(0,0,0,0.05)' }}
          >
            <h3 className="mb-4 flex items-center text-xl font-semibold" style={{ color: colors.deepRed }}>
              <Brain className="mr-2 h-5 w-5" style={{ color: colors.brightRed }} />
              AI Suggestions
            </h3>
            <div className="space-y-4">
              <button
                type="button"
                className="w-full rounded-xl border p-4 text-left"
                style={{ backgroundColor: colors.softerRed, borderColor: colors.softRed }}
                onClick={() => setPrompt('Create a nostalgic Bollywood dance mashup with energetic transitions')}
              >
                <h4 className="font-medium" style={{ color: colors.deepRed }}>
                  Bollywood Dance Set
                </h4>
                <p className="text-sm" style={{ color: colors.textDark }}>
                  High energy transitions for a performance mix.
                </p>
              </button>

              <button
                type="button"
                className="w-full rounded-xl border p-4 text-left"
                style={{ backgroundColor: colors.softerRed, borderColor: colors.softRed }}
                onClick={() => setPrompt('Blend 4 Hindi lo-fi songs into a chill late-night study mix')}
              >
                <h4 className="font-medium" style={{ color: colors.deepRed }}>
                  Lo-fi Blend
                </h4>
                <p className="text-sm" style={{ color: colors.textDark }}>
                  Smooth sections with mellow beat continuity.
                </p>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
