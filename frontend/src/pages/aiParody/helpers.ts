import type { TimelineSegment, TimelineTrack } from '../../components/TimelineEditorPanel';
import type {
  MessageTrack,
  MixChatMessage,
  MixChatVersion,
  PlanningQuestion,
  Segment,
  TimelineAttachmentPayload,
  TimelineResolution,
} from './types';

const DISPLAY_TIME_ZONE = 'Asia/Kolkata';

export function getProposalFromMessage(message: MixChatMessage): Record<string, unknown> | null {
  const content = message.content_json;
  const proposal = content?.proposal;
  return proposal && typeof proposal === 'object' ? (proposal as Record<string, unknown>) : null;
}

export function getVersionIdFromMessage(message: MixChatMessage): string | null {
  const value = message.content_json?.version_id;
  return typeof value === 'string' ? value : null;
}

export function getFinalOutput(message: MixChatMessage): { mp3_url?: string; wav_url?: string; job_id?: string } {
  const raw = message.content_json?.final_output;
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const item = raw as Record<string, unknown>;
  return {
    mp3_url: typeof item.mp3_url === 'string' ? item.mp3_url : undefined,
    wav_url: typeof item.wav_url === 'string' ? item.wav_url : undefined,
    job_id: typeof item.job_id === 'string' ? item.job_id : undefined,
  };
}

export function getFinalOutputFromVersion(version: MixChatVersion): {
  mp3_url?: string;
  wav_url?: string;
  job_id?: string;
} {
  const raw = version.final_output_json;
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const item = raw as Record<string, unknown>;
  return {
    mp3_url: typeof item.mp3_url === 'string' ? item.mp3_url : undefined,
    wav_url: typeof item.wav_url === 'string' ? item.wav_url : undefined,
    job_id: typeof item.job_id === 'string' ? item.job_id : undefined,
  };
}

export function getOutputCodeFromVersion(version: MixChatVersion): string {
  const finalOutput = getFinalOutputFromVersion(version);
  if (finalOutput.job_id) {
    return finalOutput.job_id;
  }
  if (version.mix_session_id) {
    return version.mix_session_id;
  }
  return version.id;
}

export function getTitleFromVersion(version: MixChatVersion): string {
  const proposalRoot =
    version.proposal_json && typeof version.proposal_json === 'object'
      ? (version.proposal_json as Record<string, unknown>).proposal
      : null;
  if (proposalRoot && typeof proposalRoot === 'object') {
    const title = (proposalRoot as Record<string, unknown>).title;
    if (typeof title === 'string' && title.trim()) {
      return title;
    }
  }
  return 'Generated Mix';
}

export function getOutputCode(message: MixChatMessage, version: MixChatVersion | undefined): string | null {
  const finalOutput = getFinalOutput(message);
  if (typeof finalOutput.job_id === 'string' && finalOutput.job_id.trim()) {
    return finalOutput.job_id;
  }

  const directJobId = message.content_json?.job_id;
  if (typeof directJobId === 'string' && directJobId.trim()) {
    return directJobId;
  }

  if (version?.mix_session_id) {
    return version.mix_session_id;
  }

  const versionId = getVersionIdFromMessage(message);
  return versionId || null;
}

export function getTracks(message: MixChatMessage): MessageTrack[] {
  const value = message.content_json?.tracks;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      id: typeof item.id === 'string' ? item.id : undefined,
      track_index: typeof item.track_index === 'number' ? item.track_index : undefined,
      title: typeof item.title === 'string' ? item.title : undefined,
      artist: typeof item.artist === 'string' ? item.artist : undefined,
      preview_url: typeof item.preview_url === 'string' ? item.preview_url : undefined,
      duration_seconds: typeof item.duration_seconds === 'number' ? item.duration_seconds : undefined,
    }));
}

export function normalizeTimelineSegments(rawSegments: unknown): TimelineSegment[] {
  if (!Array.isArray(rawSegments)) {
    return [];
  }

  return rawSegments
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item, index) => ({
      id: typeof item.id === 'string' ? item.id : `seg_${index + 1}`,
      order: typeof item.order === 'number' ? item.order : index,
      segment_name: typeof item.segment_name === 'string' ? item.segment_name : undefined,
      track_index: Number(item.track_index ?? 0),
      track_id: typeof item.track_id === 'string' ? item.track_id : undefined,
      track_title: typeof item.track_title === 'string' ? item.track_title : undefined,
      start_ms: Number(item.start_ms ?? 0),
      end_ms: Number(item.end_ms ?? 1000),
      duration_ms: Number(item.duration_ms ?? Number(item.end_ms ?? 1000) - Number(item.start_ms ?? 0)),
      crossfade_after_seconds: Number(item.crossfade_after_seconds ?? 0),
      effects: typeof item.effects === 'object' && item.effects ? (item.effects as Segment['effects']) : {},
      eq: typeof item.eq === 'object' && item.eq ? (item.eq as Segment['eq']) : {},
    }));
}

