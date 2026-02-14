import logging
import os
import re
import shutil
import threading
import time
import uuid
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from flask import Flask, Response, jsonify, request, send_file, stream_with_context
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
jwt = JWTManager()

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GENERATION_TYPES = {
    "ai_parody",
    "audio_mix",
    "video_download",
    "audio_download",
}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    generations = db.relationship("GenerationJob", back_populates="user", cascade="all, delete-orphan")
    mix_sessions = db.relationship("MixSession", back_populates="user", cascade="all, delete-orphan")
    mix_chat_threads = db.relationship("MixChatThread", back_populates="user", cascade="all, delete-orphan")
    mix_memory = db.relationship(
        "MixUserMemory",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


class GenerationJob(db.Model):
    __tablename__ = "generation_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    generation_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="processing", index=True)
    input_payload = db.Column(db.JSON, nullable=False, default=dict)
    output_url = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="generations")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "generation_type": self.generation_type,
            "status": self.status,
            "input_payload": self.input_payload,
            "output_url": self.output_url,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class MixSession(db.Model):
    __tablename__ = "mix_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="planning", index=True)
    planner_requirements = db.Column(db.JSON, nullable=False, default=dict)
    downloaded_tracks = db.Column(db.JSON, nullable=False, default=list)
    engineer_proposal = db.Column(db.JSON, nullable=False, default=dict)
    client_questions = db.Column(db.JSON, nullable=False, default=list)
    client_answers = db.Column(db.JSON, nullable=False, default=dict)
    follow_up_questions = db.Column(db.JSON, nullable=False, default=list)
    final_output = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="mix_sessions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "prompt": self.prompt,
            "status": self.status,
            "planner_requirements": self.planner_requirements or {},
            "downloaded_tracks": self.downloaded_tracks or [],
            "engineer_proposal": self.engineer_proposal or {},
            "client_questions": self.client_questions or [],
            "client_answers": self.client_answers or {},
            "follow_up_questions": self.follow_up_questions or [],
            "final_output": self.final_output or {},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class MixChatThread(db.Model):
    __tablename__ = "mix_chat_threads"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, default="New Mix Chat")
    archived = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_message_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship("User", back_populates="mix_chat_threads")
    messages = db.relationship("MixChatMessage", back_populates="thread", cascade="all, delete-orphan")
    versions = db.relationship("MixChatVersion", back_populates="thread", cascade="all, delete-orphan")
    runs = db.relationship("MixChatRun", back_populates="thread", cascade="all, delete-orphan")
    plan_drafts = db.relationship("MixChatPlanDraft", back_populates="thread", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "archived": self.archived,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
        }


