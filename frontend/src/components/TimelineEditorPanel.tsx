import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Paperclip, Plus, Trash2, X } from 'lucide-react';
import SegmentTrimmer from './SegmentTrimmer';
import TransitionPreviewControls from './TransitionPreviewControls';

export interface TimelineTrack {
  id?: string;
  track_index?: number;
  title?: string;
  artist?: string;
  preview_url?: string;
  duration_seconds?: number;
}

export interface TimelineSegment {
  id: string;
  order?: number;
  track_index: number;
  track_id?: string;
  track_title?: string;
  segment_name?: string;
  start_ms: number;
  end_ms: number;
  duration_ms?: number;
  crossfade_after_seconds: number;
  effects?: { reverb_amount?: number; delay_ms?: number; delay_feedback?: number };
  eq?: { low_gain_db?: number; mid_gain_db?: number; high_gain_db?: number };
}

interface TimelineEditorPanelProps {
  open: boolean;
  title: string;
  tracks: TimelineTrack[];
  segments: TimelineSegment[];
  onClose: () => void;
  onAttach: (payload: { segments: TimelineSegment[]; changedSegmentIds: string[] }) => Promise<void> | void;
}

function cloneSegments(segments: TimelineSegment[]): TimelineSegment[] {
  return segments.map((segment) => ({
    ...segment,
    effects: segment.effects ? { ...segment.effects } : {},
    eq: segment.eq ? { ...segment.eq } : {},
  }));
}

function getTrackIndex(track: TimelineTrack | undefined, fallbackIndex: number): number {
  if (track && typeof track.track_index === 'number' && Number.isFinite(track.track_index)) {
    return track.track_index;
  }
  return fallbackIndex;
}

function segmentsEqual(a: TimelineSegment, b: TimelineSegment): boolean {
  return (
    a.track_index === b.track_index &&
    (a.segment_name || '').trim() === (b.segment_name || '').trim() &&
    a.start_ms === b.start_ms &&
    a.end_ms === b.end_ms &&
    Number(a.crossfade_after_seconds.toFixed(3)) === Number(b.crossfade_after_seconds.toFixed(3))
  );
}