export function getProposalSegments(proposal: Record<string, unknown> | null): Segment[] {
  if (!proposal) {
    return [];
  }
  return normalizeTimelineSegments(proposal.segments);
}

export function getMessageKind(message: MixChatMessage): string {
  const kind = message.content_json?.kind;
  return typeof kind === 'string' ? kind : '';
}

export function isPlanningQuestionKind(kind: string): boolean {
  return kind === 'planning_questions' || kind === 'planning_revision_questions';
}

export function getPlanningDraftId(message: MixChatMessage): string | null {
  const value = message.content_json?.draft_id;
  return typeof value === 'string' && value.trim() ? value : null;
}

export function getPlanningQuestions(message: MixChatMessage): PlanningQuestion[] {
  const rawQuestions = message.content_json?.questions;
  if (!Array.isArray(rawQuestions)) {
    return [];
  }
  return rawQuestions
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => {
      const rawOptions = Array.isArray(item.options) ? item.options : [];
      const options = rawOptions
        .filter((entry): entry is Record<string, unknown> => typeof entry === 'object' && entry !== null)
        .map((entry) => ({
          id: typeof entry.id === 'string' ? entry.id : '',
          label: typeof entry.label === 'string' ? entry.label : '',
          description: typeof entry.description === 'string' ? entry.description : undefined,
        }))
        .filter((entry) => entry.id && entry.label);
      return {
        question_id: typeof item.question_id === 'string' ? item.question_id : '',
        question: typeof item.question === 'string' ? item.question : '',
        options,
        allow_other: Boolean(item.allow_other),
      };
    })
    .filter((item) => item.question_id && item.question && item.options.length > 0);
}

export function getPlanningProposal(message: MixChatMessage): Record<string, unknown> | null {
  const value = message.content_json?.proposal;
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

export function getPlanningDetectedSongs(message: MixChatMessage): string[] {
  const requiredSlots = message.content_json?.required_slots;
  if (!requiredSlots || typeof requiredSlots !== 'object') {
    return [];
  }

  const songsSlot = (requiredSlots as Record<string, unknown>).songs_set;
  if (!songsSlot || typeof songsSlot !== 'object') {
    return [];
  }

  const rawValue = (songsSlot as Record<string, unknown>).value;
  if (!Array.isArray(rawValue)) {
    return [];
  }

  return rawValue
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0)
    .slice(0, 20);
}

export function getPlanningSongSource(message: MixChatMessage): string {
  const requiredSlots = message.content_json?.required_slots;
  if (!requiredSlots || typeof requiredSlots !== 'object') {
    return '';
  }

  const songsSlot = (requiredSlots as Record<string, unknown>).songs_set;
  if (!songsSlot || typeof songsSlot !== 'object') {
    return '';
  }

  const sourceValue = (songsSlot as Record<string, unknown>).source;
  return typeof sourceValue === 'string' ? sourceValue.trim() : '';
}