class MixChatMessage(db.Model):
    __tablename__ = "mix_chat_messages"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = db.Column(db.String(36), db.ForeignKey("mix_chat_threads.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, index=True)  # user|assistant|system
    content_text = db.Column(db.Text, nullable=True)
    content_json = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(20), nullable=False, default="completed", index=True)  # queued|running|completed|failed
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    thread = db.relationship("MixChatThread", back_populates="messages")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "role": self.role,
            "content_text": self.content_text,
            "content_json": self.content_json or {},
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MixChatVersion(db.Model):
    __tablename__ = "mix_chat_versions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = db.Column(db.String(36), db.ForeignKey("mix_chat_threads.id"), nullable=False, index=True)
    source_user_message_id = db.Column(db.String(36), db.ForeignKey("mix_chat_messages.id"), nullable=True, index=True)
    assistant_message_id = db.Column(db.String(36), db.ForeignKey("mix_chat_messages.id"), nullable=True, index=True)
    parent_version_id = db.Column(db.String(36), db.ForeignKey("mix_chat_versions.id"), nullable=True, index=True)
    mix_session_id = db.Column(db.String(36), db.ForeignKey("mix_sessions.id"), nullable=True, index=True)
    proposal_json = db.Column(db.JSON, nullable=False, default=dict)
    final_output_json = db.Column(db.JSON, nullable=False, default=dict)
    state_snapshot_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    thread = db.relationship("MixChatThread", back_populates="versions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "source_user_message_id": self.source_user_message_id,
            "assistant_message_id": self.assistant_message_id,
            "parent_version_id": self.parent_version_id,
            "mix_session_id": self.mix_session_id,
            "proposal_json": self.proposal_json or {},
            "final_output_json": self.final_output_json or {},
            "state_snapshot_json": self.state_snapshot_json or {},
            "created_at": self.created_at.isoformat(),
        }


def _mix_chat_stage_progress_defaults(stage: str, status: str) -> dict[str, Any]:
    normalized_stage = str(stage or "").strip().lower()
    normalized_status = str(status or "").strip().lower()
    defaults_by_stage: dict[str, dict[str, Any]] = {
        "queued": {
            "percent": 2,
            "label": "Queued",
            "detail": "Waiting for an audio engineer worker.",
        },
        "planning": {
            "percent": 10,
            "label": "Analyzing brief",
            "detail": "Understanding your prompt and plan context.",
        },
        "planning_questions": {
            "percent": 26,
            "label": "Preparing clarifications",
            "detail": "Building targeted questions to lock constraints.",
        },
        "planning_draft_ready": {
            "percent": 42,
            "label": "Draft prepared",
            "detail": "Plan draft is ready for your review.",
        },
        "waiting_approval": {
            "percent": 48,
            "label": "Waiting for approval",
            "detail": "Approve the current plan to start rendering.",
        },
        "waiting_ai": {
            "percent": 20,
            "label": "Retrying AI capacity",
            "detail": "Temporary AI capacity issue. Retrying automatically.",
        },
        "retrying_ai": {
            "percent": 20,
            "label": "Retrying AI capacity",
            "detail": "Temporary AI capacity issue. Retrying automatically.",
        },
        "downloading": {
            "percent": 66,
            "label": "Collecting source audio",
            "detail": "Resolving and preparing source media for the mix.",
        },
        "rendering": {
            "percent": 86,
            "label": "Rendering mix",
            "detail": "Applying transitions and exporting final output.",
        },
        "draft_ready": {
            "percent": 42,
            "label": "Draft prepared",
            "detail": "Draft is ready for review.",
        },
        "completed": {
            "percent": 100,
            "label": "Completed",
            "detail": "Run finished successfully.",
        },
        "failed": {
            "percent": 100,
            "label": "Failed",
            "detail": "Run failed before completion.",
        },
    }
    defaults = defaults_by_stage.get(normalized_stage)
    if defaults:
        return defaults
    if normalized_status == "completed":
        return defaults_by_stage["completed"]
    if normalized_status == "failed":
        return defaults_by_stage["failed"]
    if normalized_status == "running":
        return {
            "percent": 25,
            "label": "In progress",
            "detail": "Processing your request.",
        }
    return defaults_by_stage["queued"]


class MixChatRun(db.Model):
    __tablename__ = "mix_chat_runs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = db.Column(db.String(36), db.ForeignKey("mix_chat_threads.id"), nullable=False, index=True)
    user_message_id = db.Column(db.String(36), db.ForeignKey("mix_chat_messages.id"), nullable=False, index=True)
    assistant_message_id = db.Column(db.String(36), db.ForeignKey("mix_chat_messages.id"), nullable=False, index=True)
    parent_version_id = db.Column(db.String(36), db.ForeignKey("mix_chat_versions.id"), nullable=True, index=True)
    version_id = db.Column(db.String(36), db.ForeignKey("mix_chat_versions.id"), nullable=True, index=True)
    mode = db.Column(db.String(20), nullable=False, default="refine_last", index=True)
    run_kind = db.Column(
        db.String(20),
        nullable=False,
        default="prompt",
        index=True,
    )  # prompt|timeline_edit|timeline_attachment|planning_intake|planning_revision|planning_execute
    input_summary_json = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="queued", index=True)  # queued|running|completed|failed
    progress_stage = db.Column(db.String(40), nullable=False, default="queued", index=True)
    progress_percent = db.Column(db.Integer, nullable=True)
    progress_label = db.Column(db.String(120), nullable=True)
    progress_detail = db.Column(db.Text, nullable=True)
    progress_updated_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    thread = db.relationship("MixChatThread", back_populates="runs")

    def to_dict(self) -> dict[str, Any]:
        normalized_status = str(self.status or "").strip().lower()
        normalized_stage = str(self.progress_stage or "").strip().lower()
        defaults = _mix_chat_stage_progress_defaults(normalized_stage, normalized_status)
        default_percent = int(defaults["percent"])
        if self.progress_percent is None:
            progress_percent = default_percent
        else:
            progress_percent = int(max(0, min(100, self.progress_percent)))
            if normalized_status in {"queued", "running"}:
                progress_percent = max(progress_percent, default_percent)
        if normalized_status in {"completed", "failed"}:
            progress_percent = 100

        # Use stage defaults by default so UI remains accurate even if only stage is updated.
        progress_label = str(defaults["label"])
        progress_detail = str(defaults["detail"])
        progress_label_override = str(self.progress_label or "").strip()
        progress_detail_override = str(self.progress_detail or "").strip()
        if normalized_stage in {"waiting_ai", "retrying_ai", "failed"}:
            if progress_label_override:
                progress_label = progress_label_override
            if progress_detail_override:
                progress_detail = progress_detail_override

        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "user_message_id": self.user_message_id,
            "assistant_message_id": self.assistant_message_id,
            "parent_version_id": self.parent_version_id,
            "version_id": self.version_id,
            "mode": self.mode,
            "run_kind": self.run_kind,
            "input_summary_json": self.input_summary_json or {},
            "status": self.status,
            "progress_stage": self.progress_stage,
            "progress_percent": progress_percent,
            "progress_label": progress_label,
            "progress_detail": progress_detail,
            "progress_updated_at": self.progress_updated_at.isoformat() if self.progress_updated_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class MixChatPlanDraft(db.Model):
    __tablename__ = "mix_chat_plan_drafts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = db.Column(db.String(36), db.ForeignKey("mix_chat_threads.id"), nullable=False, index=True)
    source_user_message_id = db.Column(db.String(36), db.ForeignKey("mix_chat_messages.id"), nullable=False, index=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="collecting",
        index=True,
    )  # collecting|draft_ready|approved|superseded|executed|cancelled
    round_count = db.Column(db.Integer, nullable=False, default=0)
    max_rounds = db.Column(db.Integer, nullable=False, default=5)
    confidence_score = db.Column(db.Float, nullable=False, default=0.0)
    required_slots_json = db.Column(db.JSON, nullable=False, default=dict)
    questions_json = db.Column(db.JSON, nullable=False, default=list)
    answers_json = db.Column(db.JSON, nullable=False, default=dict)
    proposal_json = db.Column(db.JSON, nullable=False, default=dict)
    resolution_notes_json = db.Column(db.JSON, nullable=False, default=dict)
    conversation_summary_json = db.Column(db.JSON, nullable=False, default=dict)
    constraint_contract_json = db.Column(db.JSON, nullable=False, default=dict)
    pending_clarifications_json = db.Column(db.JSON, nullable=False, default=list)
    last_planner_trace_json = db.Column(db.JSON, nullable=False, default=dict)
    adjustment_policy = db.Column(db.String(60), nullable=False, default="minor_auto_adjust_allowed")
    approved_at = db.Column(db.DateTime, nullable=True)
    executed_run_id = db.Column(db.String(36), db.ForeignKey("mix_chat_runs.id"), nullable=True, index=True)
    executed_version_id = db.Column(db.String(36), db.ForeignKey("mix_chat_versions.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    thread = db.relationship("MixChatThread", back_populates="plan_drafts")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "source_user_message_id": self.source_user_message_id,
            "status": self.status,
            "round_count": int(self.round_count or 0),
            "max_rounds": int(self.max_rounds or 0),
            "confidence_score": float(self.confidence_score or 0.0),
            "required_slots_json": self.required_slots_json or {},
            "questions_json": self.questions_json or [],
            "answers_json": self.answers_json or {},
            "proposal_json": self.proposal_json or {},
            "resolution_notes_json": self.resolution_notes_json or {},
            "conversation_summary_json": self.conversation_summary_json or {},
            "constraint_contract_json": self.constraint_contract_json or {},
            "pending_clarifications_json": self.pending_clarifications_json or [],
            "last_planner_trace_json": self.last_planner_trace_json or {},
            "adjustment_policy": self.adjustment_policy,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "executed_run_id": self.executed_run_id,
            "executed_version_id": self.executed_version_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MixChatLegacyMapping(db.Model):
    __tablename__ = "mix_chat_legacy_mappings"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_session_id = db.Column(db.String(36), db.ForeignKey("mix_sessions.id"), nullable=False, unique=True, index=True)
    thread_id = db.Column(db.String(36), db.ForeignKey("mix_chat_threads.id"), nullable=False, index=True)
    version_id = db.Column(db.String(36), db.ForeignKey("mix_chat_versions.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mix_session_id": self.mix_session_id,
            "thread_id": self.thread_id,
            "version_id": self.version_id,
            "created_at": self.created_at.isoformat(),
        }


class MixUserMemory(db.Model):
    __tablename__ = "mix_user_memory"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    profile_json = db.Column(db.JSON, nullable=False, default=dict)
    feedback_json = db.Column(db.JSON, nullable=False, default=dict)
    use_case_profiles_json = db.Column(db.JSON, nullable=False, default=dict)
    template_pack_json = db.Column(db.JSON, nullable=False, default=dict)
    quality_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="mix_memory")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "profile_json": self.profile_json or {},
            "feedback_json": self.feedback_json or {},
            "use_case_profiles_json": self.use_case_profiles_json or {},
            "template_pack_json": self.template_pack_json or {},
            "quality_json": self.quality_json or {},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(255), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(20), nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)


def _parse_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql://", 1)
    return raw_url


def _parse_time_to_seconds(time_value: Any) -> int:
    if time_value is None:
        raise ValueError("Time value is required")

    if isinstance(time_value, (int, float)):
        seconds = int(time_value)
        if seconds < 0:
            raise ValueError("Time cannot be negative")
        return seconds

    time_str = str(time_value).strip()
    if not time_str:
        raise ValueError("Time value is empty")

    if ":" not in time_str:
        seconds = int(time_str)
        if seconds < 0:
            raise ValueError("Time cannot be negative")
        return seconds

    parts = [int(part) for part in time_str.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return (minutes * 60) + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return (hours * 3600) + (minutes * 60) + seconds

    raise ValueError(f"Invalid time format: {time_str}")


def _ensure_mix_chat_runtime_schema(app: Flask) -> None:
    engine = db.engine
    inspector = inspect(engine)

    try:
        run_columns = {column["name"] for column in inspector.get_columns("mix_chat_runs")}
    except Exception:
        app.logger.warning("Unable to inspect mix_chat_runs table for runtime schema upgrades.")
        return

    dialect = engine.dialect.name
    statements: list[str] = []
    if "run_kind" not in run_columns:
        statements.append("ALTER TABLE mix_chat_runs ADD COLUMN run_kind VARCHAR(20) DEFAULT 'prompt'")
    if "input_summary_json" not in run_columns:
        json_type = "JSONB" if dialect == "postgresql" else "JSON"
        statements.append(f"ALTER TABLE mix_chat_runs ADD COLUMN input_summary_json {json_type}")
    if "progress_percent" not in run_columns:
        statements.append("ALTER TABLE mix_chat_runs ADD COLUMN progress_percent INTEGER")
    if "progress_label" not in run_columns:
        statements.append("ALTER TABLE mix_chat_runs ADD COLUMN progress_label VARCHAR(120)")
    if "progress_detail" not in run_columns:
        statements.append("ALTER TABLE mix_chat_runs ADD COLUMN progress_detail TEXT")
    if "progress_updated_at" not in run_columns:
        statements.append("ALTER TABLE mix_chat_runs ADD COLUMN progress_updated_at TIMESTAMP")

    try:
        draft_columns = {column["name"] for column in inspector.get_columns("mix_chat_plan_drafts")}
    except Exception:
        app.logger.warning("Unable to inspect mix_chat_plan_drafts table for runtime schema upgrades.")
        draft_columns = set()

    if draft_columns:
        json_type = "JSONB" if dialect == "postgresql" else "JSON"
        if "conversation_summary_json" not in draft_columns:
            statements.append(
                f"ALTER TABLE mix_chat_plan_drafts ADD COLUMN conversation_summary_json {json_type}"
            )
        if "constraint_contract_json" not in draft_columns:
            statements.append(
                f"ALTER TABLE mix_chat_plan_drafts ADD COLUMN constraint_contract_json {json_type}"
            )
        if "pending_clarifications_json" not in draft_columns:
            statements.append(
                f"ALTER TABLE mix_chat_plan_drafts ADD COLUMN pending_clarifications_json {json_type}"
            )
        if "last_planner_trace_json" not in draft_columns:
            statements.append(
                f"ALTER TABLE mix_chat_plan_drafts ADD COLUMN last_planner_trace_json {json_type}"
            )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        if "run_kind" not in run_columns:
            connection.execute(text("UPDATE mix_chat_runs SET run_kind = 'prompt' WHERE run_kind IS NULL"))
        if "progress_updated_at" not in run_columns:
            connection.execute(
                text(
                    "UPDATE mix_chat_runs "
                    "SET progress_updated_at = created_at "
                    "WHERE progress_updated_at IS NULL"
                )
            )
        if draft_columns:
            connection.execute(
                text(
                    "UPDATE mix_chat_plan_drafts "
                    "SET conversation_summary_json = '{}' "
                    "WHERE conversation_summary_json IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE mix_chat_plan_drafts "
                    "SET constraint_contract_json = '{}' "
                    "WHERE constraint_contract_json IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE mix_chat_plan_drafts "
                    "SET pending_clarifications_json = '[]' "
                    "WHERE pending_clarifications_json IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE mix_chat_plan_drafts "
                    "SET last_planner_trace_json = '{}' "
                    "WHERE last_planner_trace_json IS NULL"
                )
            )

    app.logger.info("Applied runtime mix chat schema upgrade.")


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_bool_env(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_timeline_edit_segments(raw_segments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ValueError("segments must be a non-empty array")
    if len(raw_segments) > 500:
        raise ValueError("segments cannot exceed 500 entries")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_segments):
        if not isinstance(item, dict):
            raise ValueError(f"segments[{index}] must be an object")

        segment_id = str(item.get("id", "")).strip() or f"seg_{index + 1}"
        segment_name = str(item.get("segment_name", "")).strip()
        track_index = _coerce_int(item.get("track_index"), -1)
        if track_index < 0:
            raise ValueError(f"segments[{index}].track_index must be >= 0")

        start_ms = _coerce_int(item.get("start_ms"), -1)
        end_ms = _coerce_int(item.get("end_ms"), -1)
        if start_ms < 0:
            raise ValueError(f"segments[{index}].start_ms must be >= 0")
        if end_ms <= start_ms:
            raise ValueError(f"segments[{index}].end_ms must be greater than start_ms")
        if (end_ms - start_ms) < 1000:
            raise ValueError(f"segments[{index}] duration must be at least 1000ms")

        crossfade_seconds = _clamp(_coerce_float(item.get("crossfade_after_seconds"), 0.0), 0.0, 8.0)

        eq_raw = item.get("eq", {})
        if not isinstance(eq_raw, dict):
            eq_raw = {}
        effects_raw = item.get("effects", {})
        if not isinstance(effects_raw, dict):
            effects_raw = {}

        normalized.append(
            {
                "id": segment_id[:80],
                "order": index,
                "segment_name": segment_name[:120] or f"Segment {index + 1}",
                "track_index": track_index,
                "track_id": str(item.get("track_id", track_index)).strip()[:80] or str(track_index),
                "track_title": str(item.get("track_title", "")).strip()[:200],
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": int(end_ms - start_ms),
                "crossfade_after_seconds": float(crossfade_seconds),
                "effects": {
                    "reverb_amount": _clamp(_coerce_float(effects_raw.get("reverb_amount"), 0.0), 0.0, 1.0),
                    "delay_ms": int(_clamp(_coerce_float(effects_raw.get("delay_ms"), 0.0), 0.0, 1200.0)),
                    "delay_feedback": _clamp(_coerce_float(effects_raw.get("delay_feedback"), 0.0), 0.0, 0.95),
                },
                "eq": {
                    "low_gain_db": _coerce_float(eq_raw.get("low_gain_db"), 0.0),
                    "mid_gain_db": _coerce_float(eq_raw.get("mid_gain_db"), 0.0),
                    "high_gain_db": _coerce_float(eq_raw.get("high_gain_db"), 0.0),
                },
            }
        )

    for index in range(len(normalized) - 1):
        current_duration_seconds = (normalized[index]["end_ms"] - normalized[index]["start_ms"]) / 1000.0
        next_duration_seconds = (normalized[index + 1]["end_ms"] - normalized[index + 1]["start_ms"]) / 1000.0
        max_crossfade = _clamp(min(current_duration_seconds, next_duration_seconds) - 0.1, 0.0, 8.0)
        normalized[index]["crossfade_after_seconds"] = _clamp(
            normalized[index]["crossfade_after_seconds"], 0.0, max_crossfade
        )
    if normalized:
        normalized[-1]["crossfade_after_seconds"] = 0.0

    return normalized


def _normalize_timeline_attachments(raw_attachments: Any) -> list[dict[str, Any]]:
    if raw_attachments is None:
        return []
    if not isinstance(raw_attachments, list):
        raise ValueError("attachments must be an array")
    if len(raw_attachments) > 1:
        raise ValueError("Only one attachment is supported per message")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_attachments):
        if not isinstance(item, dict):
            raise ValueError(f"attachments[{index}] must be an object")
        attachment_type = str(item.get("type", "")).strip()
        if attachment_type != "timeline_snapshot":
            raise ValueError("attachments[0].type must be timeline_snapshot")

        source_version_id = str(item.get("source_version_id", "")).strip()
        if not source_version_id:
            raise ValueError("attachments[0].source_version_id is required")

        normalized_segments = _normalize_timeline_edit_segments(item.get("segments"))
        editor_metadata = item.get("editor_metadata", {})
        if not isinstance(editor_metadata, dict):
            editor_metadata = {}

        changed_segment_ids_raw = editor_metadata.get("changed_segment_ids", [])
        changed_segment_ids = (
            [str(entry).strip()[:80] for entry in changed_segment_ids_raw if str(entry).strip()]
            if isinstance(changed_segment_ids_raw, list)
            else []
        )

        normalized.append(
            {
                "type": "timeline_snapshot",
                "source_version_id": source_version_id,
                "segments": normalized_segments,
                "editor_metadata": {
                    "changed_segment_ids": changed_segment_ids,
                    "total_segments": len(normalized_segments),
                },
            }
        )

    return normalized


def _normalize_planning_answers(raw_answers: Any) -> list[dict[str, str]]:
    if not isinstance(raw_answers, list) or not raw_answers:
        raise ValueError("planning_response.answers must be a non-empty array")

    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw_answers):
        if not isinstance(item, dict):
            raise ValueError(f"planning_response.answers[{index}] must be an object")

        question_id = str(item.get("question_id", "")).strip()
        selected_option_id = str(item.get("selected_option_id", "")).strip()
        other_text = str(item.get("other_text", "")).strip()

        if not question_id:
            raise ValueError(f"planning_response.answers[{index}].question_id is required")
        if not selected_option_id and not other_text:
            raise ValueError(
                f"planning_response.answers[{index}] must include selected_option_id or other_text"
            )

        normalized.append(
            {
                "question_id": question_id[:80],
                "selected_option_id": selected_option_id[:80],
                "other_text": other_text[:600],
            }
        )

    return normalized


def create_app(test_config: Optional[dict[str, Any]] = None) -> Flask:
    app = Flask(__name__)

    app_env = os.environ.get("APP_ENV", "").strip().lower()
    flask_env = os.environ.get("FLASK_ENV", "").strip().lower()
    if app_env == "production" or flask_env == "production":
        required_env = ("DATABASE_URL", "FLASK_SECRET_KEY", "JWT_SECRET_KEY")
        missing = [name for name in required_env if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                f"Missing required production environment variables: {', '.join(missing)}"
            )

    default_database_url = f"sqlite:///{Path(app.root_path) / 'intellimix.db'}"
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex()),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", os.urandom(32).hex()),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "30"))),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=int(os.environ.get("JWT_REFRESH_TOKEN_DAYS", "30"))),
        SQLALCHEMY_DATABASE_URI=_parse_database_url(os.environ.get("DATABASE_URL", default_database_url)),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        STORAGE_ROOT=os.environ.get("STORAGE_ROOT", str(Path(app.root_path) / "storage")),
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024,
        GENERIC_ERROR_MESSAGE="Request failed. Please retry.",
    )

    if test_config:
        app.config.update(test_config)

    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
    CORS(
        app,
        resources={
            r"/api/*": {"origins": [frontend_origin]},
            r"/files/*": {"origins": [frontend_origin]},
        },
        supports_credentials=False,
    )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    db.init_app(app)
    jwt.init_app(app)

    with app.app_context():
        db.create_all()
        _ensure_mix_chat_runtime_schema(app)

    storage_root = Path(app.config["STORAGE_ROOT"]).resolve()
    jobs_root = storage_root / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)

    @jwt.token_in_blocklist_loader
    def is_token_revoked(_jwt_header: dict[str, Any], jwt_payload: dict[str, Any]) -> bool:
        jti = jwt_payload.get("jti")
        if not jti:
            return True
        return db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar() is not None

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "microphone=(), camera=(), geolocation=()"
        return response

    @app.errorhandler(404)
    def not_found(_: Exception):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def payload_too_large(_: Exception):
        return jsonify({"error": "Uploaded payload exceeds configured size limit"}), 413

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled exception: %s", exc)
        return jsonify({"error": app.config["GENERIC_ERROR_MESSAGE"]}), 500

    def revoke_token_by_payload(payload: dict[str, Any]) -> None:
        jti = payload.get("jti")
        if not jti:
            return

        token_exp = payload.get("exp")
        if token_exp is None:
            return

        expires_at = datetime.fromtimestamp(token_exp, timezone.utc)

        existing = TokenBlocklist.query.filter_by(jti=jti).first()
        if existing:
            return

        db.session.add(
            TokenBlocklist(
                jti=jti,
                token_type=payload.get("type", "unknown"),
                expires_at=expires_at,
            )
        )

    def create_workspace(job_id: str) -> Path:
        workspace = jobs_root / job_id
        required_dirs = [
            workspace / "temp",
            workspace / "temp" / "split",
            workspace / "temp" / "output",
            workspace / "csv",
            workspace / "static" / "output",
            workspace / "static" / "audio_dl",
            workspace / "static" / "video_dl",
        ]
        for directory in required_dirs:
            directory.mkdir(parents=True, exist_ok=True)
        return workspace

    def build_file_url(job_id: str, filename: str) -> str:
        return f"{request.host_url.rstrip('/')}/files/{job_id}/{filename}"

    def create_job(user_id: str, generation_type: str, payload: dict[str, Any]) -> GenerationJob:
        if generation_type not in GENERATION_TYPES:
            raise ValueError("Unsupported generation type")

        job = GenerationJob(
            user_id=user_id,
            generation_type=generation_type,
            status="processing",
            input_payload=payload,
        )
        db.session.add(job)
        db.session.commit()
        return job

    def mark_job_success(job: GenerationJob, output_url: str) -> None:
        job.status = "success"
        job.output_url = output_url
        job.error_message = None
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    def mark_job_failure(job: GenerationJob, error_message: str) -> None:
        job.status = "failed"
        job.error_message = error_message[:2000]
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    def create_mix_session(user_id: str, prompt: str) -> MixSession:
        session = MixSession(
            user_id=user_id,
            prompt=prompt,
            status="planning",
        )
        db.session.add(session)
        db.session.commit()
        return session

    def build_relative_file_url(job_id: str, filename: str) -> str:
        return f"/files/{job_id}/{filename}"

    def create_mix_chat_thread(user_id: str, title: str | None = None) -> MixChatThread:
        safe_title = (title or "New Mix Chat").strip()[:255] or "New Mix Chat"
        thread = MixChatThread(
            user_id=user_id,
            title=safe_title,
            archived=False,
            last_message_at=datetime.now(timezone.utc),
        )
        db.session.add(thread)
        db.session.commit()
        return thread

    def create_mix_chat_message(
        *,
        thread_id: str,
        role: str,
        content_text: str | None = None,
        content_json: dict[str, Any] | None = None,
        status: str = "completed",
    ) -> MixChatMessage:
        message = MixChatMessage(
            thread_id=thread_id,
            role=role,
            content_text=(content_text or "").strip() or None,
            content_json=content_json or {},
            status=status,
        )
        db.session.add(message)
        db.session.commit()
        return message

    def _derive_chat_title_from_prompt(prompt: str) -> str:
        cleaned = " ".join(prompt.strip().split())
        if not cleaned:
            return "New Mix Chat"
        return (cleaned[:80] + "...") if len(cleaned) > 80 else cleaned

    def _should_inline_fallback() -> bool:
        return os.environ.get("MIX_CHAT_INLINE_FALLBACK", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def enqueue_mix_chat_run(run_id: str) -> bool:
        from mix_chat_queue import enqueue_run

        queued = enqueue_run(run_id)
        if queued:
            return True
        if not _should_inline_fallback():
            return False

        def _run_inline():
            try:
                from mix_chat_runner import process_mix_chat_run

                process_mix_chat_run(run_id)
            except Exception:
                app.logger.exception("inline mix chat processing failed for run %s", run_id)

        worker = threading.Thread(target=_run_inline, daemon=True)
        worker.start()
        return True

    def backfill_legacy_mix_sessions() -> None:
        legacy_sessions = (
            MixSession.query.order_by(MixSession.created_at.asc())
            .all()
        )
        if not legacy_sessions:
            return

        imported = 0
        for legacy in legacy_sessions:
            existing = MixChatLegacyMapping.query.filter_by(mix_session_id=legacy.id).first()
            if existing:
                continue

            title = _derive_chat_title_from_prompt(legacy.prompt or "Legacy Mix Session")
            thread = MixChatThread(
                user_id=legacy.user_id,
                title=title,
                archived=False,
                created_at=legacy.created_at or datetime.now(timezone.utc),
                updated_at=legacy.updated_at or datetime.now(timezone.utc),
                last_message_at=legacy.updated_at or legacy.created_at or datetime.now(timezone.utc),
            )
            db.session.add(thread)
            db.session.flush()

            user_message = MixChatMessage(
                thread_id=thread.id,
                role="user",
                content_text=legacy.prompt,
                content_json={"legacy": True, "source": "mix_sessions"},
                status="completed",
                created_at=legacy.created_at or datetime.now(timezone.utc),
                updated_at=legacy.updated_at or datetime.now(timezone.utc),
            )
            db.session.add(user_message)
            db.session.flush()

            assistant_json = {
                "kind": "mix_proposal",
                "legacy": True,
                "mix_session_id": legacy.id,
                "requirements": legacy.planner_requirements or {},
                "tracks": legacy.downloaded_tracks or [],
                "proposal": legacy.engineer_proposal or {},
                "client_questions": legacy.client_questions or [],
                "final_output": legacy.final_output or {},
                "auto_rendered": True,
            }
            assistant_message = MixChatMessage(
                thread_id=thread.id,
                role="assistant",
                content_text=str((legacy.engineer_proposal or {}).get("mixing_rationale", "")).strip() or "Legacy mix session imported.",
                content_json=assistant_json,
                status="completed",
                created_at=legacy.updated_at or legacy.created_at or datetime.now(timezone.utc),
                updated_at=legacy.updated_at or legacy.created_at or datetime.now(timezone.utc),
            )
            db.session.add(assistant_message)
            db.session.flush()

            version = MixChatVersion(
                thread_id=thread.id,
                source_user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                parent_version_id=None,
                mix_session_id=legacy.id,
                proposal_json={
                    "requirements": legacy.planner_requirements or {},
                    "tracks": legacy.downloaded_tracks or [],
                    "proposal": legacy.engineer_proposal or {},
                    "client_questions": legacy.client_questions or [],
                },
                final_output_json=legacy.final_output or {},
                state_snapshot_json={
                    "summary": str((legacy.planner_requirements or {}).get("summary", "")),
                    "mixing_rationale": str((legacy.engineer_proposal or {}).get("mixing_rationale", "")),
                    "legacy_imported": True,
                },
                created_at=legacy.updated_at or legacy.created_at or datetime.now(timezone.utc),
            )
            db.session.add(version)
            db.session.flush()

            mapping = MixChatLegacyMapping(
                mix_session_id=legacy.id,
                thread_id=thread.id,
                version_id=version.id,
            )
            db.session.add(mapping)
            imported += 1

        if imported:
            db.session.commit()
            app.logger.info("Imported %s legacy mix sessions into mix chat threads.", imported)
        else:
            db.session.rollback()

    def create_mix_chat_run(
        *,
        thread: MixChatThread,
        content: str,
        mode: str = "refine_last",
        run_kind: str = "prompt",
        parent_version: MixChatVersion | None = None,
        user_content_json: Optional[dict[str, Any]] = None,
        assistant_kind: str = "mix_proposal",
        assistant_placeholder_text: str = "Working on your mix...",
        input_summary_json: Optional[dict[str, Any]] = None,
    ) -> tuple[MixChatMessage, MixChatMessage, MixChatRun]:
        normalized_mode = mode if mode in {"refine_last", "restart_fresh"} else "refine_last"
        if run_kind in {
            "timeline_edit",
            "timeline_attachment",
            "planning_intake",
            "planning_revision",
            "planning_execute",
        }:
            normalized_run_kind = run_kind
        else:
            normalized_run_kind = "prompt"

        if (
            parent_version is None
            and normalized_mode == "refine_last"
            and normalized_run_kind in {"prompt", "timeline_edit", "timeline_attachment"}
        ):
            parent_version = (
                MixChatVersion.query.filter_by(thread_id=thread.id)
                .order_by(MixChatVersion.created_at.desc())
                .first()
            )

        user_message = MixChatMessage(
            thread_id=thread.id,
            role="user",
            content_text=content.strip(),
            content_json=user_content_json or {},
            status="completed",
        )
        db.session.add(user_message)
        db.session.flush()

        assistant_message = MixChatMessage(
            thread_id=thread.id,
            role="assistant",
            content_text=assistant_placeholder_text,
            content_json={
                "kind": assistant_kind,
                "status": "queued",
            },
            status="queued",
        )
        db.session.add(assistant_message)
        db.session.flush()

        run = MixChatRun(
            thread_id=thread.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            parent_version_id=parent_version.id if parent_version else None,
            mode=normalized_mode,
            run_kind=normalized_run_kind,
            input_summary_json=input_summary_json or {},
            status="queued",
            progress_stage="queued",
            progress_percent=2,
            progress_label="Queued",
            progress_detail="Waiting for an audio engineer worker.",
            progress_updated_at=datetime.now(timezone.utc),
        )
        db.session.add(run)
        thread.last_message_at = datetime.now(timezone.utc)
        db.session.commit()
        return user_message, assistant_message, run

    ACTIVE_PLANNING_STATUSES = {"collecting", "draft_ready", "approved"}

    def get_active_plan_draft(thread_id: str) -> Optional[MixChatPlanDraft]:
        return (
            MixChatPlanDraft.query.filter_by(thread_id=thread_id)
            .filter(MixChatPlanDraft.status.in_(list(ACTIVE_PLANNING_STATUSES)))
            .order_by(MixChatPlanDraft.updated_at.desc(), MixChatPlanDraft.created_at.desc())
            .first()
        )

    def summarize_recent_thread_context(thread_id: str, limit: int = 14) -> list[dict[str, str]]:
        recent = (
            MixChatMessage.query.filter_by(thread_id=thread_id)
            .order_by(MixChatMessage.created_at.desc())
            .limit(max(1, min(limit, 40)))
            .all()
        )
        serialized: list[dict[str, str]] = []
        for message in reversed(recent):
            text_value = str(message.content_text or "").strip()
            if not text_value:
                continue
            serialized.append(
                {
                    "role": str(message.role or "system")[:20],
                    "text": text_value[:700],
                    "kind": str((message.content_json or {}).get("kind", ""))[:80],
                }
            )
        return serialized

    def thread_payload_with_planning_state(thread: MixChatThread) -> dict[str, Any]:
        payload = thread.to_dict()
        draft = get_active_plan_draft(thread.id)
        if draft is None:
            payload["planning_status"] = None
            payload["planning_draft_id"] = None
            payload["planning_round_count"] = 0
            payload["active_planning_status"] = None
            payload["active_planning_draft_id"] = None
            return payload
        payload["planning_status"] = draft.status
        payload["planning_draft_id"] = draft.id
        payload["planning_round_count"] = int(draft.round_count or 0)
        payload["active_planning_status"] = draft.status
        payload["active_planning_draft_id"] = draft.id
        return payload

    def resolve_identity_for_file_access() -> Optional[str]:
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            if identity:
                return identity
        except Exception:
            pass

        token = request.args.get("token")
        if not token:
            return None

        try:
            decoded = decode_token(token)
            jti = decoded.get("jti")
            if jti and TokenBlocklist.query.filter_by(jti=jti).first():
                return None
            return decoded.get("sub")
        except Exception:
            return None

    @app.get("/")
    def root():
        return jsonify({
            "name": "IntelliMix API",
            "version": "v1",
            "health": "/api/v1/health",
        })

    @app.get("/api/v1/health")
    def health_check():
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

    @app.post("/api/v1/auth/register")
    def register():
        payload = request.get_json(silent=True) or {}

        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))

        if not name:
            return jsonify({"error": "Name is required"}), 400
        if not email or not EMAIL_REGEX.match(email):
            return jsonify({"error": "Valid email is required"}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400

        user = User(name=name, email=email, password_hash=generate_password_hash(password))

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "Email is already registered"}), 409

        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return (
            jsonify(
                {
                    "message": "User registered successfully",
                    "user": user.to_public_dict(),
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }
            ),
            201,
        )

    @app.post("/api/v1/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}

        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        user = User.query.filter(func.lower(User.email) == email, User.is_active.is_(True)).first()
        if user is None or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401

        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return jsonify(
            {
                "message": "Login successful",
                "user": user.to_public_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )

    @app.post("/api/v1/auth/refresh")
    def refresh_access_token():
        payload = request.get_json(silent=True) or {}
        refresh_token = str(payload.get("refresh_token", "")).strip()

        if not refresh_token:
            return jsonify({"error": "refresh_token is required"}), 400

        try:
            decoded = decode_token(refresh_token)
        except Exception:
            return jsonify({"error": "Invalid refresh token"}), 401

        if decoded.get("type") != "refresh":
            return jsonify({"error": "Provided token is not a refresh token"}), 401

        jti = decoded.get("jti")
        if jti and TokenBlocklist.query.filter_by(jti=jti).first():
            return jsonify({"error": "Refresh token has been revoked"}), 401

        user_id = decoded.get("sub")
        if not user_id:
            return jsonify({"error": "Invalid refresh token payload"}), 401

        user = User.query.filter_by(id=user_id, is_active=True).first()
        if user is None:
            return jsonify({"error": "User not found"}), 404

        access_token = create_access_token(identity=user.id)
        return jsonify({"access_token": access_token})

    @app.post("/api/v1/auth/logout")
    @jwt_required(optional=True)
    def logout():
        request_payload = request.get_json(silent=True) or {}
        refresh_token = str(request_payload.get("refresh_token", "")).strip()

        current_jwt = get_jwt()
        if current_jwt:
            revoke_token_by_payload(current_jwt)

        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                revoke_token_by_payload(refresh_payload)
            except Exception:
                pass

        db.session.commit()
        return jsonify({"message": "Logged out"})

    @app.get("/api/v1/auth/me")
    @jwt_required()
    def me():
        user_id = str(get_jwt_identity())
        user = User.query.filter_by(id=user_id, is_active=True).first()
        if user is None:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user.to_public_dict()})

    @app.get("/api/v1/history")
    @jwt_required()
    def list_history():
        user_id = str(get_jwt_identity())

        generation_type = str(request.args.get("type", "")).strip()
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))

        query = GenerationJob.query.filter_by(user_id=user_id)
        if generation_type:
            query = query.filter_by(generation_type=generation_type)

        pagination = query.order_by(GenerationJob.created_at.desc()).paginate(page=page, per_page=limit, error_out=False)

        return jsonify(
            {
                "items": [item.to_dict() for item in pagination.items],
                "page": page,
                "limit": limit,
                "total": pagination.total,
                "pages": pagination.pages,
            }
        )

    @app.get("/api/v1/history/<job_id>")
    @jwt_required()
    def get_history_item(job_id: str):
        user_id = str(get_jwt_identity())
        item = GenerationJob.query.filter_by(id=job_id, user_id=user_id).first()
        if item is None:
            return jsonify({"error": "History item not found"}), 404
        return jsonify({"item": item.to_dict()})

    @app.delete("/api/v1/history/<job_id>")
    @jwt_required()
    def delete_history_item(job_id: str):
        user_id = str(get_jwt_identity())
        item = GenerationJob.query.filter_by(id=job_id, user_id=user_id).first()
        if item is None:
            return jsonify({"error": "History item not found"}), 404

        workspace = jobs_root / job_id
        if workspace.exists() and workspace.is_dir():
            shutil.rmtree(workspace, ignore_errors=True)

        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "History item deleted"})

    @app.post("/api/v1/mix-sessions/plan")
    @jwt_required()
    def create_mix_session_plan():
        user_id = str(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            return jsonify({"error": "prompt is required"}), 400

        session = create_mix_session(user_id=user_id, prompt=prompt)
        workspace = create_workspace(session.id)

        try:
            from ai.mix_agent_flow import create_mix_proposal

            proposal_payload = create_mix_proposal(prompt, session_dir=str(workspace))
            downloaded_tracks: list[dict[str, Any]] = []
            for raw_track in proposal_payload.get("tracks", []):
                if not isinstance(raw_track, dict):
                    continue
                track = dict(raw_track)
                preview_filename = os.path.basename(str(track.get("preview_filename", "")).strip())
                if preview_filename:
                    track["preview_url"] = build_file_url(session.id, preview_filename)
                downloaded_tracks.append(track)

            session.planner_requirements = proposal_payload.get("requirements", {})
            session.downloaded_tracks = downloaded_tracks
            session.engineer_proposal = proposal_payload.get("proposal", {})
            session.client_questions = proposal_payload.get("client_questions", [])
            session.follow_up_questions = proposal_payload.get("proposal", {}).get("questions_for_client", [])
            session.status = "awaiting_client"
            session.updated_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as exc:
            app.logger.exception("mix-session planning failed for session %s", session.id)
            session.status = "failed"
            session.follow_up_questions = []
            session.final_output = {"error": str(exc)[:1200]}
            session.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({"error": str(exc), "session_id": session.id}), 500

        return jsonify(
            {
                "message": "Mix proposal created successfully.",
                "session": session.to_dict(),
            }
        )

    @app.get("/api/v1/mix-sessions")
    @jwt_required()
    def list_mix_sessions():
        user_id = str(get_jwt_identity())
        page = max(1, int(request.args.get("page", 1)))
        limit = min(50, max(1, int(request.args.get("limit", 10))))
        pagination = (
            MixSession.query.filter_by(user_id=user_id)
            .order_by(MixSession.created_at.desc())
            .paginate(page=page, per_page=limit, error_out=False)
        )
        return jsonify(
            {
                "items": [item.to_dict() for item in pagination.items],
                "page": page,
                "limit": limit,
                "total": pagination.total,
                "pages": pagination.pages,
            }
        )

    @app.get("/api/v1/mix-sessions/<session_id>")
    @jwt_required()
    def get_mix_session(session_id: str):
        user_id = str(get_jwt_identity())
        session = MixSession.query.filter_by(id=session_id, user_id=user_id).first()
        if session is None:
            return jsonify({"error": "Mix session not found"}), 404
        return jsonify({"session": session.to_dict()})

    @app.post("/api/v1/mix-sessions/<session_id>/finalize")
    @jwt_required()
    def finalize_mix_session(session_id: str):
        user_id = str(get_jwt_identity())
        session = MixSession.query.filter_by(id=session_id, user_id=user_id).first()
        if session is None:
            return jsonify({"error": "Mix session not found"}), 404

        payload = request.get_json(silent=True) or {}
        proposal = payload.get("proposal")
        if not isinstance(proposal, dict) or not isinstance(proposal.get("segments"), list):
            return jsonify({"error": "proposal with segments is required"}), 400

        answers = payload.get("answers", {})
        if not isinstance(answers, dict):
            answers = {}

        from ai.mix_agent_flow import finalize_mix_proposal, review_client_submission

        follow_ups = review_client_submission(session.client_questions or [], answers)
        session.client_answers = answers
        session.engineer_proposal = proposal
        session.updated_at = datetime.now(timezone.utc)

        if follow_ups:
            session.status = "awaiting_clarification"
            session.follow_up_questions = follow_ups
            db.session.commit()
            return jsonify(
                {
                    "status": "needs_clarification",
                    "session": session.to_dict(),
                    "questions": follow_ups,
                }
            )

        session.status = "rendering"
        session.follow_up_questions = []
        db.session.commit()

        job = create_job(
            user_id=user_id,
            generation_type="ai_parody",
            payload={"prompt": session.prompt, "session_id": session.id, "mode": "guided_mix_finalize"},
        )

        workspace = create_workspace(session.id)

        try:
            outputs = finalize_mix_proposal(
                session_dir=str(workspace),
                proposal=proposal,
            )
            mp3_filename = Path(outputs["mp3_path"]).name
            wav_filename = Path(outputs["wav_path"]).name
            mp3_url = build_file_url(session.id, mp3_filename)
            wav_url = build_file_url(session.id, wav_filename)

            mark_job_success(job, mp3_url)
            session.status = "completed"
            session.final_output = {
                "mp3_url": mp3_url,
                "wav_url": wav_url,
                "job_id": job.id,
            }
            session.completed_at = datetime.now(timezone.utc)
            session.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify(
                {
                    "status": "completed",
                    "session": session.to_dict(),
                    "output": session.final_output,
                    "job_id": job.id,
                }
            )
        except Exception as exc:
            app.logger.exception("mix-session finalize failed for session %s", session.id)
            mark_job_failure(job, str(exc))
            session.status = "failed"
            session.final_output = {"error": str(exc)[:1200], "job_id": job.id}
            session.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({"error": str(exc), "session": session.to_dict(), "job_id": job.id}), 500

    @app.post("/api/v1/mix-chats")
    @jwt_required()
    def create_mix_chat():
        user_id = str(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip()
        initial_prompt = str(payload.get("initial_prompt", "")).strip()
        mode = str(payload.get("mode", "refine_last")).strip() or "refine_last"

        thread = create_mix_chat_thread(
            user_id=user_id,
            title=title or (_derive_chat_title_from_prompt(initial_prompt) if initial_prompt else "New Mix Chat"),
        )

        response_payload: dict[str, Any] = {"thread": thread_payload_with_planning_state(thread)}
        if initial_prompt:
            guided_planning_enabled = _read_bool_env("AI_GUIDED_PLANNING_ENABLED", True)
            guided_max_rounds = _coerce_int(os.environ.get("AI_GUIDED_MAX_ROUNDS"), 5)
            if guided_max_rounds < 1:
                guided_max_rounds = 5
            guided_min_rounds = _coerce_int(os.environ.get("AI_GUIDED_MIN_ROUNDS"), 1)
            if guided_min_rounds < 0:
                guided_min_rounds = 0
            if guided_min_rounds > guided_max_rounds:
                guided_min_rounds = guided_max_rounds

            if guided_planning_enabled:
                user_message, assistant_message, run = create_mix_chat_run(
                    thread=thread,
                    content=initial_prompt,
                    mode=mode,
                    run_kind="planning_intake",
                    user_content_json={"kind": "prompt"},
                    assistant_kind="planning_questions",
                    assistant_placeholder_text="Analyzing your brief and preparing planning questions...",
                )
                draft = MixChatPlanDraft(
                    thread_id=thread.id,
                    source_user_message_id=user_message.id,
                    status="collecting",
                    round_count=0,
                    max_rounds=guided_max_rounds,
                    confidence_score=0.0,
                    required_slots_json={},
                    questions_json=[],
                    answers_json={},
                    proposal_json={},
                    resolution_notes_json={"min_rounds": guided_min_rounds},
                    conversation_summary_json={
                        "source_prompt": initial_prompt[:1200],
                        "recent_turns": [{"role": "user", "text": initial_prompt[:700], "kind": "prompt"}],
                    },
                    constraint_contract_json={},
                    pending_clarifications_json=[],
                    last_planner_trace_json={},
                    adjustment_policy=(
                        "minor_auto_adjust_allowed"
                        if _read_bool_env("AI_PLAN_MINOR_TIMING_ADJUSTMENTS", True)
                        else "strict_boundaries"
                    ),
                )
                db.session.add(draft)
                db.session.flush()
                run.input_summary_json = {
                    "draft_id": draft.id,
                    "source_user_message_id": user_message.id,
                }
                db.session.commit()
            else:
                user_message, assistant_message, run = create_mix_chat_run(
                    thread=thread,
                    content=initial_prompt,
                    mode=mode,
                )
            enqueue_mix_chat_run(run.id)
            response_payload.update(
                {
                    "user_message": user_message.to_dict(),
                    "assistant_message_placeholder": assistant_message.to_dict(),
                    "run": run.to_dict(),
                }
            )
        return jsonify(response_payload), 201

    @app.get("/api/v1/mix-chats")
    @jwt_required()
    def list_mix_chats():
        user_id = str(get_jwt_identity())
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
        archived = str(request.args.get("archived", "false")).strip().lower() in {"1", "true", "yes", "on"}

        query = MixChatThread.query.filter_by(user_id=user_id, archived=archived)
        query = query.order_by(
            func.coalesce(MixChatThread.last_message_at, MixChatThread.created_at).desc(),
            MixChatThread.created_at.desc(),
        )
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        thread_ids = [item.id for item in pagination.items]
        latest_draft_by_thread: dict[str, MixChatPlanDraft] = {}
        if thread_ids:
            drafts = (
                MixChatPlanDraft.query.filter(MixChatPlanDraft.thread_id.in_(thread_ids))
                .filter(MixChatPlanDraft.status.in_(list(ACTIVE_PLANNING_STATUSES)))
                .order_by(
                    MixChatPlanDraft.thread_id.asc(),
                    MixChatPlanDraft.updated_at.desc(),
                    MixChatPlanDraft.created_at.desc(),
                )
                .all()
            )
            for draft in drafts:
                if draft.thread_id not in latest_draft_by_thread:
                    latest_draft_by_thread[draft.thread_id] = draft

        items: list[dict[str, Any]] = []
        for item in pagination.items:
            payload = item.to_dict()
            draft = latest_draft_by_thread.get(item.id)
            if draft is not None:
                payload["planning_status"] = draft.status
                payload["planning_draft_id"] = draft.id
                payload["planning_round_count"] = int(draft.round_count or 0)
                payload["active_planning_status"] = draft.status
                payload["active_planning_draft_id"] = draft.id
            else:
                payload["planning_status"] = None
                payload["planning_draft_id"] = None
                payload["planning_round_count"] = 0
                payload["active_planning_status"] = None
                payload["active_planning_draft_id"] = None
            items.append(payload)

        return jsonify(
            {
                "items": items,
                "page": page,
                "limit": limit,
                "total": pagination.total,
                "pages": pagination.pages,
            }
        )

    @app.get("/api/v1/mix-memory")
    @jwt_required()
    def get_mix_memory():
        user_id = str(get_jwt_identity())
        memory = MixUserMemory.query.filter_by(user_id=user_id).first()
        if memory is None:
            memory = MixUserMemory(
                user_id=user_id,
                profile_json={},
                feedback_json={},
                use_case_profiles_json={},
                template_pack_json={},
                quality_json={},
            )
            db.session.add(memory)
            db.session.commit()
        return jsonify({"memory": memory.to_dict()})

    @app.patch("/api/v1/mix-chats/<thread_id>")
    @jwt_required()
    def update_mix_chat(thread_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404

        payload = request.get_json(silent=True) or {}
        if "title" in payload:
            title = str(payload.get("title", "")).strip()
            thread.title = (title[:255] or thread.title)
        if "archived" in payload:
            thread.archived = bool(payload.get("archived"))
        thread.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"thread": thread_payload_with_planning_state(thread)})

    @app.delete("/api/v1/mix-chats/<thread_id>")
    @jwt_required()
    def archive_mix_chat(thread_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404

        thread.archived = True
        thread.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"thread": thread_payload_with_planning_state(thread), "message": "Thread archived."})

    @app.get("/api/v1/mix-chats/<thread_id>/messages")
    @jwt_required()
    def list_mix_chat_messages(thread_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404

        limit = min(100, max(1, int(request.args.get("limit", 30))))
        cursor = str(request.args.get("cursor", "")).strip()

        query = MixChatMessage.query.filter_by(thread_id=thread_id)
        if cursor:
            cursor_message = MixChatMessage.query.filter_by(id=cursor, thread_id=thread_id).first()
            if cursor_message is not None:
                query = query.filter(MixChatMessage.created_at < cursor_message.created_at)

        messages_desc = query.order_by(MixChatMessage.created_at.desc()).limit(limit + 1).all()
        has_more = len(messages_desc) > limit
        messages = list(reversed(messages_desc[:limit]))
        next_cursor = messages[0].id if has_more and messages else None

        return jsonify(
            {
                "items": [message.to_dict() for message in messages],
                "next_cursor": next_cursor,
                "has_more": has_more,
            }
        )

    @app.post("/api/v1/mix-chats/<thread_id>/messages")
    @jwt_required()
    def create_mix_chat_message_endpoint(thread_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404
        if thread.archived:
            return jsonify({"error": "Cannot send messages to an archived thread"}), 400

        payload = request.get_json(silent=True) or {}
        content = str(payload.get("content", "")).strip()
        mode = str(payload.get("mode", "refine_last")).strip() or "refine_last"
        planning_target = str(payload.get("planning_target", "auto")).strip().lower() or "auto"
        explicit_draft_id = str(payload.get("draft_id", "")).strip()
        revision_mode = str(payload.get("revision_mode", "")).strip().lower()
        timeline_resolution_raw = payload.get("timeline_resolution")
        timeline_resolution = str(timeline_resolution_raw or "").strip().lower() if timeline_resolution_raw is not None else "unspecified"
        planning_response_payload = payload.get("planning_response")
        planning_action_payload = payload.get("planning_action")

        try:
            attachments = _normalize_timeline_attachments(payload.get("attachments"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        has_prompt_payload = bool(content) or bool(attachments)
        has_planning_response = isinstance(planning_response_payload, dict)
        has_planning_action = isinstance(planning_action_payload, dict)
        payload_modes_selected = int(has_prompt_payload) + int(has_planning_response) + int(has_planning_action)
        if payload_modes_selected != 1:
            return (
                jsonify(
                    {
                        "error": (
                            "Exactly one payload mode is required: "
                            "prompt/attachments OR planning_response OR planning_action."
                        )
                    }
                ),
                400,
            )

        allowed_planning_targets = {"auto", "existing_draft", "new_draft"}
        if planning_target not in allowed_planning_targets:
            return jsonify({"error": "planning_target is invalid"}), 400

        attachment_flow_enabled = _read_bool_env("AI_TIMELINE_ATTACHMENT_FLOW_ENABLED", True)
        if attachments and not attachment_flow_enabled:
            return jsonify({"error": "Timeline attachment flow is disabled"}), 400

        allowed_timeline_resolutions = {
            "unspecified",
            "keep_attached_cuts",
            "replan_with_prompt",
            "replace_timeline",
        }
        if timeline_resolution not in allowed_timeline_resolutions:
            return jsonify({"error": "timeline_resolution is invalid"}), 400
        if timeline_resolution != "unspecified" and not attachments:
            return jsonify({"error": "timeline_resolution requires a timeline attachment"}), 400

        guided_planning_enabled = _read_bool_env("AI_GUIDED_PLANNING_ENABLED", True)
        guided_first_run_only = _read_bool_env("AI_GUIDED_FIRST_RUN_ONLY", True)
        guided_max_rounds = _coerce_int(os.environ.get("AI_GUIDED_MAX_ROUNDS"), 5)
        if guided_max_rounds < 1:
            guided_max_rounds = 5
        guided_min_rounds = _coerce_int(os.environ.get("AI_GUIDED_MIN_ROUNDS"), 1)
        if guided_min_rounds < 0:
            guided_min_rounds = 0
        if guided_min_rounds > guided_max_rounds:
            guided_min_rounds = guided_max_rounds

        active_draft = get_active_plan_draft(thread_id)
        explicit_target_draft: Optional[MixChatPlanDraft] = None
        if explicit_draft_id:
            explicit_target_draft = MixChatPlanDraft.query.filter_by(
                id=explicit_draft_id,
                thread_id=thread_id,
            ).first()
            if explicit_target_draft is None:
                return jsonify({"error": "draft_id is invalid"}), 404

        if has_planning_response:
            planning_response = planning_response_payload if isinstance(planning_response_payload, dict) else {}
            draft_id = str(planning_response.get("draft_id", "")).strip()
            if not draft_id:
                return jsonify({"error": "planning_response.draft_id is required"}), 400

            draft = MixChatPlanDraft.query.filter_by(id=draft_id, thread_id=thread_id).first()
            if draft is None:
                return jsonify({"error": "planning_response.draft_id is invalid"}), 404
            if draft.status in {"approved", "superseded", "executed", "cancelled"}:
                return (
                    jsonify(
                        {
                            "error": (
                                f"Plan draft {draft.id[:8]} is {draft.status} and cannot accept new answers."
                            )
                        }
                    ),
                    409,
                )

            try:
                normalized_answers = _normalize_planning_answers(planning_response.get("answers"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

            answer_summary = ", ".join(
                f"{item['question_id']}={item['selected_option_id'] or 'other'}"
                for item in normalized_answers[:4]
            )
            content_text = f"Planning answers submitted for draft {draft.id[:8]}: {answer_summary}"

            user_message, assistant_message, run = create_mix_chat_run(
                thread=thread,
                content=content_text,
                mode="refine_last",
                run_kind="planning_revision",
                user_content_json={
                    "kind": "planning_answers",
                    "draft_id": draft.id,
                    "answers": normalized_answers,
                },
                assistant_kind="planning_questions",
                assistant_placeholder_text="Reviewing your answers and updating the mix plan...",
                input_summary_json={
                    "draft_id": draft.id,
                    "answers": normalized_answers,
                    "source": "planning_response",
                    "planning_target": planning_target,
                    "draft_override_id": explicit_draft_id or None,
                    "revision_mode": revision_mode or "chips",
                    "recent_conversation": summarize_recent_thread_context(thread.id),
                },
            )

        elif has_planning_action:
            planning_action = planning_action_payload if isinstance(planning_action_payload, dict) else {}
            draft_id = str(planning_action.get("draft_id", "")).strip()
            action = str(planning_action.get("action", "")).strip().lower()
            revision_prompt = str(planning_action.get("revision_prompt", "")).strip()[:2000]
            if not draft_id:
                return jsonify({"error": "planning_action.draft_id is required"}), 400
            if action not in {"approve_plan", "revise_plan"}:
                return jsonify({"error": "planning_action.action must be approve_plan or revise_plan"}), 400

            draft = MixChatPlanDraft.query.filter_by(id=draft_id, thread_id=thread_id).first()
            if draft is None:
                return jsonify({"error": "planning_action.draft_id is invalid"}), 404
            if draft.status in {"executed", "superseded", "cancelled"}:
                return (
                    jsonify(
                        {
                            "error": f"Plan draft {draft.id[:8]} is {draft.status} and cannot be updated."
                        }
                    ),
                    409,
                )

            if action == "approve_plan":
                if draft.status != "draft_ready":
                    return jsonify({"error": "Plan draft is not ready for approval yet"}), 409
                draft.status = "approved"
                draft.approved_at = datetime.now(timezone.utc)
                draft.updated_at = datetime.now(timezone.utc)
                db.session.commit()

                user_message, assistant_message, run = create_mix_chat_run(
                    thread=thread,
                    content=f"Approved plan draft {draft.id[:8]}.",
                    mode="refine_last",
                    run_kind="planning_execute",
                    user_content_json={
                        "kind": "planning_approval",
                        "draft_id": draft.id,
                        "action": "approve_plan",
                    },
                    assistant_kind="planning_approved_render_started",
                    assistant_placeholder_text="Plan approved. Starting render...",
                    input_summary_json={
                        "draft_id": draft.id,
                        "action": "approve_plan",
                        "planning_target": planning_target,
                        "recent_conversation": summarize_recent_thread_context(thread.id),
                    },
                )
            else:
                if draft.status == "approved":
                    draft.status = "collecting"
                    draft.approved_at = None
                    draft.updated_at = datetime.now(timezone.utc)
                    db.session.commit()

                revision_message = f"Requested plan revision for draft {draft.id[:8]}."
                if revision_prompt:
                    revision_message = f"{revision_message}\nRevision prompt: {revision_prompt}"

                user_message, assistant_message, run = create_mix_chat_run(
                    thread=thread,
                    content=revision_message,
                    mode="refine_last",
                    run_kind="planning_revision",
                    user_content_json={
                        "kind": "planning_revision_request",
                        "draft_id": draft.id,
                        "action": "revise_plan",
                        "revision_prompt": revision_prompt,
                    },
                    assistant_kind="planning_revision_questions",
                    assistant_placeholder_text="Revising the plan with targeted follow-up questions...",
                    input_summary_json={
                        "draft_id": draft.id,
                        "action": "revise_plan",
                        "revision_prompt": revision_prompt,
                        "planning_target": planning_target,
                        "draft_override_id": explicit_draft_id or None,
                        "revision_mode": revision_mode or "button",
                        "recent_conversation": summarize_recent_thread_context(thread.id),
                    },
                )

        elif attachments:
            attachment = attachments[0]
            source_version_id = str(attachment.get("source_version_id", "")).strip()
            source_version = MixChatVersion.query.filter_by(id=source_version_id, thread_id=thread_id).first()
            if source_version is None:
                return jsonify({"error": "attachments[0].source_version_id is invalid"}), 404

            has_prompt = bool(content)
            user_kind = "timeline_attachment_with_prompt" if has_prompt else "timeline_attachment_request"
            message_text = (
                content
                if has_prompt
                else (
                    f"Attached timeline from version {source_version.id[:8]} "
                    f"({len(attachment.get('segments', []))} segments)."
                )
            )

            user_message, assistant_message, run = create_mix_chat_run(
                thread=thread,
                content=message_text,
                mode=mode,
                run_kind="timeline_attachment",
                parent_version=source_version,
                user_content_json={
                    "kind": user_kind,
                    "attachments": attachments,
                    "timeline_resolution": timeline_resolution,
                },
                assistant_kind="timeline_attachment_result",
                assistant_placeholder_text="Reviewing attached timeline and your prompt...",
                input_summary_json={
                    "attachments": attachments,
                    "content": content,
                    "timeline_resolution": timeline_resolution,
                    "planning_target": planning_target,
                },
            )
        else:
            if not content:
                return jsonify({"error": "content is required"}), 400

            recent_context = summarize_recent_thread_context(thread.id)
            target_draft = explicit_target_draft
            if planning_target != "new_draft" and target_draft is None:
                target_draft = active_draft

            if planning_target == "existing_draft" and target_draft is None:
                return jsonify({"error": "No active planning draft found for this thread"}), 409
            if target_draft is not None and target_draft.status in {"superseded", "executed", "cancelled"}:
                return (
                    jsonify(
                        {
                            "error": f"Plan draft {target_draft.id[:8]} is {target_draft.status} and cannot be revised."
                        }
                    ),
                    409,
                )

            existing_versions_count = MixChatVersion.query.filter_by(thread_id=thread_id).count()
            force_guided_planning = planning_target in {"existing_draft", "new_draft"} or target_draft is not None
            should_use_guided_planning = guided_planning_enabled and (
                force_guided_planning or (not guided_first_run_only) or existing_versions_count == 0
            )

            if should_use_guided_planning:
                if target_draft is not None:
                    if target_draft.status == "approved":
                        target_draft.status = "collecting"
                        target_draft.approved_at = None
                        target_draft.updated_at = datetime.now(timezone.utc)
                        db.session.commit()

                    user_message, assistant_message, run = create_mix_chat_run(
                        thread=thread,
                        content=content,
                        mode=mode,
                        run_kind="planning_revision",
                        user_content_json={
                            "kind": "planning_freeform_revision",
                            "draft_id": target_draft.id,
                            "revision_prompt": content,
                            "planning_target": planning_target,
                        },
                        assistant_kind="planning_revision_questions",
                        assistant_placeholder_text="Reviewing your revision notes and updating the plan...",
                        input_summary_json={
                            "draft_id": target_draft.id,
                            "action": "freeform_revision",
                            "revision_prompt": content,
                            "planning_target": planning_target,
                            "draft_override_id": explicit_draft_id or None,
                            "revision_mode": revision_mode or "freeform",
                            "recent_conversation": recent_context,
                        },
                    )
                else:
                    stale_drafts = (
                        MixChatPlanDraft.query.filter_by(thread_id=thread_id)
                        .filter(MixChatPlanDraft.status.in_(list(ACTIVE_PLANNING_STATUSES)))
                        .all()
                    )
                    for stale in stale_drafts:
                        stale.status = "superseded"
                        stale.updated_at = datetime.now(timezone.utc)
                    if stale_drafts:
                        db.session.commit()

                    user_message, assistant_message, run = create_mix_chat_run(
                        thread=thread,
                        content=content,
                        mode=mode,
                        run_kind="planning_intake",
                        user_content_json={"kind": "prompt"},
                        assistant_kind="planning_questions",
                        assistant_placeholder_text="Analyzing your brief and preparing planning questions...",
                    )
                    draft = MixChatPlanDraft(
                        thread_id=thread.id,
                        source_user_message_id=user_message.id,
                        status="collecting",
                        round_count=0,
                        max_rounds=guided_max_rounds,
                        confidence_score=0.0,
                        required_slots_json={},
                        questions_json=[],
                        answers_json={},
                        proposal_json={},
                        resolution_notes_json={"min_rounds": guided_min_rounds},
                        conversation_summary_json={
                            "source_prompt": content[:1200],
                            "recent_turns": recent_context,
                        },
                        constraint_contract_json={},
                        pending_clarifications_json=[],
                        last_planner_trace_json={},
                        adjustment_policy=(
                            "minor_auto_adjust_allowed"
                            if _read_bool_env("AI_PLAN_MINOR_TIMING_ADJUSTMENTS", True)
                            else "strict_boundaries"
                        ),
                    )
                    db.session.add(draft)
                    db.session.flush()
                    run.input_summary_json = {
                        "draft_id": draft.id,
                        "source_user_message_id": user_message.id,
                        "planning_target": planning_target,
                        "draft_override_id": explicit_draft_id or None,
                        "revision_mode": revision_mode or "freeform",
                        "recent_conversation": recent_context,
                    }
                    db.session.commit()
            else:
                user_message, assistant_message, run = create_mix_chat_run(
                    thread=thread,
                    content=content,
                    mode=mode,
                )

        enqueued = enqueue_mix_chat_run(run.id)
        if not enqueued:
            run.status = "failed"
            run.progress_stage = "failed"
            run.error_message = "Queue unavailable and inline fallback disabled."
            run.completed_at = datetime.now(timezone.utc)
            assistant_message.status = "failed"
            assistant_message.content_text = "Queue unavailable. Please retry."
            assistant_message.content_json = {"kind": "error", "error": run.error_message}
            db.session.commit()
            return jsonify({"error": run.error_message, "run": run.to_dict()}), 503

        return (
            jsonify(
                {
                    "user_message": user_message.to_dict(),
                    "assistant_message_placeholder": assistant_message.to_dict(),
                    "run": run.to_dict(),
                    "poll_hint_ms": int(os.environ.get("MIX_CHAT_POLL_HINT_MS", "2000")),
                }
            ),
            202,
        )

    @app.post("/api/v1/mix-chats/<thread_id>/versions/<version_id>/edit-runs")
    @jwt_required()
    def create_mix_chat_edit_run(thread_id: str, version_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404
        if thread.archived:
            return jsonify({"error": "Cannot send messages to an archived thread"}), 400

        version = MixChatVersion.query.filter_by(id=version_id, thread_id=thread_id).first()
        if version is None:
            return jsonify({"error": "Version not found"}), 404

        payload = request.get_json(silent=True) or {}
        note = str(payload.get("note", "")).strip()
        editor_metadata = payload.get("editor_metadata", {})
        if not isinstance(editor_metadata, dict):
            editor_metadata = {}

        try:
            normalized_segments = _normalize_timeline_edit_segments(payload.get("segments"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        changed_segment_ids_raw = editor_metadata.get("changed_segment_ids", [])
        changed_segment_ids = (
            [str(item).strip()[:80] for item in changed_segment_ids_raw if str(item).strip()]
            if isinstance(changed_segment_ids_raw, list)
            else []
        )

        content_text = (
            f"Applied timeline edits to version {version.id[:8]} "
            f"({len(changed_segment_ids) or len(normalized_segments)} segments updated)."
        )
        if note:
            content_text = f"{content_text}\nNote: {note[:500]}"

        summary_payload = {
            "source_version_id": version.id,
            "segments": normalized_segments,
            "note": note[:1200],
            "editor_metadata": {
                "changed_segment_ids": changed_segment_ids,
            },
        }
        user_content_json = {
            "kind": "timeline_edit_request",
            **summary_payload,
        }

        user_message, assistant_message, run = create_mix_chat_run(
            thread=thread,
            content=content_text,
            mode="refine_last",
            run_kind="timeline_edit",
            parent_version=version,
            user_content_json=user_content_json,
            assistant_kind="timeline_edit_result",
            assistant_placeholder_text="Applying your timeline edits and rendering updated mix...",
            input_summary_json=summary_payload,
        )

        enqueued = enqueue_mix_chat_run(run.id)
        if not enqueued:
            run.status = "failed"
            run.progress_stage = "failed"
            run.error_message = "Queue unavailable and inline fallback disabled."
            run.completed_at = datetime.now(timezone.utc)
            assistant_message.status = "failed"
            assistant_message.content_text = "Queue unavailable. Please retry."
            assistant_message.content_json = {"kind": "error", "error": run.error_message}
            db.session.commit()
            return jsonify({"error": run.error_message, "run": run.to_dict()}), 503

        return (
            jsonify(
                {
                    "user_message": user_message.to_dict(),
                    "assistant_message_placeholder": assistant_message.to_dict(),
                    "run": run.to_dict(),
                    "poll_hint_ms": int(os.environ.get("MIX_CHAT_POLL_HINT_MS", "2000")),
                }
            ),
            202,
        )

    @app.get("/api/v1/mix-chats/<thread_id>/plan-drafts/<draft_id>")
    @jwt_required()
    def get_mix_chat_plan_draft(thread_id: str, draft_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404

        draft = MixChatPlanDraft.query.filter_by(id=draft_id, thread_id=thread_id).first()
        if draft is None:
            return jsonify({"error": "Plan draft not found"}), 404
        return jsonify({"draft": draft.to_dict()})

    @app.get("/api/v1/mix-chat-runs/<run_id>")
    @jwt_required()
    def get_mix_chat_run(run_id: str):
        user_id = str(get_jwt_identity())
        run = (
            MixChatRun.query.join(MixChatThread, MixChatRun.thread_id == MixChatThread.id)
            .filter(MixChatRun.id == run_id, MixChatThread.user_id == user_id)
            .first()
        )
        if run is None:
            return jsonify({"error": "Mix chat run not found"}), 404

        payload = run.to_dict()
        payload["assistant_message"] = (
            MixChatMessage.query.filter_by(id=run.assistant_message_id).first().to_dict()
            if run.assistant_message_id
            else None
        )
        return jsonify({"run": payload})

    @app.get("/api/v1/mix-chat-runs/<run_id>/events")
    def stream_mix_chat_run_events(run_id: str):
        user_id = resolve_identity_for_file_access()
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        run = (
            MixChatRun.query.join(MixChatThread, MixChatRun.thread_id == MixChatThread.id)
            .filter(MixChatRun.id == run_id, MixChatThread.user_id == user_id)
            .first()
        )
        if run is None:
            return jsonify({"error": "Mix chat run not found"}), 404

        poll_seconds = max(1, min(10, int(os.environ.get("MIX_CHAT_SSE_POLL_SECONDS", "1"))))
        heartbeat_seconds = max(5, min(60, int(os.environ.get("MIX_CHAT_SSE_HEARTBEAT_SECONDS", "15"))))
        max_seconds = max(20, min(600, int(os.environ.get("MIX_CHAT_SSE_MAX_SECONDS", "180"))))

        def _sse_event(event_name: str, payload: dict[str, Any]) -> str:
            return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"

        @stream_with_context
        def event_stream():
            started = time.monotonic()
            last_payload_serialized = ""
            last_heartbeat = started

            while True:
                current_run = (
                    MixChatRun.query.join(MixChatThread, MixChatRun.thread_id == MixChatThread.id)
                    .filter(MixChatRun.id == run_id, MixChatThread.user_id == user_id)
                    .first()
                )
                if current_run is None:
                    yield _sse_event("run_update", {"run_id": run_id, "terminal": True, "missing": True})
                    break

                run_payload = current_run.to_dict()
                terminal = current_run.status in {"completed", "failed"}
                envelope = {
                    "run": run_payload,
                    "terminal": terminal,
                }
                serialized = json.dumps(envelope, separators=(",", ":"))
                if serialized != last_payload_serialized:
                    yield f"event: run_update\ndata: {serialized}\n\n"
                    last_payload_serialized = serialized

                now = time.monotonic()
                if terminal:
                    break

                if now - last_heartbeat >= heartbeat_seconds:
                    yield "event: ping\ndata: {}\n\n"
                    last_heartbeat = now

                if now - started >= max_seconds:
                    yield _sse_event(
                        "stream_end",
                        {"run_id": run_id, "reason": "max_duration_reached"},
                    )
                    break

                time.sleep(poll_seconds)

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/api/v1/mix-chats/<thread_id>/versions")
    @jwt_required()
    def list_mix_chat_versions(thread_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404

        limit = min(100, max(1, int(request.args.get("limit", 50))))
        versions = (
            MixChatVersion.query.filter_by(thread_id=thread_id)
            .order_by(MixChatVersion.created_at.desc())
            .limit(limit)
            .all()
        )
        return jsonify({"items": [version.to_dict() for version in versions]})

    @app.post("/api/v1/mix-chats/<thread_id>/versions/<version_id>/render")
    @jwt_required()
    def render_mix_chat_version(thread_id: str, version_id: str):
        user_id = str(get_jwt_identity())
        thread = MixChatThread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread is None:
            return jsonify({"error": "Mix chat thread not found"}), 404

        version = MixChatVersion.query.filter_by(id=version_id, thread_id=thread_id).first()
        if version is None:
            return jsonify({"error": "Version not found"}), 404
        if not version.mix_session_id:
            return jsonify({"error": "Version has no mix session workspace for rendering"}), 400

        payload = request.get_json(silent=True) or {}
        proposal_override = payload.get("proposal")
        proposal_payload = version.proposal_json if isinstance(version.proposal_json, dict) else {}
        proposal = proposal_payload.get("proposal", {})
        if isinstance(proposal_override, dict):
            proposal = proposal_override
        if not isinstance(proposal, dict) or not isinstance(proposal.get("segments"), list):
            return jsonify({"error": "proposal with segments is required"}), 400

        workspace = create_workspace(version.mix_session_id)

        try:
            from ai.mix_agent_flow import finalize_mix_proposal

            outputs = finalize_mix_proposal(
                session_dir=str(workspace),
                proposal=proposal,
            )
            mp3_filename = Path(outputs["mp3_path"]).name
            wav_filename = Path(outputs["wav_path"]).name
            mp3_url = build_relative_file_url(version.mix_session_id, mp3_filename)
            wav_url = build_relative_file_url(version.mix_session_id, wav_filename)

            job = create_job(
                user_id=user_id,
                generation_type="ai_parody",
                payload={"thread_id": thread_id, "version_id": version_id, "mode": "chat_rerender"},
            )
            mark_job_success(job, mp3_url)

            final_output = {"mp3_url": mp3_url, "wav_url": wav_url, "job_id": job.id}
            version.final_output_json = final_output
            if isinstance(version.proposal_json, dict):
                updated = dict(version.proposal_json)
                updated["proposal"] = proposal
                version.proposal_json = updated
            db.session.commit()

            assistant_message = (
                MixChatMessage.query.filter_by(id=version.assistant_message_id, thread_id=thread_id).first()
                if version.assistant_message_id
                else None
            )
            if assistant_message is not None:
                current_json = dict(assistant_message.content_json or {})
                current_json["final_output"] = final_output
                current_json["proposal"] = proposal
                assistant_message.content_json = current_json
                assistant_message.updated_at = datetime.now(timezone.utc)
                db.session.commit()

            return jsonify({"output": final_output, "version": version.to_dict()})
        except Exception as exc:
            app.logger.exception("chat version render failed for version %s", version.id)
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/v1/process-array")
    @jwt_required()
    def process_array():
        user_id = str(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        url_entries = payload.get("urls", [])

        if not isinstance(url_entries, list) or not url_entries:
            return jsonify({"error": "urls array is required"}), 400

        parsed_urls: list[list[Any]] = []
        for item in url_entries:
            if not isinstance(item, dict):
                return jsonify({"error": "Each item in urls must be an object"}), 400

            url = str(item.get("url", "")).strip()
            if not url:
                return jsonify({"error": "Each item must include a valid url"}), 400

            try:
                start = _parse_time_to_seconds(item.get("start", "00:00"))
                end = _parse_time_to_seconds(item.get("end", "00:30"))
            except ValueError as error:
                return jsonify({"error": str(error)}), 400

            if end <= start:
                return jsonify({"error": "end must be greater than start"}), 400

            parsed_urls.append([url, start, end])

        job = create_job(user_id=user_id, generation_type="audio_mix", payload=payload)
        workspace = create_workspace(job.id)

        try:
            from features.audio_download import download_audio
            from features.audio_merge import merge_audio
            from features.audio_split import split_audio

            temp_dir = workspace / "temp"
            split_dir = workspace / "temp" / "split"
            output_dir = workspace / "static" / "output"

            names: list[str] = []
            for index, item in enumerate(parsed_urls):
                download_audio(item[0], name=str(index), output_dir=str(temp_dir))
                names.append(str(index))

            for name in names:
                index = int(name)
                start = parsed_urls[index][1]
                end = parsed_urls[index][2]
                split_audio(str(temp_dir / f"{name}.m4a"), start, end, output_dir=str(split_dir))

            split_files = [str(split_dir / f"{name}.mp3") for name in names]
            merged_file_path = merge_audio(split_files, output_dir=str(output_dir))

            if not merged_file_path or not Path(merged_file_path).exists():
                raise RuntimeError("Audio merge failed")

            filename = Path(merged_file_path).name
            file_url = build_file_url(job.id, filename)
            mark_job_success(job, file_url)

            return jsonify(
                {
                    "message": "Audio processing complete!",
                    "merged_file_path": file_url,
                    "job_id": job.id,
                }
            )
        except Exception as exc:
            app.logger.exception("process-array failed for job %s", job.id)
            mark_job_failure(job, str(exc))
            return jsonify({"error": str(exc), "job_id": job.id}), 500

    @app.post("/api/v1/process-csv")
    @jwt_required()
    def process_csv_endpoint():
        user_id = str(get_jwt_identity())

        if "file" not in request.files:
            return jsonify({"error": "file is required"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "file name cannot be empty"}), 400

        job = create_job(
            user_id=user_id,
            generation_type="audio_mix",
            payload={"filename": file.filename},
        )

        workspace = create_workspace(job.id)

        try:
            from features.audio_download import download_audio
            from features.audio_merge import merge_audio
            from features.audio_split import split_audio
            from features.read_csv import read_csv

            csv_dir = workspace / "csv"
            temp_dir = workspace / "temp"
            split_dir = workspace / "temp" / "split"
            output_dir = workspace / "static" / "output"

            csv_path = csv_dir / "input.csv"
            file.save(str(csv_path))

            url_start_end = read_csv(str(csv_path))
            if not url_start_end:
                raise RuntimeError("CSV did not contain valid rows")

            names: list[str] = []
            for index, row in enumerate(url_start_end):
                download_audio(row[0], name=str(index), output_dir=str(temp_dir))
                names.append(str(index))

            for name in names:
                index = int(name)
                split_audio(
                    str(temp_dir / f"{name}.m4a"),
                    int(url_start_end[index][1]),
                    int(url_start_end[index][2]),
                    output_dir=str(split_dir),
                )

            split_files = [str(split_dir / f"{name}.mp3") for name in names]
            merged_file_path = merge_audio(split_files, output_dir=str(output_dir))

            if not merged_file_path or not Path(merged_file_path).exists():
                raise RuntimeError("Audio merge failed")

            filename = Path(merged_file_path).name
            file_url = build_file_url(job.id, filename)
            mark_job_success(job, file_url)

            return jsonify(
                {
                    "message": "CSV processed successfully!",
                    "merged_file_path": file_url,
                    "job_id": job.id,
                }
            )
        except Exception as exc:
            app.logger.exception("process-csv failed for job %s", job.id)
            mark_job_failure(job, str(exc))
            return jsonify({"error": str(exc), "job_id": job.id}), 500

    @app.post("/api/v1/generate-ai")
    @jwt_required()
    def generate_ai_endpoint():
        user_id = str(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt", "")).strip()

        if not prompt:
            return jsonify({"error": "prompt is required"}), 400

        job = create_job(user_id=user_id, generation_type="ai_parody", payload={"prompt": prompt})
        workspace = create_workspace(job.id)

        try:
            from ai.ai import AIServiceError
            from ai.ai_main import generate_ai

            output_file = generate_ai(prompt, session_dir=str(workspace))
            if not output_file:
                raise RuntimeError("AI generation failed to produce output")

            output_path = Path(output_file)
            if not output_path.exists():
                raise RuntimeError("AI generation output file is missing")

            filename = output_path.name
            file_url = build_file_url(job.id, filename)
            mark_job_success(job, file_url)

            return jsonify(
                {
                    "message": "AI content generated successfully!",
                    "filepath": file_url,
                    "job_id": job.id,
                }
            )
        except AIServiceError as exc:
            app.logger.warning(
                "generate-ai upstream failure for job %s (%s): %s",
                job.id,
                exc.error_code,
                exc,
            )
            mark_job_failure(job, str(exc))
            payload: dict[str, Any] = {
                "error": str(exc),
                "code": exc.error_code,
                "job_id": job.id,
            }
            if exc.retry_after_seconds:
                payload["retry_after_seconds"] = exc.retry_after_seconds
            return jsonify(payload), exc.status_code
        except Exception as exc:
            app.logger.exception("generate-ai failed for job %s", job.id)
            mark_job_failure(job, str(exc))
            return jsonify({"error": str(exc), "job_id": job.id}), 500

    @app.post("/api/v1/download-video")
    @jwt_required()
    def download_video_endpoint():
        user_id = str(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        url = str(payload.get("url", "")).strip()

        if not url:
            return jsonify({"error": "url is required"}), 400

        job = create_job(user_id=user_id, generation_type="video_download", payload={"url": url})
        workspace = create_workspace(job.id)

        try:
            from features.download_video import download_highest_quality

            output_dir = workspace / "static" / "video_dl"
            result = download_highest_quality(url, str(output_dir))
            if not result:
                raise RuntimeError("Video download failed")

            filename = Path(result).name
            output_file = output_dir / filename
            if not output_file.exists():
                possible_absolute = Path(result)
                if possible_absolute.exists():
                    output_file = possible_absolute
                else:
                    raise RuntimeError("Downloaded video file missing")

            file_url = build_file_url(job.id, output_file.name)
            mark_job_success(job, file_url)

            return jsonify(
                {
                    "message": "Video downloaded successfully!",
                    "filepath": file_url,
                    "job_id": job.id,
                }
            )
        except Exception as exc:
            app.logger.exception("download-video failed for job %s", job.id)
            mark_job_failure(job, str(exc))
            return jsonify({"error": str(exc), "job_id": job.id}), 500

    @app.post("/api/v1/download-audio")
    @jwt_required()
    def download_audio_endpoint():
        user_id = str(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        url = str(payload.get("url", "")).strip()

        if not url:
            return jsonify({"error": "url is required"}), 400

        job = create_job(user_id=user_id, generation_type="audio_download", payload={"url": url})
        workspace = create_workspace(job.id)

        try:
            from features.download_audio import download_highest_quality_audio

            output_dir = workspace / "static" / "audio_dl"
            result = download_highest_quality_audio(url, str(output_dir))
            if not result:
                raise RuntimeError("Audio download failed")

            filename = Path(result).name
            output_file = output_dir / filename
            if not output_file.exists():
                possible_absolute = Path(result)
                if possible_absolute.exists():
                    output_file = possible_absolute
                else:
                    raise RuntimeError("Downloaded audio file missing")

            file_url = build_file_url(job.id, output_file.name)
            mark_job_success(job, file_url)

            return jsonify(
                {
                    "message": "Audio downloaded successfully!",
                    "filepath": file_url,
                    "job_id": job.id,
                }
            )
        except Exception as exc:
            app.logger.exception("download-audio failed for job %s", job.id)
            mark_job_failure(job, str(exc))
            return jsonify({"error": str(exc), "job_id": job.id}), 500

    @app.get("/files/<job_id>/<path:filename>")
    def serve_generated_file(job_id: str, filename: str):
        safe_filename = os.path.basename(filename)
        if safe_filename != filename:
            return jsonify({"error": "Invalid filename"}), 400

        job = GenerationJob.query.filter_by(id=job_id).first()
        session = MixSession.query.filter_by(id=job_id).first() if job is None else None
        if job is None and session is None:
            return jsonify({"error": "File not found"}), 404

        requester_id = resolve_identity_for_file_access()
        owner_id = job.user_id if job is not None else session.user_id  # type: ignore[union-attr]
        if requester_id != owner_id:
            return jsonify({"error": "Unauthorized"}), 403

        workspace = jobs_root / job_id
        if not workspace.exists():
            return jsonify({"error": "File not found"}), 404

        candidate_paths = [
            workspace / "static" / "output" / safe_filename,
            workspace / "static" / "video_dl" / safe_filename,
            workspace / "static" / "audio_dl" / safe_filename,
        ]

        for path in candidate_paths:
            if path.exists() and path.is_file():
                force_download = request.args.get("download") == "1"
                return send_file(str(path), as_attachment=force_download, download_name=safe_filename)

        return jsonify({"error": "File not found"}), 404

    with app.app_context():
        try:
            backfill_legacy_mix_sessions()
        except Exception:
            app.logger.exception("legacy mix session backfill failed")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
