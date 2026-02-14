import type { TimelineSegment, TimelineTrack } from '../../components/TimelineEditorPanel';

export interface MixChatThread {
  id: string;
  title: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  planning_status?: string | null;
  planning_draft_id?: string | null;
  planning_round_count?: number;
  active_planning_status?: string | null;
  active_planning_draft_id?: string | null;
}

export interface MixChatMessage {
  id: string;
  thread_id: string;
  role: 'user' | 'assistant' | 'system';
  content_text: string | null;
  content_json: Record<string, unknown>;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  updated_at: string | null;
}

export interface MixChatVersion {
  id: string;
  thread_id: string;
  source_user_message_id: string | null;
  assistant_message_id: string | null;
  parent_version_id: string | null;
  mix_session_id: string | null;
  proposal_json: Record<string, unknown>;
  final_output_json: Record<string, unknown>;
  state_snapshot_json: Record<string, unknown>;
  created_at: string;
}

export interface MixChatRun {
  id: string;
  thread_id: string;
  user_message_id: string;
  assistant_message_id: string;
  parent_version_id: string | null;
  version_id: string | null;
  mode: 'refine_last' | 'restart_fresh';
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress_stage: string;
  progress_percent?: number | null;
  progress_label?: string | null;
  progress_detail?: string | null;
  progress_updated_at?: string | null;
  assistant_message?: MixChatMessage | null;
  error_message: string | null;
  created_at: string;
}

export interface Segment {
  id: string;
  order?: number;
  segment_name?: string;
  track_index: number;
  track_id?: string;
  track_title?: string;
  start_ms: number;
  end_ms: number;
  duration_ms?: number;
  crossfade_after_seconds: number;
  effects?: { reverb_amount?: number; delay_ms?: number; delay_feedback?: number };
  eq?: { low_gain_db?: number; mid_gain_db?: number; high_gain_db?: number };
}

export interface ThreadListResponse {
  items: MixChatThread[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export interface MessageListResponse {
  items: MixChatMessage[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface VersionsResponse {
  items: MixChatVersion[];
}

export interface CreateMessageResponse {
  user_message: MixChatMessage;
  assistant_message_placeholder: MixChatMessage;
  run: MixChatRun;
  poll_hint_ms?: number;
}

export interface MessageTrack {
  id?: string;
  track_index?: number;
  title?: string;
  artist?: string;
  preview_url?: string;
  duration_seconds?: number;
}

export interface TimelineEditorState {
  sourceVersionId: string;
  sourceMessageId: string | null;
  proposalTitle: string;
  tracks: TimelineTrack[];
  segments: TimelineSegment[];
}

export interface TimelineAttachmentPayload {
  type: 'timeline_snapshot';
  source_version_id: string;
  segments: TimelineSegment[];
  editor_metadata?: {
    changed_segment_ids?: string[];
    total_segments?: number;
  };
}

export interface ComposerTimelineAttachment {
  sourceVersionId: string;
  sourceMessageId: string | null;
  proposalTitle: string;
  tracks: TimelineTrack[];
  segments: TimelineSegment[];
  changedSegmentIds: string[];
}

export interface ComposerPlanRevisionAttachment {
  draftId: string;
  sourceMessageId: string | null;
  proposalTitle: string;
}

export interface MixChatPlanDraftDetail {
  id: string;
  status: string;
  round_count: number;
  max_rounds: number;
  required_slots_json: Record<string, unknown>;
  questions_json: unknown[];
  proposal_json: Record<string, unknown>;
  constraint_contract_json: Record<string, unknown>;
  pending_clarifications_json: unknown[];
  updated_at: string | null;
}

export interface MixChatPlanDraftResponse {
  draft: MixChatPlanDraftDetail;
}

export interface ChatMediaTrack {
  key: string;
  title: string;
  artist: string;
  preview_url?: string;
  duration_seconds?: number;
}

export interface ChatMediaOutput {
  version_id: string;
  title: string;
  created_at: string;
  mp3_url?: string;
  wav_url?: string;
  output_code: string;
  version_code: string;
}

export type TimelineResolution = 'keep_attached_cuts' | 'replan_with_prompt' | 'replace_timeline';

export interface PlanningQuestionOption {
  id: string;
  label: string;
  description?: string;
}

export interface PlanningQuestion {
  question_id: string;
  question: string;
  options: PlanningQuestionOption[];
  allow_other?: boolean;
}

export interface PlanningAnswerItem {
  question_id: string;
  selected_option_id: string;
  other_text?: string;
}

export interface PlanningAnswerDraftState {
  selected: Record<string, string>;
  other: Record<string, string>;
  submitting: boolean;
  error: string | null;
}