export function getPlanningConstraintContract(message: MixChatMessage): Record<string, unknown> | null {
  const value = message.content_json?.constraint_contract;
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

export function getPlanningConstraintViolations(message: MixChatMessage): string[] {
  const value = message.content_json?.violations;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .slice(0, 20);
}

export function getPlanningSongSourceMeta(source: string): { label: string; note: string } | null {
  if (source === 'explicit') {
    return {
      label: 'Prompt detected',
      note: 'Songs parsed directly from your prompt.',
    };
  }
  if (source === 'suggested') {
    return {
      label: 'AI suggested',
      note: 'Songs suggested by IntelliMix from your artist/count intent.',
    };
  }
  if (source === 'user_other') {
    return {
      label: 'Manual list',
      note: 'Songs provided manually in Other/custom list.',
    };
  }
  if (source === 'memory') {
    return {
      label: 'Memory suggested',
      note: 'Songs suggested from your IntelliMix memory profile when prompt context is sparse.',
    };
  }
  return null;
}

export function getTimelineResolutionLabel(resolution: TimelineResolution): string {
  if (resolution === 'keep_attached_cuts') {
    return 'Keep cuts';
  }
  if (resolution === 'replan_with_prompt') {
    return 'Replan';
  }
  return 'Replace timeline';
}

export function getTimelineAttachmentFromContent(content: Record<string, unknown>): TimelineAttachmentPayload | null {
  const rawAttachments = content.attachments;
  if (!Array.isArray(rawAttachments) || rawAttachments.length === 0) {
    return null;
  }
  const item = rawAttachments[0];
  if (!item || typeof item !== 'object') {
    return null;
  }
  const record = item as Record<string, unknown>;
  if (record.type !== 'timeline_snapshot') {
    return null;
  }
  const sourceVersionId = typeof record.source_version_id === 'string' ? record.source_version_id : '';
  if (!sourceVersionId) {
    return null;
  }
  return {
    type: 'timeline_snapshot',
    source_version_id: sourceVersionId,
    segments: normalizeTimelineSegments(record.segments),
    editor_metadata:
      record.editor_metadata && typeof record.editor_metadata === 'object'
        ? (record.editor_metadata as TimelineAttachmentPayload['editor_metadata'])
        : undefined,
  };
}

export function getTimelineSnapshotFromAssistantMessage(message: MixChatMessage): TimelineAttachmentPayload | null {
  const raw = message.content_json?.timeline_snapshot;
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const snapshot = raw as Record<string, unknown>;
  if (snapshot.type !== 'timeline_snapshot') {
    return null;
  }
  const sourceVersionId = typeof snapshot.source_version_id === 'string' ? snapshot.source_version_id : '';
  if (!sourceVersionId) {
    return null;
  }
  return {
    type: 'timeline_snapshot',
    source_version_id: sourceVersionId,
    segments: normalizeTimelineSegments(snapshot.segments),
    editor_metadata:
      snapshot.editor_metadata && typeof snapshot.editor_metadata === 'object'
        ? (snapshot.editor_metadata as TimelineAttachmentPayload['editor_metadata'])
        : undefined,
  };
}

export function getTimelineTracksFromVersion(version: MixChatVersion | undefined): TimelineTrack[] {
  if (!version || !version.proposal_json || typeof version.proposal_json !== 'object') {
    return [];
  }
  const rawTracks = (version.proposal_json as Record<string, unknown>).tracks;
  if (!Array.isArray(rawTracks)) {
    return [];
  }
  return rawTracks
    .filter((track): track is Record<string, unknown> => typeof track === 'object' && track !== null)
    .map((track, index) => ({
      id: typeof track.id === 'string' ? track.id : undefined,
      track_index: typeof track.track_index === 'number' ? track.track_index : index,
      title: typeof track.title === 'string' ? track.title : `Track ${index + 1}`,
      artist: typeof track.artist === 'string' ? track.artist : undefined,
      preview_url:
        typeof track.preview_url === 'string'
          ? track.preview_url
          : typeof track.preview_filename === 'string' && version.mix_session_id
            ? `/files/${version.mix_session_id}/${track.preview_filename}`
            : undefined,
      duration_seconds: typeof track.duration_seconds === 'number' ? track.duration_seconds : undefined,
    }));
}

export function getThreadMonogram(title: string): string {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return '#';
  }
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  const first = words[0][0] ?? '';
  const second = words[1][0] ?? '';
  return `${first}${second}`.toUpperCase();
}

export function getStatusMeta(status: MixChatMessage['status']) {
  if (status === 'queued') {
    return { label: 'Queued', background: '#fff4dc', color: '#9a5a00' };
  }
  if (status === 'running') {
    return { label: 'Running', background: '#eef4ff', color: '#1f4ab8' };
  }
  if (status === 'failed') {
    return { label: 'Failed', background: '#ffe8e8', color: '#b3261e' };
  }
  return { label: 'Completed', background: '#e8f8ee', color: '#136c3d' };
}

export function parseApiTimestamp(value: string): Date {
  const normalized = value.trim().replace(' ', 'T');
  const hasTimezone = /(Z|[+-]\d{2}:\d{2})$/i.test(normalized);
  return new Date(hasTimezone ? normalized : `${normalized}Z`);
}

export function formatMessageTime(value: string): string {
  const parsed = parseApiTimestamp(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return `${parsed.toLocaleTimeString('en-IN', {
    timeZone: DISPLAY_TIME_ZONE,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })} IST`;
}

export function formatThreadTime(value: string): string {
  const parsed = parseApiTimestamp(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return `${parsed.toLocaleString('en-IN', {
    timeZone: DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })} IST`;
}

