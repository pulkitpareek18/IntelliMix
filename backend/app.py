import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request, send_file
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
from sqlalchemy import func
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


def create_app(test_config: Optional[dict[str, Any]] = None) -> Flask:
    app = Flask(__name__)

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
        if job is None:
            return jsonify({"error": "File not found"}), 404

        requester_id = resolve_identity_for_file_access()
        if requester_id != job.user_id:
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
