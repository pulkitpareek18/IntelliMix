import React, { useEffect, useRef, useState } from 'react';
import { Pause, Play, Volume2, VolumeX } from 'lucide-react';

interface StudioAudioPlayerProps {
  src: string;
  preload?: 'none' | 'metadata' | 'auto';
  compact?: boolean;
  className?: string;
}

const PLAYER_FOCUS_EVENT = 'intellimix-studio-player-focus';

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return '0:00';
  }
  const totalSeconds = Math.floor(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = String(totalSeconds % 60).padStart(2, '0');
  return `${minutes}:${remainingSeconds}`;
}

export default function StudioAudioPlayer({
  src,
  preload = 'metadata',
  compact = false,
  className = '',
}: StudioAudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const playerIdRef = useRef(`studio-player-${Math.random().toString(36).slice(2)}`);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.pause();
    audio.currentTime = 0;
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [src]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    const syncDuration = () => {
      const next = Number.isFinite(audio.duration) ? audio.duration : 0;
      setDuration(next > 0 ? next : 0);
    };
    const syncTime = () => setCurrentTime(audio.currentTime || 0);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => {
      setIsPlaying(false);
      setCurrentTime(audio.duration || 0);
    };

    audio.addEventListener('durationchange', syncDuration);
    audio.addEventListener('loadedmetadata', syncDuration);
    audio.addEventListener('timeupdate', syncTime);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('durationchange', syncDuration);
      audio.removeEventListener('loadedmetadata', syncDuration);
      audio.removeEventListener('timeupdate', syncTime);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('ended', onEnded);
    };
  }, [src]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.volume = Math.min(1, Math.max(0, volume));
  }, [volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.muted = muted;
  }, [muted]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.playbackRate = playbackRate;
  }, [playbackRate]);

  useEffect(() => {
    const onFocusAnotherPlayer = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      if (detail === playerIdRef.current) {
        return;
      }
      const audio = audioRef.current;
      if (audio && !audio.paused) {
        audio.pause();
      }
    };

    window.addEventListener(PLAYER_FOCUS_EVENT, onFocusAnotherPlayer as EventListener);
    return () => window.removeEventListener(PLAYER_FOCUS_EVENT, onFocusAnotherPlayer as EventListener);
  }, []);

  const progress = duration > 0 ? (currentTime / duration) * 1000 : 0;

  const onTogglePlay = async () => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    if (audio.paused) {
      window.dispatchEvent(new CustomEvent(PLAYER_FOCUS_EVENT, { detail: playerIdRef.current }));
      try {
        await audio.play();
      } catch {
        setIsPlaying(false);
      }
      return;
    }

    audio.pause();
  };

  const onSeek = (event: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio || duration <= 0) {
      return;
    }
    const nextProgress = Number(event.target.value);
    const nextTime = (nextProgress / 1000) * duration;
    audio.currentTime = nextTime;
    setCurrentTime(nextTime);
  };

  const onChangeVolume = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = Number(event.target.value);
    setVolume(next / 100);
    setMuted(next <= 0);
  };

  const onToggleMute = () => {
    setMuted((current) => !current);
  };

  return (
    <div
      className={`rounded-xl border bg-white/95 p-2.5 ${className}`}
      style={{ borderColor: 'rgba(210, 77, 52, 0.2)' }}
    >
      <audio ref={audioRef} src={src} preload={preload} />
      <div className={`flex items-center gap-2 ${compact ? '' : 'md:gap-3'}`}>
        <button
          type="button"
          onClick={() => void onTogglePlay()}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-white text-[#d24d34]"
          style={{ borderColor: 'rgba(210, 77, 52, 0.35)' }}
          aria-label={isPlaying ? 'Pause audio' : 'Play audio'}
        >
          {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
        </button>

        <div className="min-w-0 flex-1">
          <input
            type="range"
            min={0}
            max={1000}
            step={1}
            value={Number.isFinite(progress) ? progress : 0}
            onChange={onSeek}
            className="h-2 w-full cursor-pointer accent-[#d24d34]"
            aria-label="Seek audio"
          />
          <div className="mt-1 flex items-center justify-between text-[11px]" style={{ color: '#6b7280' }}>
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={onToggleMute}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-white text-[#d24d34]"
          style={{ borderColor: 'rgba(210, 77, 52, 0.25)' }}
          aria-label={muted ? 'Unmute audio' : 'Mute audio'}
        >
          {muted || volume <= 0 ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
        </button>

        {!compact && (
          <>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={muted ? 0 : Math.round(volume * 100)}
              onChange={onChangeVolume}
              className="hidden h-2 w-20 cursor-pointer accent-[#d24d34] lg:block"
              aria-label="Audio volume"
            />
            <select
              value={String(playbackRate)}
              onChange={(event) => setPlaybackRate(Number(event.target.value))}
              className="hidden rounded-md border bg-white px-2 py-1 text-[11px] text-[#444444] lg:block"
              style={{ borderColor: 'rgba(210, 77, 52, 0.22)' }}
              aria-label="Playback speed"
            >
              <option value="0.75">0.75x</option>
              <option value="1">1x</option>
              <option value="1.25">1.25x</option>
              <option value="1.5">1.5x</option>
            </select>
          </>
        )}
      </div>
    </div>
  );
}
