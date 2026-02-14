import React, { useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { getAuthenticatedFileUrl } from '../utils/api';

interface PreviewTrack {
  title?: string;
  preview_url?: string;
}

interface PreviewSegment {
  track_index: number;
  start_ms: number;
  end_ms: number;
}

interface TransitionPreviewControlsProps {
  selectedSegment: PreviewSegment | null;
  nextSegment: PreviewSegment | null;
  tracksByIndex: Record<number, PreviewTrack>;
}

export default function TransitionPreviewControls({
  selectedSegment,
  nextSegment,
  tracksByIndex,
}: TransitionPreviewControlsProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const [playingLabel, setPlayingLabel] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    audioRef.current = new Audio();
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
      }
    };
  }, []);

  const stopPlayback = () => {
    if (stopRef.current) {
      stopRef.current();
      stopRef.current = null;
    }
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
    }
    setPlayingLabel(null);
  };

  const playWindow = (rawUrl: string, startSeconds: number, endSeconds: number, label: string): Promise<void> => {
    const audio = audioRef.current;
    if (!audio) {
      return Promise.reject(new Error('Audio player unavailable'));
    }

    return new Promise((resolve, reject) => {
      const url = getAuthenticatedFileUrl(rawUrl);
      setPlayingLabel(label);

      let stopped = false;
      const cleanup = () => {
        audio.removeEventListener('timeupdate', onTimeUpdate);
        audio.removeEventListener('loadedmetadata', onLoadedMetadata);
        audio.removeEventListener('ended', onEnded);
      };
      const stop = () => {
        if (stopped) {
          return;
        }
        stopped = true;
        cleanup();
        audio.pause();
      };
      stopRef.current = stop;

      const onEnded = () => {
        cleanup();
        resolve();
      };
      const onTimeUpdate = () => {
        if (audio.currentTime >= endSeconds) {
          stop();
          resolve();
        }
      };
      const onLoadedMetadata = async () => {
        try {
          audio.currentTime = Math.max(0, startSeconds);
          await audio.play();
        } catch (error) {
          stop();
          reject(error instanceof Error ? error : new Error('Playback failed'));
        }
      };

      audio.addEventListener('timeupdate', onTimeUpdate);
      audio.addEventListener('loadedmetadata', onLoadedMetadata, { once: true });
      audio.addEventListener('ended', onEnded, { once: true });
      audio.src = url;
      audio.load();
    });
  };

  const playSegmentPreview = async () => {
    if (!selectedSegment) {
      return;
    }
    setPreviewError(null);
    const track = tracksByIndex[selectedSegment.track_index];
    if (!track?.preview_url) {
      setPreviewError('Preview audio not available for this segment.');
      return;
    }
    try {
      await playWindow(
        track.preview_url,
        selectedSegment.start_ms / 1000,
        selectedSegment.end_ms / 1000,
        'segment'
      );
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : 'Segment preview failed.');
    } finally {
      setPlayingLabel(null);
    }
  };

  const playTransitionPreview = async () => {
    if (!selectedSegment || !nextSegment) {
      return;
    }
    setPreviewError(null);
    const currentTrack = tracksByIndex[selectedSegment.track_index];
    const nextTrack = tracksByIndex[nextSegment.track_index];
    if (!currentTrack?.preview_url || !nextTrack?.preview_url) {
      setPreviewError('Preview audio not available for transition.');
      return;
    }

    try {
      const tailStartSeconds = Math.max(selectedSegment.start_ms / 1000, (selectedSegment.end_ms / 1000) - 2.0);
      const tailEndSeconds = selectedSegment.end_ms / 1000;
      await playWindow(currentTrack.preview_url, tailStartSeconds, tailEndSeconds, 'transition');

      const headStartSeconds = nextSegment.start_ms / 1000;
      const headEndSeconds = Math.min(nextSegment.end_ms / 1000, headStartSeconds + 2.0);
      await playWindow(nextTrack.preview_url, headStartSeconds, headEndSeconds, 'transition');
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : 'Transition preview failed.');
    } finally {
      setPlayingLabel(null);
    }
  };

  return (
    <div className="rounded-lg border border-red-100 bg-white p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-red-700">Preview</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            if (playingLabel) {
              stopPlayback();
              return;
            }
            void playSegmentPreview();
          }}
          disabled={!selectedSegment}
          className="inline-flex items-center gap-1 rounded-md border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {playingLabel === 'segment' ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          Play Segment
        </button>
        <button
          type="button"
          onClick={() => {
            if (playingLabel) {
              stopPlayback();
              return;
            }
            void playTransitionPreview();
          }}
          disabled={!selectedSegment || !nextSegment}
          className="inline-flex items-center gap-1 rounded-md border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {playingLabel === 'transition' ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          Play Transition
        </button>
      </div>
      {previewError && <p className="mt-2 text-xs text-red-600">{previewError}</p>}
    </div>
  );
}