export default function TimelineEditorPanel({
  open,
  title,
  tracks,
  segments,
  onClose,
  onAttach,
}: TimelineEditorPanelProps) {
  const [workingSegments, setWorkingSegments] = useState<TimelineSegment[]>([]);
  const [originalSegments, setOriginalSegments] = useState<TimelineSegment[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState<string | null>(null);
  const segmentItemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const resequenceSegments = (items: TimelineSegment[]): TimelineSegment[] =>
    items.map((segment, index) => ({
      ...segment,
      order: index,
      id: String(segment.id || `seg_${index + 1}`).trim() || `seg_${index + 1}`,
      segment_name: (segment.segment_name || '').trim() || `Segment ${index + 1}`,
    }));

  const getTrackDurationMs = (trackIndex: number): number => {
    const track = tracksByIndex[trackIndex];
    const durationFromTrack = Math.round((track?.duration_seconds ?? 0) * 1000);
    return Math.max(durationFromTrack, 1000);
  };

  useEffect(() => {
    if (!open) {
      return;
    }
    const base = resequenceSegments(cloneSegments(segments));
    setWorkingSegments(base);
    setOriginalSegments(resequenceSegments(cloneSegments(segments)));
    setSelectedIndex(0);
    setAttachError(null);
  }, [open, segments]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [open, onClose]);

  const tracksByIndex = useMemo(() => {
    const map: Record<number, TimelineTrack> = {};
    tracks.forEach((track, idx) => {
      map[getTrackIndex(track, idx)] = track;
    });
    return map;
  }, [tracks]);

  const selectedSegment = workingSegments[selectedIndex] ?? null;
  const nextSegment = selectedIndex >= 0 ? (workingSegments[selectedIndex + 1] ?? null) : null;

  const changedSegmentIds = useMemo(() => {
    const changed: string[] = [];
    for (let index = 0; index < workingSegments.length; index += 1) {
      const current = workingSegments[index];
      const original = originalSegments[index];
      if (!original || !segmentsEqual(current, original)) {
        changed.push(current.id);
      }
    }
    return changed;
  }, [workingSegments, originalSegments]);

  const updateSegment = (index: number, updater: (segment: TimelineSegment) => TimelineSegment) => {
    setWorkingSegments((current) =>
      resequenceSegments(current.map((segment, segmentIndex) => (segmentIndex === index ? updater(segment) : segment)))
    );
  };

  const addSegment = () => {
    const insertAt = Math.min(Math.max(selectedIndex + 1, 0), workingSegments.length);
    const baseTrackIndex = workingSegments[selectedIndex]?.track_index ?? getTrackIndex(tracks[0], 0);
    const maxDurationMs = getTrackDurationMs(baseTrackIndex);
    const defaultStartMs = 0;
    const defaultEndMs = Math.min(maxDurationMs, Math.max(defaultStartMs + 1000, 30000));
    const newSegment: TimelineSegment = {
      id: `seg_new_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
      order: insertAt,
      segment_name: `Segment ${workingSegments.length + 1}`,
      track_index: baseTrackIndex,
      track_id: String(baseTrackIndex),
      track_title: tracksByIndex[baseTrackIndex]?.title || '',
      start_ms: defaultStartMs,
      end_ms: defaultEndMs,
      duration_ms: defaultEndMs - defaultStartMs,
      crossfade_after_seconds: 2.0,
      effects: { reverb_amount: 0, delay_ms: 0, delay_feedback: 0 },
      eq: { low_gain_db: 0, mid_gain_db: 0, high_gain_db: 0 },
    };
    setWorkingSegments((current) => {
      const next = [...current];
      next.splice(insertAt, 0, newSegment);
      return resequenceSegments(next);
    });
    setSelectedIndex(insertAt);
  };

  const moveSegment = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= workingSegments.length) {
      return;
    }
    setWorkingSegments((current) => {
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(targetIndex, 0, item);
      return resequenceSegments(next);
    });
    setSelectedIndex(targetIndex);
  };

  const removeSegment = (index: number) => {
    if (workingSegments.length <= 1) {
      setAttachError('At least one segment is required.');
      return;
    }
    setAttachError(null);
    setWorkingSegments((current) => resequenceSegments(current.filter((_, segmentIndex) => segmentIndex !== index)));
    setSelectedIndex((current) => Math.max(0, Math.min(current > index ? current - 1 : current, workingSegments.length - 2)));
  };

  const selectedTrack = selectedSegment ? tracksByIndex[selectedSegment.track_index] : undefined;
  const selectedTrackDurationMs = Math.max(
    selectedSegment ? selectedSegment.end_ms + 1000 : 1000,
    getTrackDurationMs(selectedSegment?.track_index ?? 0)
  );

  useEffect(() => {
    if (workingSegments.length === 0) {
      return;
    }
    setSelectedIndex((current) => Math.min(Math.max(current, 0), workingSegments.length - 1));
  }, [workingSegments.length]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const segment = workingSegments[selectedIndex];
    if (!segment) {
      return;
    }
    segmentItemRefs.current[segment.id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [open, selectedIndex, workingSegments]);

  const handleAttach = async () => {
    setAttachError(null);
    setAttaching(true);
    try {
      const normalizedSegments = resequenceSegments(workingSegments).map((segment, index) => ({
        ...segment,
        order: index,
        segment_name: (segment.segment_name || '').trim() || `Segment ${index + 1}`,
        track_title:
          segment.track_title ||
          tracksByIndex[segment.track_index]?.title ||
          `Track ${segment.track_index + 1}`,
      }));
      await onAttach({
        segments: normalizedSegments,
        changedSegmentIds,
      });
    } catch (error) {
      setAttachError(error instanceof Error ? error.message : 'Failed to attach timeline.');
    } finally {
      setAttaching(false);
    }
  };

  if (!open || segments.length === 0) {
    return null;
  }

  if (typeof document === 'undefined') {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-[120] pointer-events-none">
      <button
        type="button"
        className="absolute inset-0 bg-black/30 pointer-events-auto"
        onClick={onClose}
        aria-label="Close editor"
      />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-[1000px] flex-col border-l border-red-100 bg-white shadow-2xl pointer-events-auto">
        <header className="flex items-center justify-between border-b border-red-100 px-4 py-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-red-700">Timeline Editor</p>
            <h3 className="max-w-[640px] truncate text-sm font-semibold text-gray-700">{title || 'Mix timeline'}</h3>
            <p className="mt-0.5 text-[11px] text-gray-500">Edit segments, then attach this timeline to the chat composer.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-200 text-red-700"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[220px_minmax(0,1fr)]">
          <div className="min-h-0 border-b border-r-0 border-red-100 p-3 md:flex md:flex-col md:overflow-hidden md:border-b-0 md:border-r">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-red-700">Segments</p>
              <button
                type="button"
                onClick={addSegment}
                className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-[11px] font-semibold text-red-700"
              >
                <Plus className="h-3.5 w-3.5" />
                Add
              </button>
            </div>
            <p className="mt-1 text-[11px] text-gray-500">
              {workingSegments.length} total - {Math.min(selectedIndex + 1, workingSegments.length)} selected
            </p>
            <div className="mt-2 space-y-1 overflow-y-auto md:min-h-0 md:flex-1 md:pr-1">
              {workingSegments.map((segment, index) => {
                const track = tracksByIndex[segment.track_index];
                const isActive = index === selectedIndex;
                const durationLabel = `${((segment.end_ms - segment.start_ms) / 1000).toFixed(1)}s`;
                return (
                  <div
                    key={`${segment.id}-${index}`}
                    ref={(node) => {
                      segmentItemRefs.current[segment.id] = node;
                    }}
                    className={`rounded-lg border p-2 text-xs transition-colors ${
                      isActive ? 'border-red-400 bg-red-50' : 'border-red-100 bg-white hover:border-red-200'
                    }`}
                  >
                    <button type="button" onClick={() => setSelectedIndex(index)} className="w-full text-left">
                      <p className="truncate font-semibold text-red-700">{segment.segment_name || `Segment ${index + 1}`}</p>
                      <p className="truncate text-gray-600">{track?.title || `Track ${segment.track_index + 1}`}</p>
                      <p className="mt-0.5 text-[10px] text-gray-500">Duration {durationLabel}</p>
                    </button>
                    <div className="mt-2 flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => moveSegment(index, -1)}
                        disabled={index === 0}
                        className="inline-flex h-6 w-6 items-center justify-center rounded border border-red-200 text-red-700 disabled:opacity-40"
                        aria-label={`Move ${segment.segment_name || `Segment ${index + 1}`} up`}
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveSegment(index, 1)}
                        disabled={index === workingSegments.length - 1}
                        className="inline-flex h-6 w-6 items-center justify-center rounded border border-red-200 text-red-700 disabled:opacity-40"
                        aria-label={`Move ${segment.segment_name || `Segment ${index + 1}`} down`}
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeSegment(index)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded border border-red-200 text-red-700 disabled:opacity-40"
                        aria-label={`Delete ${segment.segment_name || `Segment ${index + 1}`}`}
                        disabled={workingSegments.length <= 1}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="min-h-0 flex flex-col">
            {selectedSegment ? (
              <>
                <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 pb-3">
                  <div className="rounded-lg border border-red-100 bg-red-50/35 p-3">
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-red-700">Segment Editor</p>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-red-700">
                          {selectedTrack?.title || `Track ${selectedSegment.track_index + 1}`}
                        </p>
                        {selectedTrack?.artist && <p className="text-xs text-gray-600">{selectedTrack.artist}</p>}
                        <p className="mt-1 text-[11px] text-gray-500">
                          Segment {selectedIndex + 1} of {workingSegments.length}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => setSelectedIndex((current) => Math.max(0, current - 1))}
                          disabled={selectedIndex === 0}
                          className="inline-flex h-7 w-7 items-center justify-center rounded border border-red-200 text-red-700 disabled:opacity-40"
                          aria-label="Go to previous segment"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setSelectedIndex((current) => Math.min(workingSegments.length - 1, current + 1))}
                          disabled={selectedIndex >= workingSegments.length - 1}
                          className="inline-flex h-7 w-7 items-center justify-center rounded border border-red-200 text-red-700 disabled:opacity-40"
                          aria-label="Go to next segment"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 rounded-lg border border-red-100 bg-white p-3 md:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-red-700">Segment name</label>
                      <input
                        type="text"
                        value={selectedSegment.segment_name || ''}
                        onChange={(event) => {
                          const value = event.target.value.slice(0, 120);
                          updateSegment(selectedIndex, (segment) => ({
                            ...segment,
                            segment_name: value,
                          }));
                        }}
                        placeholder={`Segment ${selectedIndex + 1}`}
                        className="w-full rounded-md border border-red-100 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-red-200"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-red-700">Track</label>
                      <select
                        value={selectedSegment.track_index}
                        onChange={(event) => {
                          const nextTrackIndex = Number(event.target.value);
                          const nextTrackDurationMs = getTrackDurationMs(nextTrackIndex);
                          updateSegment(selectedIndex, (segment) => {
                            const nextStartMs = Math.min(segment.start_ms, Math.max(0, nextTrackDurationMs - 1000));
                            const nextEndMs = Math.max(nextStartMs + 1000, Math.min(segment.end_ms, nextTrackDurationMs));
                            return {
                              ...segment,
                              track_index: nextTrackIndex,
                              track_id: String(nextTrackIndex),
                              track_title: tracksByIndex[nextTrackIndex]?.title || '',
                              start_ms: nextStartMs,
                              end_ms: nextEndMs,
                              duration_ms: nextEndMs - nextStartMs,
                            };
                          });
                        }}
                        className="w-full rounded-md border border-red-100 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-red-200"
                      >
                        {tracks.map((track, idx) => {
                          const trackIndex = getTrackIndex(track, idx);
                          return (
                            <option key={`track-option-${trackIndex}`} value={trackIndex}>
                              {track.title || `Track ${trackIndex + 1}`}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  </div>

                  <div className="rounded-lg border border-red-100 bg-white p-3">
                    <SegmentTrimmer
                      startMs={selectedSegment.start_ms}
                      endMs={selectedSegment.end_ms}
                      maxMs={selectedTrackDurationMs}
                      onChange={(nextStartMs, nextEndMs) => {
                        updateSegment(selectedIndex, (segment) => ({
                          ...segment,
                          start_ms: nextStartMs,
                          end_ms: nextEndMs,
                          duration_ms: nextEndMs - nextStartMs,
                        }));
                      }}
                    />
                  </div>

                  <div className="rounded-lg border border-red-100 bg-white p-3">
                    <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-red-700">
                      Crossfade after segment: {selectedSegment.crossfade_after_seconds.toFixed(1)}s
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={8}
                      step={0.1}
                      value={selectedSegment.crossfade_after_seconds}
                      onChange={(event) => {
                        const next = Number(event.target.value);
                        updateSegment(selectedIndex, (segment) => ({
                          ...segment,
                          crossfade_after_seconds: Number.isFinite(next) ? next : segment.crossfade_after_seconds,
                        }));
                      }}
                      className="w-full"
                    />
                  </div>

                  <TransitionPreviewControls
                    selectedSegment={selectedSegment}
                    nextSegment={nextSegment}
                    tracksByIndex={tracksByIndex}
                  />
                </div>

                <div className="shrink-0 border-t border-red-100 bg-white/95 px-4 py-3 backdrop-blur-sm">
                  <div className="rounded-lg border border-red-100 bg-red-50/30 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-red-700">Attachment Summary</p>
                    <p className="mt-1 text-xs text-gray-700">
                      {changedSegmentIds.length === 0
                        ? 'No segment changes yet. You can still attach this timeline snapshot.'
                        : `${changedSegmentIds.length} segment(s) changed and ready to attach.`}
                    </p>
                  </div>

                  {attachError && <p className="mt-2 text-xs text-red-600">{attachError}</p>}

                  <button
                    type="button"
                    onClick={() => void handleAttach()}
                    disabled={attaching || workingSegments.length === 0}
                    className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Paperclip className="h-4 w-4" />
                    {attaching ? 'Attaching timeline...' : 'Attach timeline to chat'}
                  </button>
                </div>
              </>
            ) : (
              <p className="p-4 text-sm text-gray-600">No editable segments found for this version.</p>
            )}
          </div>
        </div>
      </aside>
    </div>,
    document.body
  );
}
