import React from 'react';

interface SegmentTrimmerProps {
  startMs: number;
  endMs: number;
  maxMs: number;
  minDurationMs?: number;
  onChange: (nextStartMs: number, nextEndMs: number) => void;
}

function msToSeconds(ms: number): number {
  return Number((ms / 1000).toFixed(2));
}

export default function SegmentTrimmer({
  startMs,
  endMs,
  maxMs,
  minDurationMs = 1000,
  onChange,
}: SegmentTrimmerProps) {
  const safeMaxMs = Math.max(maxMs, minDurationMs + 1);
  const safeStartMs = Math.max(0, Math.min(startMs, safeMaxMs - minDurationMs));
  const safeEndMs = Math.max(safeStartMs + minDurationMs, Math.min(endMs, safeMaxMs));

  const selectedLeft = (safeStartMs / safeMaxMs) * 100;
  const selectedRight = (safeEndMs / safeMaxMs) * 100;
  const selectedWidth = Math.max(0, selectedRight - selectedLeft);

  return (
    <div className="space-y-2">
      <div className="relative h-12">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-red-100" />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-red-400/80"
          style={{ left: `${selectedLeft}%`, width: `${selectedWidth}%` }}
        />
        <input
          type="range"
          min={0}
          max={safeMaxMs}
          step={50}
          value={safeStartMs}
          aria-label="Segment start"
          onChange={(event) => {
            const nextStart = Number(event.target.value);
            const clampedStart = Math.max(0, Math.min(nextStart, safeEndMs - minDurationMs));
            onChange(clampedStart, safeEndMs);
          }}
          className="trimmer-range trimmer-range-start absolute inset-0 z-30 w-full appearance-none bg-transparent"
        />
        <input
          type="range"
          min={0}
          max={safeMaxMs}
          step={50}
          value={safeEndMs}
          aria-label="Segment end"
          onChange={(event) => {
            const nextEnd = Number(event.target.value);
            const clampedEnd = Math.min(safeMaxMs, Math.max(nextEnd, safeStartMs + minDurationMs));
            onChange(safeStartMs, clampedEnd);
          }}
          className="trimmer-range trimmer-range-end absolute inset-0 z-20 w-full appearance-none bg-transparent"
        />
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
        <span>Start: {msToSeconds(safeStartMs)}s</span>
        <span className="text-center">Duration: {msToSeconds(safeEndMs - safeStartMs)}s</span>
        <span className="text-right">End: {msToSeconds(safeEndMs)}s</span>
      </div>
    </div>
  );
}
