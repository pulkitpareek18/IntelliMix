import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Archive,
  ArrowDown,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Loader2,
  Menu,
  MessageSquare,
  Paperclip,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  RotateCcw,
  Send,
  X,
} from 'lucide-react';
import TimelineEditorPanel, { TimelineSegment } from '../components/TimelineEditorPanel';
import StudioAudioPlayer from '../components/StudioAudioPlayer';
import {
  ENDPOINTS,
  apiRequest,
  getAuthenticatedFileUrl,
  getMixChatRunEventsUrl,
  getMixChatPlanDraftEndpoint,
} from '../utils/api';
import type {
  ChatMediaOutput,
  ChatMediaTrack,
  ComposerPlanRevisionAttachment,
  ComposerTimelineAttachment,
  CreateMessageResponse,
  MessageListResponse,
  MixChatMessage,
  MixChatPlanDraftDetail,
  MixChatPlanDraftResponse,
  MixChatRun,
  MixChatThread,
  MixChatVersion,
  PlanningAnswerDraftState,
  PlanningAnswerItem,
  ThreadListResponse,
  TimelineAttachmentPayload,
  TimelineEditorState,
  TimelineResolution,
  VersionsResponse,
} from './aiParody/types';
import {
  formatMessageTime,
  formatThreadTime,
  getFinalOutput,
  getFinalOutputFromVersion,
  getMessageKind,
  getOutputCode,
  getOutputCodeFromVersion,
  getPlanningConstraintContract,
  getPlanningConstraintViolations,
  getPlanningDetectedSongs,
  getPlanningDraftId,
  getPlanningProposal,
  getPlanningQuestions,
  getPlanningSongSource,
  getPlanningSongSourceMeta,
  getProposalFromMessage,
  getProposalSegments,
  getStatusMeta,
  getThreadMonogram,
  getTimelineAttachmentFromContent,
  getTimelineResolutionLabel,
  getTimelineSnapshotFromAssistantMessage,
  getTimelineTracksFromVersion,
  getTitleFromVersion,
  getTracks,
  getVersionIdFromMessage,
  isPlanningQuestionKind,
  parseApiTimestamp,
} from './aiParody/helpers';

