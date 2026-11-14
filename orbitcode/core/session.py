"""Session persistence for OrbitCode."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from contextlib import asynccontextmanager

import aiofiles
from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Integer, select
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session as SQLSession

from orbitcode.config import get_settings
from orbitcode.core.model_router import ChatMessage

Base = declarative_base()


class SessionModel(Base):
    """SQLAlchemy model for sessions."""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    project_path = Column(String(500), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    message_count = Column(Integer, default=0)
    data = Column(Text, nullable=False)  # JSONL of messages


@dataclass
class Session:
    """In-memory session representation."""
    id: str
    project_path: Path
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _dirty: bool = field(default=False, init=False)
    metadata: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str, tool_calls: list = None):
        """Add a message to the session."""
        msg = ChatMessage(role=role, content=content, tool_calls=tool_calls or [])
        self.messages.append(msg)
        self.updated_at = datetime.utcnow()
        self._dirty = True

    def to_jsonl(self) -> str:
        """Serialize messages to JSONL."""
        return "\n".join(msg.model_dump_json() for msg in self.messages)

    @classmethod
    def from_jsonl(cls, session_id: str, project_path: Path, jsonl: str, created_at: datetime, updated_at: datetime) -> "Session":
        messages = [ChatMessage.model_validate_json(line) for line in jsonl.strip().split("\n") if line.strip()]
        return cls(
            id=session_id,
            project_path=project_path,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
        )


class SessionManager:
    """Manages session persistence using SQLite."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.db_path = self.settings.session_dir / "sessions.db"
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._current_session: Optional[Session] = None

    def _get_db(self) -> SQLSession:
        return self.SessionLocal()

    def create_session(self, project_path: Path) -> Session:
        """Create a new session for a project."""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            project_path=project_path.resolve(),
        )
        self._save_session(session)
        self._current_session = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session by ID."""
        with self._get_db() as db:
            model = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if not model:
                return None
            return Session.from_jsonl(
                model.id,
                Path(model.project_path),
                model.data,
                model.created_at,
                model.updated_at,
            )

    def get_latest_session(self, project_path: Path) -> Optional[Session]:
        """Get the most recent session for a project."""
        project_str = str(project_path.resolve())
        with self._get_db() as db:
            model = db.query(SessionModel).filter(
                SessionModel.project_path == project_str
            ).order_by(SessionModel.updated_at.desc()).first()
            if not model:
                return None
            return Session.from_jsonl(
                model.id,
                Path(model.project_path),
                model.data,
                model.created_at,
                model.updated_at,
            )

    def list_sessions(self, project_path: Path, limit: int = 20) -> list[Session]:
        """List recent sessions for a project."""
        project_str = str(project_path.resolve())
        with self._get_db() as db:
            models = db.query(SessionModel).filter(
                SessionModel.project_path == project_str
            ).order_by(SessionModel.updated_at.desc()).limit(limit).all()
            return [
                Session.from_jsonl(m.id, Path(m.project_path), m.data, m.created_at, m.updated_at)
                for m in models
            ]

    def _save_session(self, session: Session):
        """Persist session to database."""
        with self._get_db() as db:
            model = db.query(SessionModel).filter(SessionModel.id == session.id).first()
            if not model:
                model = SessionModel(
                    id=session.id,
                    project_path=str(session.project_path),
                    created_at=session.created_at,
                )
                db.add(model)
            model.project_path = str(session.project_path)
            model.updated_at = session.updated_at
            model.message_count = len(session.messages)
            model.data = session.to_jsonl()
            db.commit()
        session._dirty = False

    def save_current(self):
        """Save the current session if dirty."""
        if self._current_session and self._current_session._dirty:
            self._save_session(self._current_session)

    def set_current(self, session: Session):
        """Set the current active session."""
        self._current_session = session

    def get_current(self) -> Optional[Session]:
        """Get the current active session."""
        return self._current_session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._get_db() as db:
            model = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if model:
                db.delete(model)
                db.commit()
                return True
        return False

    @asynccontextmanager
    async def auto_save(self, interval: int = 5):
        """Context manager for auto-saving session periodically."""
        import asyncio
        async def save_loop():
            while True:
                await asyncio.sleep(interval)
                self.save_current()
        task = asyncio.create_task(save_loop())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self.save_current()