const colors = {
  deepRed: '#d24d34',
  brightRed: '#f4483a',
  softRed: '#fee2e1',
  softestYellow: '#fff8e8',
  textDark: '#444444',
  mediumGray: '#9AA0A6',
};
export default function AIParody() {
  const chatUiEnabled = (import.meta.env.VITE_AI_CHAT_UI_ENABLED ?? 'true').toLowerCase() !== 'false';
  const timelineAttachmentFlowEnabled =
    (import.meta.env.VITE_TIMELINE_ATTACHMENT_FLOW_ENABLED ?? 'true').toLowerCase() !== 'false';
  const mixChatSseEnabled = (import.meta.env.VITE_MIX_CHAT_SSE_ENABLED ?? 'true').toLowerCase() !== 'false';
  const [threads, setThreads] = useState<MixChatThread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MixChatMessage[]>([]);
  const [versions, setVersions] = useState<MixChatVersion[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [composer, setComposer] = useState('');
  const [sending, setSending] = useState(false);
  const [pollHintMs, setPollHintMs] = useState(2000);
  const [activeRuns, setActiveRuns] = useState<Record<string, string>>({});
  const [runSnapshots, setRunSnapshots] = useState<Record<string, MixChatRun>>({});
  const [error, setError] = useState<string | null>(null);
  const [planningAnswerDrafts, setPlanningAnswerDrafts] = useState<Record<string, PlanningAnswerDraftState>>({});
  const [planningActionBusy, setPlanningActionBusy] = useState<Record<string, boolean>>({});
  const [expandedAdvanced, setExpandedAdvanced] = useState<Record<string, boolean>>({});
  const [collapsedMixArtifacts, setCollapsedMixArtifacts] = useState<Record<string, boolean>>({});
  const [timelineEditor, setTimelineEditor] = useState<TimelineEditorState | null>(null);
  const [composerAttachment, setComposerAttachment] = useState<ComposerTimelineAttachment | null>(null);
  const [composerPlanRevision, setComposerPlanRevision] = useState<ComposerPlanRevisionAttachment | null>(null);
  const [composerPlanDraftView, setComposerPlanDraftView] = useState<MixChatPlanDraftDetail | null>(null);
  const [composerPlanDraftLoading, setComposerPlanDraftLoading] = useState(false);
  const [forceNewDraft, setForceNewDraft] = useState(false);
  const [pendingTimelineResolution, setPendingTimelineResolution] = useState<TimelineResolution | null>(null);
  const [copiedCodeByKey, setCopiedCodeByKey] = useState<Record<string, boolean>>({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileThreadsOpen, setMobileThreadsOpen] = useState(false);
  const [chatMediaOpen, setChatMediaOpen] = useState(false);
  const [isNearBottom, setIsNearBottom] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const shouldStickToBottomRef = useRef(true);
  const runEventSourcesRef = useRef<Record<string, EventSource>>({});
  const runSseFallbackRef = useRef<Record<string, boolean>>({});

  const activeThread = useMemo(
    () => threads.find((item) => item.id === activeThreadId) ?? null,
    [threads, activeThreadId]
  );
  const activePlanningDraftId = useMemo(() => {
    if (!activeThread) {
      return null;
    }
    if (typeof activeThread.active_planning_draft_id === 'string' && activeThread.active_planning_draft_id.trim()) {
      return activeThread.active_planning_draft_id;
    }
    if (typeof activeThread.planning_draft_id === 'string' && activeThread.planning_draft_id.trim()) {
      return activeThread.planning_draft_id;
    }
    return null;
  }, [activeThread]);
  const activePlanningStatus = useMemo(() => {
    if (!activeThread) {
      return null;
    }
    if (typeof activeThread.active_planning_status === 'string' && activeThread.active_planning_status.trim()) {
      return activeThread.active_planning_status;
    }
    if (typeof activeThread.planning_status === 'string' && activeThread.planning_status.trim()) {
      return activeThread.planning_status;
    }
    return null;
  }, [activeThread]);
  const hasActivePlanningDraft = useMemo(
    () =>
      Boolean(
        activePlanningDraftId &&
          activePlanningStatus &&
          ['collecting', 'draft_ready', 'approved'].includes(activePlanningStatus)
      ),
    [activePlanningDraftId, activePlanningStatus]
  );

  const versionMap = useMemo(() => {
    const map: Record<string, MixChatVersion> = {};
    versions.forEach((item) => {
      map[item.id] = item;
    });
    return map;
  }, [versions]);

  const chatMedia = useMemo(() => {
    const downloadedTracksByKey = new Map<string, ChatMediaTrack>();
    const outputs: ChatMediaOutput[] = [];
    const sortedVersions = [...versions].sort(
      (a, b) => parseApiTimestamp(b.created_at).getTime() - parseApiTimestamp(a.created_at).getTime()
    );

    sortedVersions.forEach((version) => {
      const tracks = getTimelineTracksFromVersion(version);
      tracks.forEach((track, index) => {
        const previewUrl = typeof track.preview_url === 'string' ? track.preview_url : undefined;
        if (!previewUrl) {
          return;
        }
        const key = `${previewUrl}|${track.title || ''}|${track.artist || ''}|${track.track_index ?? index}`;
        if (downloadedTracksByKey.has(key)) {
          return;
        }
        downloadedTracksByKey.set(key, {
          key,
          title: track.title || `Track ${(track.track_index ?? index) + 1}`,
          artist: track.artist || 'Unknown artist',
          preview_url: previewUrl,
          duration_seconds: track.duration_seconds,
        });
      });

      const finalOutput = getFinalOutputFromVersion(version);
      if (!finalOutput.mp3_url && !finalOutput.wav_url) {
        return;
      }

      outputs.push({
        version_id: version.id,
        title: getTitleFromVersion(version),
        created_at: version.created_at,
        mp3_url: finalOutput.mp3_url,
        wav_url: finalOutput.wav_url,
        output_code: getOutputCodeFromVersion(version),
        version_code: version.id,
      });
    });

    return {
      downloadedTracks: Array.from(downloadedTracksByKey.values()),
      outputs,
    };
  }, [versions]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    container.scrollTo({ top: container.scrollHeight, behavior });
  }, []);

  const closeRunEventSource = useCallback((runId: string) => {
    const source = runEventSourcesRef.current[runId];
    if (source) {
      source.close();
      delete runEventSourcesRef.current[runId];
    }
  }, []);

  const handleMessageScroll = useCallback(() => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
    shouldStickToBottomRef.current = nearBottom;
    setIsNearBottom(nearBottom);
  }, []);

  const loadThreads = useCallback(async () => {
    setThreadsLoading(true);
    try {
      const response = await apiRequest<ThreadListResponse>(`${ENDPOINTS.MIX_CHATS}?limit=50&page=1`, {
        method: 'GET',
      });
      setThreads(response.items);
      if (response.items.length === 0) {
        setActiveThreadId(null);
      } else if (!activeThreadId || !response.items.some((item) => item.id === activeThreadId)) {
        setActiveThreadId(response.items[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chats');
    } finally {
      setThreadsLoading(false);
    }
  }, [activeThreadId]);

  const loadVersions = useCallback(async (threadId: string) => {
    const response = await apiRequest<VersionsResponse>(`${ENDPOINTS.MIX_CHATS}/${threadId}/versions?limit=100`, {
      method: 'GET',
    });
    setVersions(response.items);
  }, []);

  const loadMessages = useCallback(
    async (threadId: string, cursor?: string | null, appendOlder = false) => {
      setMessagesLoading(true);
      try {
        const query = new URLSearchParams({ limit: '30' });
        if (cursor) {
          query.set('cursor', cursor);
        }
        const response = await apiRequest<MessageListResponse>(
          `${ENDPOINTS.MIX_CHATS}/${threadId}/messages?${query.toString()}`,
          { method: 'GET' }
        );

        if (appendOlder) {
          setMessages((current) => [...response.items, ...current]);
        } else {
          shouldStickToBottomRef.current = true;
          setIsNearBottom(true);
          setMessages(response.items);
        }
        setNextCursor(response.next_cursor);
        setHasMoreMessages(response.has_more);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load messages');
      } finally {
        setMessagesLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  useEffect(() => {
    if (!activeThreadId) {
      setMessages([]);
      setVersions([]);
      setTimelineEditor(null);
      setComposerAttachment(null);
      setComposerPlanRevision(null);
      setComposerPlanDraftView(null);
      setComposerPlanDraftLoading(false);
      setForceNewDraft(false);
      setPendingTimelineResolution(null);
      setPlanningAnswerDrafts({});
      setPlanningActionBusy({});
      return;
    }
    setTimelineEditor(null);
    setComposerAttachment(null);
    setComposerPlanRevision(null);
    setComposerPlanDraftView(null);
    setComposerPlanDraftLoading(false);
    setForceNewDraft(false);
    setPendingTimelineResolution(null);
    setChatMediaOpen(false);
    setPlanningAnswerDrafts({});
    setPlanningActionBusy({});
    void loadMessages(activeThreadId, null, false);
    void loadVersions(activeThreadId);
    setMobileThreadsOpen(false);
  }, [activeThreadId, loadMessages, loadVersions]);

  useEffect(() => {
    if (!timelineEditor || !timelineEditor.sourceMessageId) {
      return;
    }
    const messageExists = messages.some((message) => message.id === timelineEditor.sourceMessageId);
    if (!messageExists) {
      setTimelineEditor(null);
    }
  }, [messages, timelineEditor]);

  useEffect(() => {
    if (messages.length === 0) {
      return;
    }
    if (!shouldStickToBottomRef.current) {
      return;
    }
    scrollToBottom('smooth');
  }, [messages, scrollToBottom]);

  useEffect(() => {
    const activeRunEntries = Object.entries(activeRuns);
    const browserSupportsSse = typeof window !== 'undefined' && typeof window.EventSource !== 'undefined';
    const shouldUseSse = mixChatSseEnabled && browserSupportsSse;

    const syncAssistantMessageFromRun = (run: MixChatRun) => {
      const assistantMessage = run.assistant_message;
      if (!assistantMessage || typeof assistantMessage.id !== 'string') {
        return;
      }
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantMessage.id
            ? {
                ...message,
                ...assistantMessage,
              }
            : message
        )
      );
    };

    const syncRunSnapshot = (run: MixChatRun) => {
      setRunSnapshots((current) => ({
        ...current,
        [run.id]: run,
      }));
      syncAssistantMessageFromRun(run);
    };

    const handleTerminalRun = (run: MixChatRun, fallbackThreadId: string) => {
      const effectiveThreadId = run.thread_id || fallbackThreadId;
      syncAssistantMessageFromRun(run);
      setActiveRuns((current) => {
        const next = { ...current };
        delete next[run.id];
        return next;
      });
      setRunSnapshots((current) => {
        const next = { ...current };
        delete next[run.id];
        return next;
      });
      closeRunEventSource(run.id);
      delete runSseFallbackRef.current[run.id];
      if (activeThreadId === effectiveThreadId) {
        void loadMessages(effectiveThreadId, null, false);
        void loadVersions(effectiveThreadId);
      }
      void loadThreads();
    };

    if (activeRunEntries.length === 0) {
      Object.keys(runEventSourcesRef.current).forEach((runId) => closeRunEventSource(runId));
      runSseFallbackRef.current = {};
      setRunSnapshots({});
      return;
    }

    if (shouldUseSse) {
      for (const [runId, threadId] of activeRunEntries) {
        if (runEventSourcesRef.current[runId] || runSseFallbackRef.current[runId]) {
          continue;
        }
        try {
          const streamUrl = getMixChatRunEventsUrl(runId);
          const source = new EventSource(streamUrl);
          runEventSourcesRef.current[runId] = source;

          const processPayload = (rawData: string) => {
            try {
              const payload = JSON.parse(rawData) as { run?: MixChatRun; terminal?: boolean };
              const run = payload?.run;
              if (!run || typeof run !== 'object' || typeof run.id !== 'string') {
                return;
              }
              syncRunSnapshot(run);
              const isTerminal = Boolean(payload.terminal) || run.status === 'completed' || run.status === 'failed';
              if (isTerminal) {
                handleTerminalRun(run, threadId);
              }
            } catch {
              // ignore malformed stream payload
            }
          };

          source.addEventListener('run_update', (event: Event) => {
            const messageEvent = event as MessageEvent<string>;
            processPayload(messageEvent.data);
          });

          source.addEventListener('stream_end', () => {
            closeRunEventSource(runId);
            runSseFallbackRef.current[runId] = true;
          });

          source.onopen = () => {
            delete runSseFallbackRef.current[runId];
          };

          source.onerror = () => {
            closeRunEventSource(runId);
            runSseFallbackRef.current[runId] = true;
          };
        } catch {
          runSseFallbackRef.current[runId] = true;
        }
      }
    }

    for (const runId of Object.keys(runEventSourcesRef.current)) {
      if (!activeRuns[runId]) {
        closeRunEventSource(runId);
        delete runSseFallbackRef.current[runId];
        setRunSnapshots((current) => {
          const next = { ...current };
          delete next[runId];
          return next;
        });
      }
    }

    const timer = window.setInterval(async () => {
      const pollingEntries = Object.entries(activeRuns).filter(
        ([runId]) => !shouldUseSse || runSseFallbackRef.current[runId] || !runEventSourcesRef.current[runId]
      );
      if (pollingEntries.length === 0) {
        return;
      }
      for (const [runId, threadId] of pollingEntries) {
        try {
          const response = await apiRequest<{ run: MixChatRun }>(`${ENDPOINTS.MIX_CHAT_RUNS}/${runId}`, {
            method: 'GET',
          });
          const run = response.run;
          syncRunSnapshot(run);
          if (run.status === 'completed' || run.status === 'failed') {
            handleTerminalRun(run, threadId);
          }
        } catch {
          // best-effort polling fallback
        }
      }
    }, pollHintMs);

    return () => window.clearInterval(timer);
  }, [
    activeRuns,
    pollHintMs,
    activeThreadId,
    loadMessages,
    loadVersions,
    loadThreads,
    mixChatSseEnabled,
    closeRunEventSource,
    setMessages,
  ]);

  useEffect(() => {
    return () => {
      const openSources = runEventSourcesRef.current;
      Object.keys(openSources).forEach((runId) => {
        const source = openSources[runId];
        if (source) {
          source.close();
          delete openSources[runId];
        }
      });
      runEventSourcesRef.current = {};
      runSseFallbackRef.current = {};
    };
  }, []);

  useEffect(() => {
    const textarea = composerRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = '0px';
    const maxHeight = 168;
    const contentHeight = Math.max(textarea.scrollHeight, 56);
    textarea.style.height = `${Math.min(contentHeight, maxHeight)}px`;
    textarea.style.overflowY = contentHeight > maxHeight ? 'auto' : 'hidden';
  }, [composer]);

  useEffect(() => {
    const handleOpenThreads = () => setMobileThreadsOpen(true);
    window.addEventListener('studio-open-threads', handleOpenThreads);
    return () => window.removeEventListener('studio-open-threads', handleOpenThreads);
  }, []);

  useEffect(() => {
    if (!mobileThreadsOpen) {
      return;
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileThreadsOpen(false);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [mobileThreadsOpen]);

  const createThread = async () => {
    try {
      const response = await apiRequest<{ thread: MixChatThread }>(ENDPOINTS.MIX_CHATS, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setThreads((current) => [response.thread, ...current]);
      setActiveThreadId(response.thread.id);
      setComposer('');
      setComposerAttachment(null);
      setComposerPlanRevision(null);
      setComposerPlanDraftView(null);
      setComposerPlanDraftLoading(false);
      setPendingTimelineResolution(null);
      setError(null);
      shouldStickToBottomRef.current = true;
      setIsNearBottom(true);
      setMobileThreadsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create chat');
    }
  };

  const renameThread = async (thread: MixChatThread) => {
    const nextTitle = window.prompt('Rename chat', thread.title)?.trim();
    if (!nextTitle) {
      return;
    }
    try {
      const response = await apiRequest<{ thread: MixChatThread }>(`${ENDPOINTS.MIX_CHATS}/${thread.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: nextTitle }),
      });
      setThreads((current) => current.map((item) => (item.id === thread.id ? response.thread : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rename chat');
    }
  };

  const archiveThread = async (threadId: string) => {
    try {
      await apiRequest<{ thread: MixChatThread }>(`${ENDPOINTS.MIX_CHATS}/${threadId}`, {
        method: 'DELETE',
      });

      setThreads((current) => {
        const next = current.filter((item) => item.id !== threadId);
        if (activeThreadId === threadId) {
          setActiveThreadId(next[0]?.id ?? null);
        }
        return next;
      });
      setMobileThreadsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to archive chat');
    }
  };

  const sendPrompt = async () => {
    if (!activeThreadId) {
      setError('Create or select a chat first.');
      return;
    }
    const content = composer.trim();
    if (!content && !composerAttachment) {
      return;
    }
    if (composerPlanRevision && !content) {
      setError('Add a revision prompt before sending.');
      return;
    }

    const attachments: TimelineAttachmentPayload[] = timelineAttachmentFlowEnabled && composerAttachment
      ? [
          {
            type: 'timeline_snapshot',
            source_version_id: composerAttachment.sourceVersionId,
            segments: composerAttachment.segments,
            editor_metadata: {
              changed_segment_ids: composerAttachment.changedSegmentIds,
              total_segments: composerAttachment.segments.length,
            },
          },
        ]
      : [];

    setSending(true);
    setError(null);
    try {
      const targetDraftId =
        composerPlanRevision?.draftId ||
        (hasActivePlanningDraft && !forceNewDraft && activePlanningDraftId ? activePlanningDraftId : null);
      const requestBody: Record<string, unknown> = {
        content,
        mode: 'refine_last',
        attachments: attachments.length ? attachments : undefined,
        timeline_resolution: attachments.length && pendingTimelineResolution ? pendingTimelineResolution : undefined,
      };
      if (!attachments.length) {
        if (forceNewDraft) {
          requestBody.planning_target = 'new_draft';
          requestBody.revision_mode = 'freeform';
        } else if (targetDraftId) {
          requestBody.planning_target = 'existing_draft';
          requestBody.draft_id = targetDraftId;
          requestBody.revision_mode = composerPlanRevision ? 'freeform' : 'auto_continuation';
        } else {
          requestBody.planning_target = 'auto';
        }
      }
      const response = await apiRequest<CreateMessageResponse>(`${ENDPOINTS.MIX_CHATS}/${activeThreadId}/messages`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
      });
      setComposer('');
      setComposerAttachment(null);
      setComposerPlanRevision(null);
      setComposerPlanDraftView(null);
      setComposerPlanDraftLoading(false);
      setForceNewDraft(false);
      setPendingTimelineResolution(null);
      shouldStickToBottomRef.current = true;
      setIsNearBottom(true);
      setMessages((current) => [...current, response.user_message, response.assistant_message_placeholder]);
      setActiveRuns((current) => ({ ...current, [response.run.id]: activeThreadId }));
      setRunSnapshots((current) => ({ ...current, [response.run.id]: response.run }));
      if (typeof response.poll_hint_ms === 'number' && response.poll_hint_ms > 0) {
        setPollHintMs(response.poll_hint_ms);
      }
      void loadThreads();
      window.setTimeout(() => scrollToBottom('smooth'), 10);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send prompt');
    } finally {
      setSending(false);
    }
  };

  const updatePlanningOption = (messageId: string, questionId: string, optionId: string) => {
    setPlanningAnswerDrafts((current) => {
      const existing = current[messageId] ?? {
        selected: {},
        other: {},
        submitting: false,
        error: null,
      };
      return {
        ...current,
        [messageId]: {
          ...existing,
          selected: {
            ...existing.selected,
            [questionId]: optionId,
          },
          error: null,
        },
      };
    });
  };

  const updatePlanningOtherText = (messageId: string, questionId: string, text: string) => {
    setPlanningAnswerDrafts((current) => {
      const existing = current[messageId] ?? {
        selected: {},
        other: {},
        submitting: false,
        error: null,
      };
      return {
        ...current,
        [messageId]: {
          ...existing,
          other: {
            ...existing.other,
            [questionId]: text.slice(0, 600),
          },
          error: null,
        },
      };
    });
  };

  const submitPlanningAnswers = async (message: MixChatMessage) => {
    if (!activeThreadId) {
      setError('Create or select a chat first.');
      return;
    }
    const draftId = getPlanningDraftId(message);
    if (!draftId) {
      setError('Missing planning draft id.');
      return;
    }
    const questions = getPlanningQuestions(message);
    if (questions.length === 0) {
      setError('No planning questions found.');
      return;
    }

    const answerState = planningAnswerDrafts[message.id] ?? {
      selected: {},
      other: {},
      submitting: false,
      error: null,
    };
    const answers: PlanningAnswerItem[] = questions
      .map((question) => {
        const selectedOptionId = (answerState.selected[question.question_id] || '').trim();
        const otherText = (answerState.other[question.question_id] || '').trim();
        if (!selectedOptionId && !otherText) {
          return null;
        }
        return {
          question_id: question.question_id,
          selected_option_id: selectedOptionId,
          other_text: otherText || undefined,
        };
      })
      .filter((item): item is PlanningAnswerItem => item !== null);

    if (answers.length === 0) {
      setPlanningAnswerDrafts((current) => ({
        ...current,
        [message.id]: {
          ...answerState,
          submitting: false,
          error: 'Select at least one option or provide Other text.',
        },
      }));
      return;
    }

    setPlanningAnswerDrafts((current) => ({
      ...current,
      [message.id]: {
        ...answerState,
        submitting: true,
        error: null,
      },
    }));
    setError(null);
    try {
      const response = await apiRequest<CreateMessageResponse>(`${ENDPOINTS.MIX_CHATS}/${activeThreadId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          planning_response: {
            draft_id: draftId,
            answers,
          },
        }),
      });
      shouldStickToBottomRef.current = true;
      setIsNearBottom(true);
      setMessages((current) => [...current, response.user_message, response.assistant_message_placeholder]);
      setActiveRuns((current) => ({ ...current, [response.run.id]: activeThreadId }));
      setRunSnapshots((current) => ({ ...current, [response.run.id]: response.run }));
      if (typeof response.poll_hint_ms === 'number' && response.poll_hint_ms > 0) {
        setPollHintMs(response.poll_hint_ms);
      }
      setPlanningAnswerDrafts((current) => {
        const next = { ...current };
        delete next[message.id];
        return next;
      });
      void loadThreads();
      window.setTimeout(() => scrollToBottom('smooth'), 10);
    } catch (err) {
      const messageText = err instanceof Error ? err.message : 'Failed to submit planning answers';
      setPlanningAnswerDrafts((current) => ({
        ...current,
        [message.id]: {
          ...answerState,
          submitting: false,
          error: messageText,
        },
      }));
      setError(messageText);
    }
  };

  const regeneratePlanningSongSuggestions = async (message: MixChatMessage) => {
    if (!activeThreadId) {
      setError('Create or select a chat first.');
      return;
    }

    const draftId = getPlanningDraftId(message);
    if (!draftId) {
      setError('Missing planning draft id.');
      return;
    }

    const actionKey = `${message.id}:regenerate_suggestions`;
    setPlanningActionBusy((current) => ({ ...current, [actionKey]: true }));
    setError(null);
    try {
      const response = await apiRequest<CreateMessageResponse>(`${ENDPOINTS.MIX_CHATS}/${activeThreadId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          planning_response: {
            draft_id: draftId,
            answers: [{ question_id: 'songs_set', selected_option_id: 'regenerate_suggestions' }],
          },
        }),
      });

      shouldStickToBottomRef.current = true;
      setIsNearBottom(true);
      setMessages((current) => [...current, response.user_message, response.assistant_message_placeholder]);
      setActiveRuns((current) => ({ ...current, [response.run.id]: activeThreadId }));
      setRunSnapshots((current) => ({ ...current, [response.run.id]: response.run }));
      if (typeof response.poll_hint_ms === 'number' && response.poll_hint_ms > 0) {
        setPollHintMs(response.poll_hint_ms);
      }
      void loadThreads();
      window.setTimeout(() => scrollToBottom('smooth'), 10);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate song suggestions');
    } finally {
      setPlanningActionBusy((current) => {
        const next = { ...current };
        delete next[actionKey];
        return next;
      });
    }
  };

  const submitPlanningAction = async (
    message: MixChatMessage,
    draftId: string,
    action: 'approve_plan'
  ) => {
    if (!activeThreadId) {
      setError('Create or select a chat first.');
      return;
    }
    const actionKey = `${message.id}:${action}`;
    setPlanningActionBusy((current) => ({ ...current, [actionKey]: true }));
    setError(null);
    try {
      const response = await apiRequest<CreateMessageResponse>(`${ENDPOINTS.MIX_CHATS}/${activeThreadId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          planning_action: {
            draft_id: draftId,
            action,
          },
        }),
      });
      shouldStickToBottomRef.current = true;
      setIsNearBottom(true);
      setMessages((current) => [...current, response.user_message, response.assistant_message_placeholder]);
      setActiveRuns((current) => ({ ...current, [response.run.id]: activeThreadId }));
      setRunSnapshots((current) => ({ ...current, [response.run.id]: response.run }));
      if (typeof response.poll_hint_ms === 'number' && response.poll_hint_ms > 0) {
        setPollHintMs(response.poll_hint_ms);
      }
      void loadThreads();
      window.setTimeout(() => scrollToBottom('smooth'), 10);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit planning action');
    } finally {
      setPlanningActionBusy((current) => {
        const next = { ...current };
        delete next[actionKey];
        return next;
      });
    }
  };

  const loadOlderMessages = async () => {
    if (!activeThreadId || !nextCursor) {
      return;
    }
    shouldStickToBottomRef.current = false;
    setIsNearBottom(false);
    await loadMessages(activeThreadId, nextCursor, true);
  };

  const toggleAdvanced = (messageId: string) => {
    setExpandedAdvanced((current) => ({ ...current, [messageId]: !current[messageId] }));
  };

  const toggleMixArtifacts = (messageId: string) => {
    setCollapsedMixArtifacts((current) => ({ ...current, [messageId]: !current[messageId] }));
  };

  const openTimelineEditor = (versionId: string, message: MixChatMessage) => {
    const proposal = getProposalFromMessage(message);
    const segments = getProposalSegments(proposal);
    if (segments.length === 0) {
      setError('No editable timeline segments found for this version.');
      return;
    }

    let tracks = getTracks(message).map((track, index) => ({
      id: track.id,
      track_index: typeof track.track_index === 'number' ? track.track_index : index,
      title: track.title,
      artist: track.artist,
      preview_url: track.preview_url,
      duration_seconds: track.duration_seconds,
    }));
    if (tracks.length === 0) {
      tracks = getTimelineTracksFromVersion(versionMap[versionId]);
    }
    if (tracks.length === 0) {
      setError('No source tracks available for timeline editing.');
      return;
    }

    setTimelineEditor({
      sourceVersionId: versionId,
      sourceMessageId: message.id,
      proposalTitle: typeof proposal?.title === 'string' ? proposal.title : 'Mix timeline',
      tracks,
      segments,
    });
  };

  const attachTimelineToComposer = async (payload: {
    segments: TimelineSegment[];
    changedSegmentIds: string[];
  }) => {
    if (!timelineEditor) {
      throw new Error('No active chat timeline context.');
    }
    if (!timelineAttachmentFlowEnabled) {
      throw new Error('Timeline attachment flow is disabled.');
    }

    setComposerAttachment({
      sourceVersionId: timelineEditor.sourceVersionId,
      sourceMessageId: timelineEditor.sourceMessageId,
      proposalTitle: timelineEditor.proposalTitle,
      tracks: timelineEditor.tracks,
      segments: payload.segments,
      changedSegmentIds: payload.changedSegmentIds,
    });
    setComposerPlanRevision(null);
    setComposerPlanDraftView(null);
    setComposerPlanDraftLoading(false);
    setPendingTimelineResolution(null);
    setTimelineEditor(null);
    setError(null);
  };

  const openAttachmentEditor = () => {
    if (!composerAttachment) {
      return;
    }
    setTimelineEditor({
      sourceVersionId: composerAttachment.sourceVersionId,
      sourceMessageId: composerAttachment.sourceMessageId,
      proposalTitle: composerAttachment.proposalTitle,
      tracks: composerAttachment.tracks,
      segments: composerAttachment.segments,
    });
  };

  const loadPlanDraftView = useCallback(
    async (draftId: string, sourceMessage?: MixChatMessage | null) => {
      if (!activeThreadId || !draftId.trim()) {
        return;
      }
      setComposerPlanDraftLoading(true);
      try {
        const response = await apiRequest<MixChatPlanDraftResponse>(
          getMixChatPlanDraftEndpoint(activeThreadId, draftId),
          { method: 'GET' }
        );
        const draft = response.draft;
        const draftProposal =
          draft.proposal_json && typeof draft.proposal_json === 'object' ? draft.proposal_json : {};
        const draftRequiredSlots =
          draft.required_slots_json && typeof draft.required_slots_json === 'object'
            ? draft.required_slots_json
            : {};
        const fallbackProposal = sourceMessage ? getPlanningProposal(sourceMessage) : null;
        const fallbackRequiredSlots =
          sourceMessage && sourceMessage.content_json && typeof sourceMessage.content_json.required_slots === 'object'
            ? (sourceMessage.content_json.required_slots as Record<string, unknown>)
            : null;
        setComposerPlanDraftView({
          ...draft,
          proposal_json:
            Object.keys(draftProposal).length > 0
              ? draftProposal
              : fallbackProposal && typeof fallbackProposal === 'object'
                ? fallbackProposal
                : {},
          required_slots_json:
            Object.keys(draftRequiredSlots).length > 0
              ? draftRequiredSlots
              : fallbackRequiredSlots && typeof fallbackRequiredSlots === 'object'
                ? fallbackRequiredSlots
                : {},
        });
      } catch (err) {
        setComposerPlanDraftView(null);
        setError(err instanceof Error ? err.message : 'Failed to load plan draft details');
      } finally {
        setComposerPlanDraftLoading(false);
      }
    },
    [activeThreadId]
  );

  const preparePlanRevisionInComposer = (message: MixChatMessage, draftId: string) => {
    const proposal = getPlanningProposal(message);
    const proposalTitleRaw = proposal && typeof proposal.title === 'string' ? proposal.title.trim() : '';
    const proposalTitle = proposalTitleRaw || `Draft ${draftId.slice(0, 8)}`;
    setComposerPlanRevision({
      draftId,
      sourceMessageId: message.id,
      proposalTitle,
    });
    setForceNewDraft(false);
    setComposerAttachment(null);
    setPendingTimelineResolution(null);
    setComposerPlanDraftView(null);
    setError(null);
    void loadPlanDraftView(draftId, message);
    shouldStickToBottomRef.current = true;
    setIsNearBottom(true);
    window.setTimeout(() => {
      composerRef.current?.focus();
      scrollToBottom('smooth');
    }, 10);
  };

  const attachActiveDraftToComposer = () => {
    if (!activePlanningDraftId) {
      return;
    }
    const latestDraftMessage = [...messages]
      .reverse()
      .find((message) => message.role === 'assistant' && getPlanningDraftId(message) === activePlanningDraftId);
    if (latestDraftMessage) {
      preparePlanRevisionInComposer(latestDraftMessage, activePlanningDraftId);
      window.setTimeout(() => {
        const draftMessageNode = document.querySelector<HTMLElement>(
          `[data-message-id="${latestDraftMessage.id}"]`
        );
        draftMessageNode?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 40);
      return;
    }
    setComposerPlanRevision({
      draftId: activePlanningDraftId,
      sourceMessageId: null,
      proposalTitle: `Draft ${activePlanningDraftId.slice(0, 8)}`,
    });
    setForceNewDraft(false);
    setComposerAttachment(null);
    setPendingTimelineResolution(null);
    setComposerPlanDraftView(null);
    setError(null);
    void loadPlanDraftView(activePlanningDraftId, null);
    window.setTimeout(() => {
      composerRef.current?.focus();
      scrollToBottom('smooth');
    }, 10);
  };

  const reuseTimelineFromClarification = (
    message: MixChatMessage,
    resolution: TimelineResolution | null = null
  ) => {
    const snapshot = getTimelineSnapshotFromAssistantMessage(message);
    if (!snapshot) {
      setError('No timeline snapshot found in this clarification response.');
      return;
    }

    const sourceVersion = versionMap[snapshot.source_version_id];
    let tracks = getTimelineTracksFromVersion(sourceVersion);
    if (tracks.length === 0) {
      tracks = getTracks(message).map((track, index) => ({
        id: track.id,
        track_index: typeof track.track_index === 'number' ? track.track_index : index,
        title: track.title,
        artist: track.artist,
        preview_url: track.preview_url,
        duration_seconds: track.duration_seconds,
      }));
    }
    if (tracks.length === 0) {
      setError('Could not resolve source tracks for the attached timeline.');
      return;
    }

    const changedSegmentIds =
      snapshot.editor_metadata && Array.isArray(snapshot.editor_metadata.changed_segment_ids)
        ? snapshot.editor_metadata.changed_segment_ids.filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0)
        : [];

    let proposalTitle = 'Mix timeline';
    if (sourceVersion && sourceVersion.proposal_json && typeof sourceVersion.proposal_json === 'object') {
      const proposalValue = (sourceVersion.proposal_json as Record<string, unknown>).proposal;
      if (proposalValue && typeof proposalValue === 'object') {
        const titleValue = (proposalValue as Record<string, unknown>).title;
        if (typeof titleValue === 'string' && titleValue.trim()) {
          proposalTitle = titleValue;
        }
      }
    }

    setComposerAttachment({
      sourceVersionId: snapshot.source_version_id,
      sourceMessageId: message.id,
      proposalTitle,
      tracks,
      segments: snapshot.segments,
      changedSegmentIds,
    });
    setComposerPlanRevision(null);
    setComposerPlanDraftView(null);
    setPendingTimelineResolution(resolution);
    setError(null);
  };

  const onComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendPrompt();
    }
  };

  const copyCode = async (copyKey: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCodeByKey((current) => ({ ...current, [copyKey]: true }));
      window.setTimeout(() => {
        setCopiedCodeByKey((current) => {
          if (!current[copyKey]) {
            return current;
          }
          const next = { ...current };
          delete next[copyKey];
          return next;
        });
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to copy output code');
    }
  };

  const selectThread = (threadId: string) => {
    setTimelineEditor(null);
    setComposerAttachment(null);
    setComposerPlanRevision(null);
    setComposerPlanDraftView(null);
    setComposerPlanDraftLoading(false);
    setPendingTimelineResolution(null);
    setActiveThreadId(threadId);
    setMobileThreadsOpen(false);
  };

  if (!chatUiEnabled) {
    return (
      <div className="rounded-2xl border bg-white p-6" style={{ borderColor: `${colors.deepRed}20` }}>
        <h1 className="text-xl font-semibold" style={{ color: colors.deepRed }}>
          AI Chat UI Is Disabled
        </h1>
        <p className="mt-2 text-sm" style={{ color: colors.textDark }}>
          Set <code>VITE_AI_CHAT_UI_ENABLED=true</code> in your environment to enable the new chat-based studio.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-0 w-full overflow-hidden border-y bg-white shadow-sm" style={{ borderColor: `${colors.deepRed}18` }}>
      <div className="flex h-full min-h-0 w-full overflow-hidden">
        <aside
          className={`hidden h-full min-h-0 shrink-0 border-r bg-white transition-[width] duration-200 md:flex md:flex-col ${
            sidebarCollapsed ? 'w-[72px]' : 'w-[320px]'
          }`}
          style={{ borderColor: `${colors.deepRed}15` }}
        >
          <div
            className={`flex items-center border-b px-3 py-2.5 ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}
            style={{ borderColor: `${colors.deepRed}15` }}
          >
            {!sidebarCollapsed && (
              <h2 className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                Mix Chats
              </h2>
            )}
            <div className={`flex items-center gap-1 ${sidebarCollapsed ? 'flex-col' : ''}`}>
              <button
                type="button"
                onClick={createThread}
                className={`inline-flex items-center justify-center gap-1 rounded-md font-semibold text-white ${
                  sidebarCollapsed ? 'h-8 w-8 text-xs' : 'px-2.5 py-1.5 text-xs'
                } ${sidebarCollapsed ? 'order-2' : 'order-1'}`}
                style={{ backgroundColor: colors.deepRed }}
                title="New chat"
              >
                <Plus className="h-3.5 w-3.5" />
                {!sidebarCollapsed && <span>New</span>}
              </button>
              <button
                type="button"
                onClick={() => setSidebarCollapsed((current) => !current)}
                className={`inline-flex h-8 w-8 items-center justify-center rounded-md border text-xs ${
                  sidebarCollapsed ? 'order-1' : 'order-2'
                }`}
                style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            {threadsLoading ? (
              <div className="flex items-center gap-2 p-2 text-xs" style={{ color: colors.textDark }}>
                <Loader2 className="h-4 w-4 animate-spin" /> {!sidebarCollapsed && <span>Loading chats...</span>}
              </div>
            ) : threads.length === 0 ? (
              <p className={`p-2 text-xs ${sidebarCollapsed ? 'text-center' : ''}`} style={{ color: colors.textDark }}>
                {sidebarCollapsed ? '...' : 'No chats yet.'}
              </p>
            ) : (
              threads.map((thread) =>
                sidebarCollapsed ? (
                  <button
                    key={thread.id}
                    type="button"
                    onClick={() => selectThread(thread.id)}
                    className="mb-2 flex w-full flex-col items-center rounded-lg border px-2 py-2 text-center"
                    style={{
                      borderColor: activeThreadId === thread.id ? `${colors.deepRed}50` : `${colors.deepRed}15`,
                      backgroundColor: activeThreadId === thread.id ? colors.softestYellow : 'white',
                    }}
                    title={thread.title}
                  >
                    <span className="text-xs font-semibold" style={{ color: colors.deepRed }}>
                      {getThreadMonogram(thread.title)}
                    </span>
                  </button>
                ) : (
                  <div
                    key={thread.id}
                    className="mb-2 rounded-lg border p-3 transition-all duration-200 hover:shadow-sm"
                    style={{
                      borderColor: activeThreadId === thread.id ? `${colors.deepRed}50` : `${colors.deepRed}15`,
                      backgroundColor: activeThreadId === thread.id ? colors.softestYellow : 'white',
                    }}
                  >
                    <button type="button" onClick={() => selectThread(thread.id)} className="w-full text-left">
                      <p className="line-clamp-2 text-sm font-semibold" style={{ color: colors.deepRed }}>
                        {thread.title}
                      </p>
                      <p className="mt-1 text-[11px]" style={{ color: colors.mediumGray }}>
                        {formatThreadTime(thread.last_message_at || thread.created_at)}
                      </p>
                      {thread.planning_status &&
                        ['collecting', 'draft_ready', 'approved'].includes(thread.planning_status) && (
                        <span
                          className="mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                          style={{ backgroundColor: '#fff4dc', color: '#9a5a00' }}
                        >
                          Planning {thread.planning_round_count ? `• Round ${thread.planning_round_count}` : ''}
                        </span>
                      )}
                    </button>
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => renameThread(thread)}
                        className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px]"
                        style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                      >
                        <Pencil className="h-3 w-3" /> Rename
                      </button>
                      <button
                        type="button"
                        onClick={() => archiveThread(thread.id)}
                        className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px]"
                        style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                      >
                        <Archive className="h-3 w-3" /> Archive
                      </button>
                    </div>
                  </div>
                )
              )
            )}
          </div>
        </aside>

        <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
          <div className="shrink-0 border-b px-3 py-3 md:px-6" style={{ borderColor: `${colors.deepRed}15` }}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <button
                  type="button"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md border md:hidden"
                  style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                  onClick={() => setMobileThreadsOpen(true)}
                  aria-label="Open chats"
                >
                  <Menu className="h-4 w-4" />
                </button>
                <div className="min-w-0">
                  <h1 className="truncate text-base font-semibold md:text-lg" style={{ color: colors.deepRed }}>
                    {activeThread?.title || 'AI Music Studio'}
                  </h1>
                  <p className="truncate text-xs" style={{ color: colors.mediumGray }}>
                    Follow up in the same chat to refine and get modified mixes.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setChatMediaOpen(true)}
                disabled={!activeThreadId}
                className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed, backgroundColor: '#fff' }}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Chat Media
              </button>
            </div>
          </div>

          <div className="relative min-h-0 flex-1">
            <div ref={scrollRef} onScroll={handleMessageScroll} className="h-full space-y-3 overflow-y-auto px-3 py-4 pb-36 md:px-6 md:pb-40">
              {hasMoreMessages && (
                <div className="sticky top-2 z-10 flex justify-center">
                  <button
                    type="button"
                    onClick={() => void loadOlderMessages()}
                    className="rounded-md border px-3 py-1 text-xs"
                    style={{ borderColor: `${colors.deepRed}20`, color: colors.deepRed }}
                  >
                    Load older messages
                  </button>
                </div>
              )}

              {messagesLoading && messages.length === 0 ? (
                <div className="flex items-center gap-2 text-sm" style={{ color: colors.textDark }}>
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading conversation...
                </div>
              ) : messages.length === 0 ? (
                <div className="rounded-xl border p-6 text-center" style={{ borderColor: `${colors.deepRed}15`, color: colors.textDark }}>
                  <MessageSquare className="mx-auto mb-2 h-8 w-8" style={{ color: colors.deepRed }} />
                  Start by sending your first prompt.
                </div>
              ) : (
                messages.map((message) => {
                  const isUser = message.role === 'user';
                  const versionId = getVersionIdFromMessage(message);
                  const proposal = getProposalFromMessage(message);
                  const finalOutput = getFinalOutput(message);
                  const tracks = getTracks(message);
                  const proposalSegments = getProposalSegments(proposal);
                  const version = versionId ? versionMap[versionId] : undefined;
                  const outputCode = !isUser ? getOutputCode(message, version) : null;
                  const versionCode = !isUser ? versionId || version?.id || null : null;
                  const messageKind = getMessageKind(message);
                  const showStandardProposalCard = !isUser && Boolean(proposal) && messageKind !== 'planning_draft_ready';
                  const isAdvancedOpen = expandedAdvanced[message.id] ?? false;
                  const isMixArtifactsCollapsed = collapsedMixArtifacts[message.id] ?? false;
                  const linkedRun = !isUser
                    ? Object.values(runSnapshots).find((run) => run.assistant_message_id === message.id) ?? null
                    : null;
                  const effectiveStatus = !isUser && linkedRun ? linkedRun.status : message.status;
                  const statusMeta = getStatusMeta(effectiveStatus);
                  const liveProgressPercent =
                    !isUser && linkedRun && typeof linkedRun.progress_percent === 'number'
                      ? Math.max(0, Math.min(100, Math.round(linkedRun.progress_percent)))
                      : null;
                  const liveProgressLabel =
                    !isUser && linkedRun && typeof linkedRun.progress_label === 'string'
                      ? linkedRun.progress_label.trim()
                      : '';
                  const liveProgressDetail =
                    !isUser && linkedRun && typeof linkedRun.progress_detail === 'string'
                      ? linkedRun.progress_detail.trim()
                      : '';
                  const showLiveProgress =
                    !isUser &&
                    linkedRun !== null &&
                    (linkedRun.status === 'queued' || linkedRun.status === 'running');
                  const timelineAttachment = isUser ? getTimelineAttachmentFromContent(message.content_json) : null;
                  const timelineResolutionValue = isUser
                    ? (typeof message.content_json?.timeline_resolution === 'string'
                        ? (message.content_json.timeline_resolution as string)
                        : '')
                    : '';
                  const attachmentSegmentCount = timelineAttachment?.segments.length ?? 0;
                  const planningDraftId = !isUser ? getPlanningDraftId(message) : null;
                  const planningQuestions =
                    !isUser && isPlanningQuestionKind(messageKind) ? getPlanningQuestions(message) : [];
                  const planningDetectedSongs =
                    !isUser && isPlanningQuestionKind(messageKind) ? getPlanningDetectedSongs(message) : [];
                  const planningSongSource = !isUser ? getPlanningSongSource(message) : '';
                  const planningSongSourceMeta = !isUser ? getPlanningSongSourceMeta(planningSongSource) : null;
                  const planningConstraintContract = !isUser ? getPlanningConstraintContract(message) : null;
                  const planningConstraintViolations = !isUser ? getPlanningConstraintViolations(message) : [];
                  const contractSongCount =
                    planningConstraintContract && typeof planningConstraintContract.song_count === 'number'
                      ? planningConstraintContract.song_count
                      : null;
                  const contractSegmentCount =
                    planningConstraintContract && typeof planningConstraintContract.segment_count === 'number'
                      ? planningConstraintContract.segment_count
                      : null;
                  const contractTransitionCount =
                    planningConstraintContract && typeof planningConstraintContract.transition_count === 'number'
                      ? planningConstraintContract.transition_count
                      : null;
                  const contractMustInclude =
                    planningConstraintContract && Array.isArray(planningConstraintContract.must_include_songs)
                      ? planningConstraintContract.must_include_songs
                          .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
                          .slice(0, 12)
                      : [];
                  const contractPreferredSequence =
                    planningConstraintContract && Array.isArray(planningConstraintContract.preferred_sequence)
                      ? planningConstraintContract.preferred_sequence
                          .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
                          .slice(0, 12)
                      : [];
                  const contractMirrorSequenceAtEnd =
                    planningConstraintContract && typeof planningConstraintContract.mirror_sequence_at_end === 'boolean'
                      ? planningConstraintContract.mirror_sequence_at_end
                      : false;
                  const planningRetryAfterSeconds =
                    !isUser && typeof message.content_json?.retry_after_seconds === 'number'
                      ? message.content_json.retry_after_seconds
                      : null;
                  const planningRetryLabel =
                    !isUser && typeof message.content_json?.status_label === 'string'
                      ? message.content_json.status_label
                      : '';
                  const planningAnswerState = planningAnswerDrafts[message.id] ?? {
                    selected: {},
                    other: {},
                    submitting: false,
                    error: null,
                  };
                  const planningDraftProposal =
                    !isUser && messageKind === 'planning_draft_ready' ? getPlanningProposal(message) : null;
                  const planResolvedSongs = Array.isArray(planningDraftProposal?.resolved_songs)
                    ? (planningDraftProposal?.resolved_songs as Array<Record<string, unknown>>)
                    : [];
                  const planTimeline = Array.isArray(planningDraftProposal?.provisional_timeline)
                    ? (planningDraftProposal?.provisional_timeline as Array<Record<string, unknown>>)
                    : [];
                  const songResolutionRows =
                    !isUser && Array.isArray(message.content_json?.song_resolution)
                      ? (message.content_json.song_resolution as Array<Record<string, unknown>>)
                      : [];
                  const qualityPayload =
                    !isUser && message.content_json?.quality && typeof message.content_json.quality === 'object'
                      ? (message.content_json.quality as Record<string, unknown>)
                      : null;
                  const qualityScore =
                    qualityPayload && typeof qualityPayload.score === 'number'
                      ? Number(qualityPayload.score)
                      : null;
                  const qualityGrade =
                    qualityPayload && typeof qualityPayload.grade === 'string' ? qualityPayload.grade : '';
                  const clarificationSnapshot =
                    !isUser && messageKind === 'clarification_question'
                      ? getTimelineSnapshotFromAssistantMessage(message)
                      : null;
                  const detectedConflictsRaw = message.content_json?.detected_conflicts;
                  const detectedConflicts = Array.isArray(detectedConflictsRaw)
                    ? detectedConflictsRaw.filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0)
                    : [];
                  const nextStepHint =
                    typeof message.content_json?.next_step_hint === 'string' ? message.content_json.next_step_hint : '';
                  const clarificationQuickActionsRaw = message.content_json?.quick_actions;
                  const clarificationQuickActions = Array.isArray(clarificationQuickActionsRaw)
                    ? clarificationQuickActionsRaw
                        .filter(
                          (entry): entry is Record<string, unknown> =>
                            typeof entry === 'object' && entry !== null
                        )
                        .map((entry) => ({
                          id: typeof entry.id === 'string' ? entry.id : '',
                          label: typeof entry.label === 'string' ? entry.label : '',
                          description:
                            typeof entry.description === 'string' ? entry.description : '',
                        }))
                        .filter(
                          (entry): entry is { id: TimelineResolution; label: string; description: string } =>
                            (entry.id === 'keep_attached_cuts' ||
                              entry.id === 'replan_with_prompt' ||
                              entry.id === 'replace_timeline') &&
                            Boolean(entry.label)
                        )
                    : [];

                  return (
                    <div
                      key={message.id}
                      data-message-id={message.id}
                      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className="max-w-[92%] rounded-2xl border px-4 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition-shadow duration-200 hover:shadow-[0_6px_20px_rgba(0,0,0,0.06)] md:max-w-[86%]"
                        style={{
                          borderColor: isUser ? `${colors.deepRed}35` : `${colors.deepRed}18`,
                          backgroundColor: isUser ? colors.softRed : '#fff',
                        }}
                      >
                        <div className="mb-1 flex items-center gap-2 text-[11px]" style={{ color: colors.mediumGray }}>
                          <span>{isUser ? 'You' : 'IntelliMix'}</span>
                          <span>|</span>
                          <span>{formatMessageTime(message.created_at)}</span>
                          {!isUser && (
                            <span
                              className="inline-flex rounded-full px-2 py-0.5 font-semibold"
                              style={{ backgroundColor: statusMeta.background, color: statusMeta.color }}
                            >
                              {statusMeta.label}
                            </span>
                          )}
                        </div>

                        {timelineAttachment && (
                          <div
                            className="mb-2 rounded-lg border px-3 py-2"
                            style={{ borderColor: `${colors.deepRed}22`, backgroundColor: '#fff9f1' }}
                          >
                            <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: colors.deepRed }}>
                              <Paperclip className="h-3.5 w-3.5" />
                              <span>Timeline attachment</span>
                            </div>
                            <p className="mt-1 text-xs" style={{ color: colors.textDark }}>
                              {attachmentSegmentCount} segment{attachmentSegmentCount === 1 ? '' : 's'} from version{' '}
                              {timelineAttachment.source_version_id.slice(0, 8)}.
                            </p>
                            {timelineResolutionValue &&
                              ['keep_attached_cuts', 'replan_with_prompt', 'replace_timeline'].includes(
                                timelineResolutionValue
                              ) && (
                                <span
                                  className="mt-2 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                                  style={{ backgroundColor: colors.softRed, color: colors.deepRed }}
                                >
                                  Resolution:{' '}
                                  {getTimelineResolutionLabel(timelineResolutionValue as TimelineResolution)}
                                </span>
                              )}
                          </div>
                        )}

                        {message.content_text && (
                          <p className="whitespace-pre-wrap text-sm" style={{ color: colors.textDark }}>
                            {message.content_text}
                          </p>
                        )}
                        {!message.content_text && !isUser && (
                          <p className="whitespace-pre-wrap text-sm" style={{ color: colors.textDark }}>
                            Processing...
                          </p>
                        )}

                        {showLiveProgress && (
                          <div
                            className="mt-3 rounded-xl border px-3 py-2"
                            style={{ borderColor: `${colors.deepRed}20`, backgroundColor: '#fffaf4' }}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                                {liveProgressLabel || 'Audio Engineer Progress'}
                              </p>
                              {liveProgressPercent !== null && (
                                <span className="text-[11px] font-semibold" style={{ color: colors.deepRed }}>
                                  {liveProgressPercent}%
                                </span>
                              )}
                            </div>
                            {liveProgressDetail && (
                              <p className="mt-1 text-xs" style={{ color: colors.textDark }}>
                                {liveProgressDetail}
                              </p>
                            )}
                            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: '#f4dfd5' }}>
                              <div
                                className="h-full rounded-full transition-all duration-500 ease-out"
                                style={{
                                  width: `${liveProgressPercent ?? 12}%`,
                                  backgroundColor: colors.deepRed,
                                }}
                              />
                            </div>
                          </div>
                        )}

                        {!isUser && messageKind === 'planning_waiting_ai' && (
                          <div
                            className="mt-3 rounded-xl border p-3"
                            style={{ borderColor: `${colors.deepRed}24`, backgroundColor: '#fff6e9' }}
                          >
                            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                              Audio Engineer Status
                            </p>
                            <div className="mt-2 inline-flex items-center gap-2 text-xs" style={{ color: colors.textDark }}>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              <span>
                                {planningRetryLabel || 'Retrying due to temporary AI capacity'}
                                {planningRetryAfterSeconds ? ` (${planningRetryAfterSeconds}s)` : ''}
                              </span>
                            </div>
                          </div>
                        )}

                        {!isUser && messageKind === 'planning_constraint_clarification' && (
                          <div
                            className="mt-3 rounded-xl border p-3"
                            style={{ borderColor: `${colors.deepRed}24`, backgroundColor: '#fff6e9' }}
                          >
                            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                              Constraint Clarification
                            </p>
                            {planningConstraintViolations.length > 0 && (
                              <ul className="mt-2 space-y-1 text-xs" style={{ color: colors.textDark }}>
                                {planningConstraintViolations.map((reason, index) => (
                                  <li key={`${message.id}-violation-${index}`}>- {reason}</li>
                                ))}
                              </ul>
                            )}
                            {planningDraftId && (
                              <button
                                type="button"
                                onClick={() => preparePlanRevisionInComposer(message, planningDraftId)}
                                className="mt-2 inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-semibold"
                                style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed, backgroundColor: '#fff' }}
                              >
                                <Pencil className="h-3.5 w-3.5" />
                                Revise Plan
                              </button>
                            )}
                          </div>
                        )}

                        {!isUser && version?.parent_version_id && (
                          <span
                            className="mt-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold"
                            style={{ backgroundColor: colors.softestYellow, color: colors.deepRed }}
                          >
                            Modified from {version.parent_version_id.slice(0, 8)}
                          </span>
                        )}

                        {!isUser && messageKind === 'clarification_question' && (
                          <div
                            className="mt-3 rounded-xl border p-3"
                            style={{ borderColor: `${colors.deepRed}24`, backgroundColor: '#fff6e9' }}
                          >
                            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                              Clarification Needed
                            </p>
                            {detectedConflicts.length > 0 && (
                              <ul className="mt-2 space-y-1 text-xs" style={{ color: colors.textDark }}>
                                {detectedConflicts.map((reason, index) => (
                                  <li key={`${message.id}-conflict-${index}`}>- {reason}</li>
                                ))}
                              </ul>
                            )}
                            {nextStepHint && (
                              <p className="mt-2 text-xs" style={{ color: colors.textDark }}>
                                {nextStepHint}
                              </p>
                            )}
                            {clarificationSnapshot && clarificationQuickActions.length > 0 && (
                              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
                                {clarificationQuickActions.map((action) => (
                                  <button
                                    key={`${message.id}-action-${action.id}`}
                                    type="button"
                                    onClick={() => reuseTimelineFromClarification(message, action.id)}
                                    className="rounded-md border px-2 py-1.5 text-left text-xs font-semibold"
                                    style={{
                                      borderColor:
                                        pendingTimelineResolution === action.id
                                          ? colors.deepRed
                                          : `${colors.deepRed}28`,
                                      color: colors.deepRed,
                                      backgroundColor:
                                        pendingTimelineResolution === action.id ? colors.softRed : '#fff',
                                    }}
                                  >
                                    <span className="block">{action.label}</span>
                                    {action.description && (
                                      <span className="mt-1 block text-[10px]" style={{ color: colors.textDark }}>
                                        {action.description}
                                      </span>
                                    )}
                                  </button>
                                ))}
                              </div>
                            )}
                            {clarificationSnapshot && clarificationQuickActions.length === 0 && (
                              <button
                                type="button"
                                onClick={() => reuseTimelineFromClarification(message)}
                                className="mt-2 inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold"
                                style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed, backgroundColor: '#fff' }}
                              >
                                <Paperclip className="h-3.5 w-3.5" />
                                Reuse attached timeline
                              </button>
                            )}
                          </div>
                        )}

                        {!isUser && planningDraftId && planningQuestions.length > 0 && (
                          <div
                            className="mt-3 rounded-xl border p-3"
                            style={{ borderColor: `${colors.deepRed}20`, backgroundColor: '#fffdf6' }}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                                Planning Questions
                              </p>
                              <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: '#ffe8dc', color: colors.deepRed }}>
                                Draft {planningDraftId.slice(0, 8)}
                              </span>
                            </div>
                            <div className="mt-2 space-y-3">
                              {planningQuestions.map((question) => (
                                <div key={`${message.id}-${question.question_id}`} className="rounded-lg border p-2" style={{ borderColor: `${colors.deepRed}14`, backgroundColor: '#fff' }}>
                                  <p className="text-xs font-semibold" style={{ color: colors.textDark }}>
                                    {question.question}
                                  </p>
                                  {question.question_id === 'songs_set' && (
                                    <div
                                      className="mt-2 rounded-md border px-2 py-1.5 text-xs"
                                      style={{ borderColor: `${colors.deepRed}16`, backgroundColor: '#fff8f1', color: colors.textDark }}
                                    >
                                      <div className="flex flex-wrap items-center justify-between gap-2">
                                        <p className="font-semibold" style={{ color: colors.deepRed }}>
                                          {planningSongSource === 'suggested' || planningSongSource === 'memory'
                                            ? 'Suggested songs'
                                            : 'Detected songs'}
                                        </p>
                                        <div className="flex flex-wrap items-center gap-2">
                                          {planningSongSourceMeta && (
                                            <span
                                              className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                                              style={{ backgroundColor: colors.softRed, color: colors.deepRed }}
                                              title={planningSongSourceMeta.note}
                                            >
                                              Source: {planningSongSourceMeta.label}
                                            </span>
                                          )}
                                          <button
                                            type="button"
                                            onClick={() => void regeneratePlanningSongSuggestions(message)}
                                            disabled={Boolean(planningActionBusy[`${message.id}:regenerate_suggestions`])}
                                            className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold disabled:opacity-60"
                                            style={{ borderColor: `${colors.deepRed}24`, color: colors.deepRed, backgroundColor: '#fff' }}
                                          >
                                            {planningActionBusy[`${message.id}:regenerate_suggestions`] ? (
                                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                              <RotateCcw className="h-3.5 w-3.5" />
                                            )}
                                            Regenerate suggestions
                                          </button>
                                        </div>
                                      </div>
                                      {planningDetectedSongs.length > 0 ? (
                                        <ul className="mt-1 space-y-0.5">
                                          {planningDetectedSongs.map((song, index) => (
                                            <li key={`${message.id}-planning-song-${index}`}>{index + 1}. {song}</li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <p className="mt-1">
                                          No songs detected yet. Use <strong>Add/remove songs</strong> or type your full list in <strong>Other</strong>.
                                        </p>
                                      )}
                                      {planningSongSource === 'suggested' && planningDetectedSongs.length > 0 && (
                                        <p className="mt-1 text-[11px]" style={{ color: colors.mediumGray }}>
                                          Suggested from your artist/track-count prompt. Confirm or edit before continuing.
                                        </p>
                                      )}
                                    </div>
                                  )}
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {question.options.map((option) => {
                                      const active = planningAnswerState.selected[question.question_id] === option.id;
                                      return (
                                        <button
                                          key={`${question.question_id}-${option.id}`}
                                          type="button"
                                          onClick={() => updatePlanningOption(message.id, question.question_id, option.id)}
                                          className="rounded-full border px-2 py-1 text-[11px] font-semibold transition-colors"
                                          style={{
                                            borderColor: active ? colors.deepRed : `${colors.deepRed}26`,
                                            backgroundColor: active ? colors.softRed : '#fff',
                                            color: colors.deepRed,
                                          }}
                                        >
                                          {option.label}
                                        </button>
                                      );
                                    })}
                                  </div>
                                  {question.allow_other && (
                                    <div className="mt-2">
                                      <input
                                        value={planningAnswerState.other[question.question_id] || ''}
                                        onChange={(event) =>
                                          updatePlanningOtherText(message.id, question.question_id, event.target.value)
                                        }
                                        placeholder="Other (optional)"
                                        className="w-full rounded-md border px-2 py-1.5 text-xs focus:outline-none focus:ring-2"
                                        style={{ borderColor: `${colors.deepRed}22`, color: colors.textDark }}
                                      />
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                            {planningAnswerState.error && (
                              <p className="mt-2 text-xs" style={{ color: colors.brightRed }}>
                                {planningAnswerState.error}
                              </p>
                            )}
                            <button
                              type="button"
                              onClick={() => void submitPlanningAnswers(message)}
                              disabled={planningAnswerState.submitting}
                              className="mt-3 inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                              style={{ backgroundColor: colors.deepRed }}
                            >
                              {planningAnswerState.submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                              Submit answers
                            </button>
                          </div>
                        )}

                        {!isUser && planningDraftId && planningDraftProposal && (
                          <div
                            className="mt-3 rounded-xl border p-3"
                            style={{ borderColor: `${colors.deepRed}20`, backgroundColor: '#fffdf6' }}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                                Plan Draft Ready
                              </p>
                              {planningSongSourceMeta && (
                                <span
                                  className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                                  style={{ backgroundColor: colors.softRed, color: colors.deepRed }}
                                  title={planningSongSourceMeta.note}
                                >
                                  Song source: {planningSongSourceMeta.label}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-sm font-semibold" style={{ color: colors.textDark }}>
                              {typeof planningDraftProposal.title === 'string' && planningDraftProposal.title.trim()
                                ? planningDraftProposal.title
                                : 'Guided Plan Draft'}
                            </p>
                            <p className="mt-1 text-xs" style={{ color: colors.textDark }}>
                              {typeof planningDraftProposal.summary === 'string' && planningDraftProposal.summary.trim()
                                ? planningDraftProposal.summary
                                : 'Review and approve this plan to start rendering.'}
                            </p>
                            <div className="mt-2 grid grid-cols-1 gap-2 text-xs md:grid-cols-3">
                              <div className="rounded border px-2 py-1.5" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fff' }}>
                                <p className="font-semibold" style={{ color: colors.deepRed }}>Target Duration</p>
                                <p style={{ color: colors.textDark }}>
                                  {typeof planningDraftProposal.target_duration_seconds === 'number'
                                    ? `${planningDraftProposal.target_duration_seconds}s`
                                    : 'Auto'}
                                </p>
                              </div>
                              <div className="rounded border px-2 py-1.5" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fff' }}>
                                <p className="font-semibold" style={{ color: colors.deepRed }}>Energy Curve</p>
                                <p style={{ color: colors.textDark }}>
                                  {typeof planningDraftProposal.energy_curve === 'string'
                                    ? planningDraftProposal.energy_curve
                                    : 'Balanced'}
                                </p>
                              </div>
                              <div className="rounded border px-2 py-1.5" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fff' }}>
                                <p className="font-semibold" style={{ color: colors.deepRed }}>Use Case</p>
                                <p style={{ color: colors.textDark }}>
                                  {typeof planningDraftProposal.use_case === 'string'
                                    ? planningDraftProposal.use_case
                                    : 'General listening'}
                                </p>
                              </div>
                            </div>

                            {(contractSongCount !== null ||
                              contractSegmentCount !== null ||
                              contractTransitionCount !== null ||
                              contractMustInclude.length > 0 ||
                              contractPreferredSequence.length > 0) && (
                              <div className="mt-2 rounded border p-2" style={{ borderColor: `${colors.deepRed}14`, backgroundColor: '#fff' }}>
                                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                                  Constraint Contract
                                </p>
                                <div className="mt-1 space-y-1 text-xs" style={{ color: colors.textDark }}>
                                  {contractSongCount !== null && <p>Songs: {contractSongCount}</p>}
                                  {contractSegmentCount !== null && <p>Segments: {contractSegmentCount}</p>}
                                  {contractTransitionCount !== null && <p>Transitions: {contractTransitionCount}</p>}
                                  {contractMustInclude.length > 0 && <p>Must include: {contractMustInclude.join(', ')}</p>}
                                  {contractPreferredSequence.length > 0 && (
                                    <p>
                                      Sequence: {contractPreferredSequence.join(' -> ')}
                                      {contractMirrorSequenceAtEnd ? ' (mirror at ending)' : ''}
                                    </p>
                                  )}
                                </div>
                              </div>
                            )}

                            {planningConstraintViolations.length > 0 && (
                              <div className="mt-2 rounded border p-2" style={{ borderColor: `${colors.brightRed}45`, backgroundColor: '#fff7f7' }}>
                                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.brightRed }}>
                                  Resolve Before Approve
                                </p>
                                <ul className="mt-1 space-y-1 text-xs" style={{ color: colors.textDark }}>
                                  {planningConstraintViolations.map((reason, index) => (
                                    <li key={`${message.id}-draft-violation-${index}`}>- {reason}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {planResolvedSongs.length > 0 && (
                              <div className="mt-2 rounded border p-2" style={{ borderColor: `${colors.deepRed}14`, backgroundColor: '#fff' }}>
                                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                                  Resolved Songs
                                </p>
                                <div className="mt-1 space-y-1 text-xs" style={{ color: colors.textDark }}>
                                  {planResolvedSongs.map((item, index) => (
                                    <div key={`${message.id}-song-${index}`}>
                                      {String(item.matched_track || item.requested_song || `Song ${index + 1}`)}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {planTimeline.length > 0 && (
                              <div className="mt-2 rounded border p-2" style={{ borderColor: `${colors.deepRed}14`, backgroundColor: '#fff' }}>
                                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                                  Provisional Timeline
                                </p>
                                <div className="mt-1 max-h-40 overflow-y-auto space-y-1 pr-1 text-xs" style={{ color: colors.textDark }}>
                                  {planTimeline.map((item, index) => (
                                    <div key={`${message.id}-timeline-${index}`} className="grid grid-cols-[auto,1fr,auto] gap-2">
                                      <span>#{String(item.segment_index || index + 1)}</span>
                                      <span className="truncate">{String(item.song || 'Song')}</span>
                                      <span>
                                        {String(item.start_seconds ?? 0)}s - {String(item.end_seconds ?? 0)}s
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            <div className="mt-3 flex flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => void submitPlanningAction(message, planningDraftId, 'approve_plan')}
                                disabled={Boolean(planningActionBusy[`${message.id}:approve_plan`]) || planningConstraintViolations.length > 0}
                                className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                                style={{ backgroundColor: colors.deepRed }}
                              >
                                {planningActionBusy[`${message.id}:approve_plan`] ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Send className="h-3.5 w-3.5" />
                                )}
                                Approve Plan
                              </button>
                              <button
                                type="button"
                                onClick={() => preparePlanRevisionInComposer(message, planningDraftId)}
                                className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
                                style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed, backgroundColor: '#fff' }}
                              >
                                <Pencil className="h-3.5 w-3.5" />
                                Revise Plan
                              </button>
                            </div>
                          </div>
                        )}

                        {showStandardProposalCard && proposal && (
                          <div className="mt-3 rounded-xl border p-3" style={{ borderColor: `${colors.deepRed}14`, backgroundColor: colors.softestYellow }}>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold" style={{ color: colors.deepRed }}>
                                {(proposal.title as string) || 'Engineer Proposal'}
                              </p>
                              {qualityScore !== null && (
                                <span
                                  className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                                  style={{ backgroundColor: '#fff', color: colors.deepRed }}
                                  title={qualityGrade ? `Quality grade ${qualityGrade}` : 'Quality score'}
                                >
                                  Quality {qualityScore.toFixed(1)}{qualityGrade ? ` • ${qualityGrade}` : ''}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-xs" style={{ color: colors.textDark }}>
                              {(proposal.mixing_rationale as string) || 'Mix draft ready for review.'}
                            </p>

                            <button
                              type="button"
                              onClick={() => toggleAdvanced(message.id)}
                              className="mt-2 inline-flex items-center gap-1 text-xs font-semibold"
                              style={{ color: colors.deepRed }}
                            >
                              {isAdvancedOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                              Mix Details
                            </button>
                            {versionId && proposalSegments.length > 0 && (
                              <button
                                type="button"
                                onClick={() => openTimelineEditor(versionId, message)}
                                className="ml-2 mt-2 inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold"
                                style={{ borderColor: `${colors.deepRed}30`, color: colors.deepRed, backgroundColor: '#fff' }}
                              >
                                Edit Timeline
                              </button>
                            )}

                            {isAdvancedOpen && versionId && (
                              <div className="mt-3 rounded-lg border" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fffdf8' }}>
                                <button
                                  type="button"
                                  onClick={() => toggleMixArtifacts(message.id)}
                                  className="flex w-full items-center justify-between border-b px-3 py-2 text-xs font-semibold"
                                  style={{ borderColor: `${colors.deepRed}14`, color: colors.deepRed }}
                                >
                                  <span>Source Tracks & Timeline</span>
                                  {isMixArtifactsCollapsed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
                                </button>

                                {!isMixArtifactsCollapsed && (
                                  <div>
                                    {tracks.length > 0 && (
                                      <div className="p-2">
                                        <p
                                          className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wide"
                                          style={{ color: colors.deepRed }}
                                        >
                                          Source Tracks
                                        </p>
                                        <div className="space-y-2">
                                          {tracks.map((track, index) => (
                                            <div
                                              key={`${track.id || 't'}-${index}`}
                                              className="rounded border p-2"
                                              style={{ borderColor: `${colors.deepRed}12`, backgroundColor: '#fff' }}
                                            >
                                              <p className="text-xs font-semibold" style={{ color: colors.deepRed }}>
                                                {track.title || `Track ${index + 1}`}
                                              </p>
                                              {track.artist && (
                                                <p className="mb-1 text-[11px]" style={{ color: colors.mediumGray }}>
                                                  {track.artist}
                                                </p>
                                              )}
                                              {track.preview_url && (
                                                <StudioAudioPlayer
                                                  compact
                                                  src={getAuthenticatedFileUrl(track.preview_url)}
                                                  preload="none"
                                                />
                                              )}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {proposalSegments.length > 0 && (
                                      <div
                                        className="p-2"
                                        style={{ borderTop: tracks.length > 0 ? `1px solid ${colors.deepRed}14` : 'none' }}
                                      >
                                        <p
                                          className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wide"
                                          style={{ color: colors.deepRed }}
                                        >
                                          Timeline Segments
                                        </p>
                                        <div className="overflow-hidden rounded border" style={{ borderColor: `${colors.deepRed}15` }}>
                                          {proposalSegments.map((segment, index) => (
                                            <div
                                            key={`${segment.id}-${index}`}
                                            className="grid grid-cols-1 gap-2 border-b p-2 text-xs md:grid-cols-4"
                                            style={{ borderColor: `${colors.deepRed}10`, backgroundColor: index % 2 === 0 ? '#fff' : '#fffaf1' }}
                                          >
                                            <span style={{ color: colors.textDark }}>
                                              {segment.segment_name || `Segment ${index + 1}`}
                                            </span>
                                            <span style={{ color: colors.textDark }}>Start: {(segment.start_ms / 1000).toFixed(2)}s</span>
                                            <span style={{ color: colors.textDark }}>End: {(segment.end_ms / 1000).toFixed(2)}s</span>
                                            <span style={{ color: colors.textDark }}>
                                                Crossfade: {Number(segment.crossfade_after_seconds || 0).toFixed(1)}s
                                              </span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}

                            {songResolutionRows.length > 0 && (
                              <div
                                className="mt-3 rounded-lg border p-2"
                                style={{ borderColor: `${colors.deepRed}14`, backgroundColor: '#fff' }}
                              >
                                <p
                                  className="text-[11px] font-semibold uppercase tracking-wide"
                                  style={{ color: colors.deepRed }}
                                >
                                  Song Resolution
                                </p>
                                <div className="mt-1 space-y-1 text-xs" style={{ color: colors.textDark }}>
                                  {songResolutionRows.map((row, index) => {
                                    const requested = String(row.requested_song || `Requested ${index + 1}`);
                                    const resolved = String(row.resolved_track || requested);
                                    const fallback = Boolean(row.resolved_with_fallback);
                                    return (
                                      <div key={`${message.id}-song-resolution-${index}`} className="rounded border px-2 py-1" style={{ borderColor: `${colors.deepRed}10` }}>
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                          <span>
                                            {requested}
                                            {' -> '}
                                            {resolved}
                                          </span>
                                          {fallback && (
                                            <span
                                              className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                                              style={{ backgroundColor: '#fff4dc', color: '#9a5a00' }}
                                            >
                                              Fallback
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {finalOutput.mp3_url && (
                              <div className="mt-3 space-y-2">
                                {(outputCode || versionCode) && (
                                  <div
                                    className="space-y-1 rounded-md border px-2 py-1.5 text-xs"
                                    style={{ borderColor: `${colors.deepRed}20`, backgroundColor: '#fff' }}
                                  >
                                    {outputCode && (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-semibold" style={{ color: colors.deepRed }}>
                                          Output code:
                                        </span>
                                        <code className="rounded bg-[#fff4ea] px-1.5 py-0.5 font-mono text-[11px]" style={{ color: colors.textDark }}>
                                          {outputCode}
                                        </code>
                                        <button
                                          type="button"
                                          onClick={() => void copyCode(`${message.id}:output`, outputCode)}
                                          className="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-semibold"
                                          style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                                        >
                                          {copiedCodeByKey[`${message.id}:output`] ? (
                                            <>
                                              <Check className="h-3 w-3" />
                                              Copied
                                            </>
                                          ) : (
                                            <>
                                              <Copy className="h-3 w-3" />
                                              Copy
                                            </>
                                          )}
                                        </button>
                                      </div>
                                    )}

                                    {versionCode && (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-semibold" style={{ color: colors.deepRed }}>
                                          Version code:
                                        </span>
                                        <code className="rounded bg-[#fff4ea] px-1.5 py-0.5 font-mono text-[11px]" style={{ color: colors.textDark }}>
                                          {versionCode}
                                        </code>
                                        <button
                                          type="button"
                                          onClick={() => void copyCode(`${message.id}:version`, versionCode)}
                                          className="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-semibold"
                                          style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                                        >
                                          {copiedCodeByKey[`${message.id}:version`] ? (
                                            <>
                                              <Check className="h-3 w-3" />
                                              Copied
                                            </>
                                          ) : (
                                            <>
                                              <Copy className="h-3 w-3" />
                                              Copy
                                            </>
                                          )}
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                )}

                                <StudioAudioPlayer src={getAuthenticatedFileUrl(finalOutput.mp3_url)} />
                                <div className="flex flex-wrap gap-2 text-xs">
                                  <a
                                    href={getAuthenticatedFileUrl(finalOutput.mp3_url)}
                                    download={outputCode ? `intellimix-${outputCode.slice(0, 8)}.mp3` : undefined}
                                    className="rounded border px-2 py-1"
                                    style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                                  >
                                    Download MP3
                                  </a>
                                  {finalOutput.wav_url && (
                                    <a
                                      href={getAuthenticatedFileUrl(finalOutput.wav_url)}
                                      download={outputCode ? `intellimix-${outputCode.slice(0, 8)}.wav` : undefined}
                                      className="rounded border px-2 py-1"
                                      style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                                    >
                                      Download WAV
                                    </a>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {!isNearBottom && messages.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  shouldStickToBottomRef.current = true;
                  setIsNearBottom(true);
                  scrollToBottom('smooth');
                }}
                className="absolute bottom-4 right-4 inline-flex h-10 w-10 items-center justify-center rounded-full border bg-white shadow-md transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
                style={{ borderColor: `${colors.deepRed}30`, color: colors.deepRed }}
                aria-label="Jump to latest message"
              >
                <ArrowDown className="h-5 w-5" />
              </button>
            )}
          </div>

          <div
            className="relative z-20 border-t bg-white/95 px-3 pt-3 shadow-[0_-8px_24px_rgba(0,0,0,0.05)] backdrop-blur-sm md:px-6"
            style={{ borderColor: `${colors.deepRed}15`, paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom))' }}
          >
            <div className="pointer-events-none absolute inset-x-0 -top-4 h-4 bg-gradient-to-t from-white to-transparent" />
            {error && (
              <p className="mb-2 text-xs" style={{ color: colors.brightRed }}>
                {error}
              </p>
            )}
            {hasActivePlanningDraft && activePlanningDraftId && (
              <div
                className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2"
                style={{ borderColor: `${colors.deepRed}22`, backgroundColor: forceNewDraft ? '#fff4f2' : colors.softestYellow }}
              >
                <span className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: colors.deepRed }}>
                  <Paperclip className="h-3.5 w-3.5" />
                  Active Plan Draft {activePlanningDraftId.slice(0, 8)} {activePlanningStatus ? `• ${activePlanningStatus}` : ''}
                </span>
                <button
                  type="button"
                  onClick={attachActiveDraftToComposer}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed, backgroundColor: '#fff' }}
                >
                  View draft
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setForceNewDraft((current) => !current);
                    if (!forceNewDraft) {
                      setComposerPlanRevision(null);
                      setComposerPlanDraftView(null);
                      setComposerPlanDraftLoading(false);
                    }
                  }}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed, backgroundColor: '#fff' }}
                >
                  {forceNewDraft ? 'Use active draft' : 'Detach (start new draft)'}
                </button>
              </div>
            )}
            {composerAttachment && (
              <div
                className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2"
                style={{ borderColor: `${colors.deepRed}22`, backgroundColor: colors.softestYellow }}
              >
                <div className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: colors.deepRed }}>
                  <Paperclip className="h-3.5 w-3.5" />
                  <span>
                    Timeline - {composerAttachment.proposalTitle} - {composerAttachment.segments.length} segment
                    {composerAttachment.segments.length === 1 ? '' : 's'}
                  </span>
                </div>
                {pendingTimelineResolution && (
                  <span
                    className="inline-flex rounded-full px-2 py-1 text-[11px] font-semibold"
                    style={{ backgroundColor: colors.softRed, color: colors.deepRed }}
                  >
                    {getTimelineResolutionLabel(pendingTimelineResolution)}
                  </span>
                )}
                <button
                  type="button"
                  onClick={openAttachmentEditor}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed }}
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={openAttachmentEditor}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed }}
                >
                  View
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setComposerAttachment(null);
                    setPendingTimelineResolution(null);
                  }}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed }}
                >
                  Remove
                </button>
              </div>
            )}
            {composerPlanRevision && (
              <div
                className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2"
                style={{ borderColor: `${colors.deepRed}22`, backgroundColor: colors.softestYellow }}
              >
                <div className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: colors.deepRed }}>
                  <Paperclip className="h-3.5 w-3.5" />
                  <span>
                    Plan draft - {composerPlanRevision.proposalTitle} - {composerPlanRevision.draftId.slice(0, 8)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => void loadPlanDraftView(composerPlanRevision.draftId, null)}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed }}
                  disabled={composerPlanDraftLoading}
                >
                  {composerPlanDraftLoading ? 'Loading...' : 'Refresh'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setComposerPlanRevision(null);
                    setComposerPlanDraftView(null);
                    setComposerPlanDraftLoading(false);
                  }}
                  className="inline-flex items-center rounded border px-2 py-1 text-[11px] font-semibold"
                  style={{ borderColor: `${colors.deepRed}28`, color: colors.deepRed }}
                >
                  Remove
                </button>
              </div>
            )}
            {composerPlanRevision && (
              <div
                className="mb-2 rounded-lg border px-3 py-2"
                style={{ borderColor: `${colors.deepRed}20`, backgroundColor: '#fffdf6' }}
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                  Draft Snapshot
                </p>
                {composerPlanDraftLoading && (
                  <div className="mt-2 inline-flex items-center gap-2 text-xs" style={{ color: colors.textDark }}>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Loading draft details...
                  </div>
                )}
                {!composerPlanDraftLoading && composerPlanDraftView && (
                  <div className="mt-2 space-y-2 text-xs" style={{ color: colors.textDark }}>
                    <p>
                      Status: <strong>{composerPlanDraftView.status || 'collecting'}</strong>
                      {' • '}
                      Round {composerPlanDraftView.round_count}/{composerPlanDraftView.max_rounds}
                    </p>
                    {composerPlanDraftView.updated_at && (
                      <p>Updated: {formatMessageTime(composerPlanDraftView.updated_at)}</p>
                    )}
                    {Array.isArray(composerPlanDraftView.pending_clarifications_json) &&
                      composerPlanDraftView.pending_clarifications_json.length > 0 && (
                        <div className="rounded border p-2" style={{ borderColor: `${colors.deepRed}18`, backgroundColor: '#fff' }}>
                          <p className="font-semibold" style={{ color: colors.deepRed }}>
                            Pending clarifications
                          </p>
                          <ul className="mt-1 space-y-1">
                            {composerPlanDraftView.pending_clarifications_json
                              .filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0)
                              .slice(0, 4)
                              .map((entry, index) => (
                                <li key={`${composerPlanRevision.draftId}-clarify-${index}`}>- {entry}</li>
                              ))}
                          </ul>
                        </div>
                      )}
                    {(() => {
                      const proposal = composerPlanDraftView.proposal_json;
                      const resolvedSongsRaw = Array.isArray(proposal?.['resolved_songs'])
                        ? (proposal['resolved_songs'] as unknown[])
                        : [];
                      const resolvedSongs = resolvedSongsRaw
                        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
                        .map((item) =>
                          String(item.matched_track || item.requested_song || '').trim()
                        )
                        .filter((item) => item.length > 0)
                        .slice(0, 8);
                      const timelineRaw = Array.isArray(proposal?.['provisional_timeline'])
                        ? (proposal['provisional_timeline'] as unknown[])
                        : [];
                      const timeline = timelineRaw
                        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
                        .slice(0, 5);
                      if (resolvedSongs.length === 0 && timeline.length === 0) {
                        const questionCount = Array.isArray(composerPlanDraftView.questions_json)
                          ? composerPlanDraftView.questions_json.length
                          : 0;
                        return (
                          <p>
                            This draft is still collecting context.
                            {questionCount > 0 ? ` ${questionCount} planning question(s) are waiting for answers.` : ''}
                          </p>
                        );
                      }
                      return (
                        <>
                          {resolvedSongs.length > 0 && (
                            <div className="rounded border p-2" style={{ borderColor: `${colors.deepRed}18`, backgroundColor: '#fff' }}>
                              <p className="font-semibold" style={{ color: colors.deepRed }}>
                                Resolved songs
                              </p>
                              <ul className="mt-1 space-y-1">
                                {resolvedSongs.map((song, index) => (
                                  <li key={`${composerPlanRevision.draftId}-song-${index}`}>{index + 1}. {song}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {timeline.length > 0 && (
                            <div className="rounded border p-2" style={{ borderColor: `${colors.deepRed}18`, backgroundColor: '#fff' }}>
                              <p className="font-semibold" style={{ color: colors.deepRed }}>
                                Timeline preview
                              </p>
                              <div className="mt-1 space-y-1">
                                {timeline.map((item, index) => (
                                  <p key={`${composerPlanRevision.draftId}-timeline-${index}`}>
                                    #{String(item.segment_index ?? index + 1)} {String(item.song || 'Song')}
                                    {' • '}
                                    {String(item.start_seconds ?? 0)}s - {String(item.end_seconds ?? 0)}s
                                  </p>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                )}
                {!composerPlanDraftLoading && !composerPlanDraftView && (
                  <p className="mt-2 text-xs" style={{ color: colors.mediumGray }}>
                    Draft details are not loaded yet. Click Refresh.
                  </p>
                )}
              </div>
            )}
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.mediumGray }}>
              {composerPlanRevision
                ? 'Revising active plan in this chat'
                : forceNewDraft
                  ? 'Starting a new plan draft'
                  : hasActivePlanningDraft
                    ? 'Continuing active plan draft'
                    : 'Refining latest mix in this chat'}
            </p>
            <div className="flex flex-col gap-2 md:flex-row md:items-end">
              <textarea
                ref={composerRef}
                value={composer}
                onChange={(event) => setComposer(event.target.value)}
                onKeyDown={onComposerKeyDown}
                placeholder={
                  composerPlanRevision
                    ? 'Describe the plan changes you want...'
                    : forceNewDraft
                      ? 'Describe the new mix brief you want...'
                    : 'Describe the mix change you want...'
                }
                className="min-h-[56px] w-full resize-none rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 md:flex-1"
                style={{ borderColor: `${colors.deepRed}25`, color: colors.textDark }}
                disabled={!activeThreadId || sending}
              />
              <button
                type="button"
                onClick={() => void sendPrompt()}
                disabled={!activeThreadId || sending || (!composer.trim() && !composerAttachment)}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 md:self-auto"
                style={{ backgroundColor: colors.deepRed }}
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Send
              </button>
            </div>
          </div>
        </section>
      </div>

      {chatMediaOpen && (
        <div className="absolute inset-0 z-30">
          <button
            type="button"
            className="absolute inset-0 bg-black/35"
            onClick={() => setChatMediaOpen(false)}
            aria-label="Close chat media panel"
          />
          <aside className="absolute inset-y-0 right-0 flex w-[96vw] max-w-[520px] flex-col border-l bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-3 border-b px-4 py-3" style={{ borderColor: `${colors.deepRed}15` }}>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                  Chat Media
                </p>
                <h3 className="line-clamp-1 text-sm font-semibold" style={{ color: colors.textDark }}>
                  {activeThread?.title || 'Current chat'}
                </h3>
                <p className="mt-1 text-[11px]" style={{ color: colors.mediumGray }}>
                  Downloaded songs and generated outputs for this chat.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setChatMediaOpen(false)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border px-3 py-2" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fff9f2' }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                    Downloaded songs
                  </p>
                  <p className="mt-1 text-lg font-semibold" style={{ color: colors.textDark }}>
                    {chatMedia.downloadedTracks.length}
                  </p>
                </div>
                <div className="rounded-lg border px-3 py-2" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fff9f2' }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                    Generated outputs
                  </p>
                  <p className="mt-1 text-lg font-semibold" style={{ color: colors.textDark }}>
                    {chatMedia.outputs.length}
                  </p>
                </div>
              </div>

              <section className="rounded-xl border p-3" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fffefb' }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                  Downloaded Songs
                </p>
                {chatMedia.downloadedTracks.length === 0 ? (
                  <p className="mt-2 text-xs" style={{ color: colors.mediumGray }}>
                    No downloaded source tracks detected yet for this chat.
                  </p>
                ) : (
                  <div className="mt-2 space-y-2">
                    {chatMedia.downloadedTracks.map((track) => (
                      <div key={track.key} className="rounded-lg border p-2" style={{ borderColor: `${colors.deepRed}12`, backgroundColor: '#fff' }}>
                        <p className="text-xs font-semibold" style={{ color: colors.deepRed }}>
                          {track.title}
                        </p>
                        <p className="mb-1 text-[11px]" style={{ color: colors.mediumGray }}>
                          {track.artist}
                          {typeof track.duration_seconds === 'number' ? ` • ${Math.round(track.duration_seconds)}s` : ''}
                        </p>
                        {track.preview_url && (
                          <>
                            <StudioAudioPlayer compact src={getAuthenticatedFileUrl(track.preview_url)} preload="none" />
                            <div className="mt-2 flex flex-wrap gap-2">
                              <a
                                href={getAuthenticatedFileUrl(track.preview_url)}
                                target="_blank"
                                rel="noreferrer"
                                className="rounded border px-2 py-1 text-[11px] font-semibold"
                                style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                              >
                                Open
                              </a>
                              <a
                                href={getAuthenticatedFileUrl(track.preview_url)}
                                download
                                className="rounded border px-2 py-1 text-[11px] font-semibold"
                                style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                              >
                                Download
                              </a>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border p-3" style={{ borderColor: `${colors.deepRed}15`, backgroundColor: '#fffefb' }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                  Generated Outputs
                </p>
                {chatMedia.outputs.length === 0 ? (
                  <p className="mt-2 text-xs" style={{ color: colors.mediumGray }}>
                    No generated outputs yet in this chat.
                  </p>
                ) : (
                  <div className="mt-2 space-y-2">
                    {chatMedia.outputs.map((output) => (
                      <div
                        key={output.version_id}
                        className="rounded-lg border p-2"
                        style={{ borderColor: `${colors.deepRed}12`, backgroundColor: '#fff' }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-xs font-semibold" style={{ color: colors.deepRed }}>
                              {output.title}
                            </p>
                            <p className="text-[11px]" style={{ color: colors.mediumGray }}>
                              {formatThreadTime(output.created_at)}
                            </p>
                          </div>
                          <span
                            className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                            style={{ backgroundColor: '#fff1e8', color: colors.deepRed }}
                          >
                            v {output.version_code.slice(0, 8)}
                          </span>
                        </div>
                        <div className="mt-1 rounded border px-2 py-1 text-[11px]" style={{ borderColor: `${colors.deepRed}16` }}>
                          <span className="font-semibold" style={{ color: colors.deepRed }}>
                            Output code:
                          </span>{' '}
                          <code style={{ color: colors.textDark }}>{output.output_code}</code>
                        </div>
                        {output.mp3_url && (
                          <div className="mt-2">
                            <StudioAudioPlayer compact src={getAuthenticatedFileUrl(output.mp3_url)} preload="none" />
                          </div>
                        )}
                        <div className="mt-2 flex flex-wrap gap-2">
                          {output.mp3_url && (
                            <a
                              href={getAuthenticatedFileUrl(output.mp3_url)}
                              download={`intellimix-${output.output_code.slice(0, 8)}.mp3`}
                              className="rounded border px-2 py-1 text-[11px] font-semibold"
                              style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                            >
                              Download MP3
                            </a>
                          )}
                          {output.wav_url && (
                            <a
                              href={getAuthenticatedFileUrl(output.wav_url)}
                              download={`intellimix-${output.output_code.slice(0, 8)}.wav`}
                              className="rounded border px-2 py-1 text-[11px] font-semibold"
                              style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                            >
                              Download WAV
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </aside>
        </div>
      )}

      <TimelineEditorPanel
        open={Boolean(timelineEditor && timelineEditor.segments.length > 0)}
        title={timelineEditor?.proposalTitle || 'Mix timeline'}
        tracks={timelineEditor?.tracks ?? []}
        segments={timelineEditor?.segments ?? []}
        onClose={() => setTimelineEditor(null)}
        onAttach={attachTimelineToComposer}
      />

      {mobileThreadsOpen && (
        <div className="absolute inset-0 z-40 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/35"
            onClick={() => setMobileThreadsOpen(false)}
            aria-label="Close chat drawer"
          />
          <aside className="absolute inset-y-0 left-0 flex w-[88vw] max-w-[320px] flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-3 py-3" style={{ borderColor: `${colors.deepRed}15` }}>
              <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                Mix Chats
              </h2>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={createThread}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-white"
                  style={{ backgroundColor: colors.deepRed }}
                  aria-label="New chat"
                >
                  <Plus className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setMobileThreadsOpen(false)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                  style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {threadsLoading ? (
                <div className="flex items-center gap-2 p-2 text-sm" style={{ color: colors.textDark }}>
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading chats...
                </div>
              ) : threads.length === 0 ? (
                <p className="p-2 text-sm" style={{ color: colors.textDark }}>
                  No chats yet.
                </p>
              ) : (
                threads.map((thread) => (
                  <div
                    key={thread.id}
                    className="mb-2 rounded-lg border p-3 transition-all duration-200 hover:shadow-sm"
                    style={{
                      borderColor: activeThreadId === thread.id ? `${colors.deepRed}50` : `${colors.deepRed}15`,
                      backgroundColor: activeThreadId === thread.id ? colors.softestYellow : 'white',
                    }}
                  >
                    <button type="button" onClick={() => selectThread(thread.id)} className="w-full text-left">
                      <p className="line-clamp-2 text-sm font-semibold" style={{ color: colors.deepRed }}>
                        {thread.title}
                      </p>
                      <p className="mt-1 text-[11px]" style={{ color: colors.mediumGray }}>
                        {formatThreadTime(thread.last_message_at || thread.created_at)}
                      </p>
                      {thread.planning_status &&
                        ['collecting', 'draft_ready', 'approved'].includes(thread.planning_status) && (
                        <span
                          className="mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                          style={{ backgroundColor: '#fff4dc', color: '#9a5a00' }}
                        >
                          Planning {thread.planning_round_count ? `• Round ${thread.planning_round_count}` : ''}
                        </span>
                      )}
                    </button>
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => renameThread(thread)}
                        className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px]"
                        style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                      >
                        <Pencil className="h-3 w-3" /> Rename
                      </button>
                      <button
                        type="button"
                        onClick={() => archiveThread(thread.id)}
                        className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px]"
                        style={{ borderColor: `${colors.deepRed}25`, color: colors.deepRed }}
                      >
                        <Archive className="h-3 w-3" /> Archive
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}


