"""OrbitCode Self-Learning Engine - SQLite + Embeddings for mistake distillation and adaptive improvement"""
import sqlite3
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import threading

from orbitcode.config import get_settings


@dataclass
class ErrorEvent:
    """Recorded error event"""
    id: Optional[int]
    error_signature: str
    tool_name: str
    file_ext: str
    context_hash: str
    raw_error: str
    timestamp: float
    resolved: bool = False
    fix_applied: Optional[str] = None


@dataclass
class Lesson:
    """Distilled lesson from error->fix pairing"""
    id: Optional[int]
    error_pattern: str
    root_cause: str
    verified_fix: str
    tool_name: str
    file_ext: str
    confidence: float
    usage_count: int
    created_at: float
    last_used: float


@dataclass
class NegativeRule:
    """Hard constraint: never do this again"""
    id: Optional[int]
    rule: str
    context: str
    created_at: float
    strict: bool = True


@dataclass
class ModelPerformance:
    """Track per-model performance metrics"""
    model_name: str
    task_type: str  # planning, coding, debugging, reviewing, etc.
    success_count: int
    total_count: int
    avg_latency_ms: float
    avg_tokens: int
    last_updated: float


class LearningEngine:
    """Self-learning engine that distills mistakes into rules and adapts behavior"""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.db_path = self.settings.data_dir / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with all tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS error_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_signature TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    file_ext TEXT,
                    context_hash TEXT,
                    raw_error TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    resolved INTEGER DEFAULT 0,
                    fix_applied TEXT
                );

                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_pattern TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    verified_fix TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    file_ext TEXT,
                    confidence REAL DEFAULT 0.5,
                    usage_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_used REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS negative_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule TEXT NOT NULL UNIQUE,
                    context TEXT,
                    created_at REAL NOT NULL,
                    strict INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS model_performance (
                    model_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 0,
                    avg_latency_ms REAL DEFAULT 0,
                    avg_tokens INTEGER DEFAULT 0,
                    last_updated REAL NOT NULL,
                    PRIMARY KEY (model_name, task_type)
                );

                CREATE TABLE IF NOT EXISTS repo_playbook (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_path TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(repo_path, key)
                );

                CREATE TABLE IF NOT EXISTS search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL UNIQUE,
                    query TEXT NOT NULL,
                    results TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_error_signature ON error_events(error_signature);
                CREATE INDEX IF NOT EXISTS idx_lessons_pattern ON lessons(error_pattern);
                CREATE INDEX IF NOT EXISTS idx_negative_rules ON negative_rules(rule);
                CREATE INDEX IF NOT EXISTS idx_search_cache ON search_cache(query_hash);
            """)

    # ==================== ERROR EVENT LOGGING ====================

    def log_error(
        self,
        error: Exception,
        tool_name: str,
        file_path: Optional[str] = None,
        context: Optional[str] = None
    ) -> int:
        """Log an error event for later analysis"""
        error_signature = self._generate_signature(error, tool_name, context)
        file_ext = Path(file_path).suffix if file_path else ""
        context_hash = hashlib.md5((context or "").encode()).hexdigest()[:16]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO error_events
                   (error_signature, tool_name, file_ext, context_hash, raw_error, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (error_signature, tool_name, file_ext, context_hash, str(error), time.time())
            )
            return cursor.lastrowid or 0

    def _generate_signature(self, error: Exception, tool_name: str, context: Optional[str]) -> str:
        """Generate a unique signature for an error pattern"""
        error_type = type(error).__name__
        error_msg = str(error)[:200]
        key = f"{tool_name}:{error_type}:{error_msg}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    def mark_resolved(self, event_id: int, fix_applied: str) -> None:
        """Mark an error as resolved with the fix that worked"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE error_events SET resolved = 1, fix_applied = ? WHERE id = ?",
                (fix_applied, event_id)
            )
            # Try to distill a lesson
            self._try_distill_lesson(event_id, fix_applied)

    def _try_distill_lesson(self, event_id: int, fix_applied: str) -> None:
        """Attempt to distill a reusable lesson from resolved error"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT error_signature, tool_name, file_ext, raw_error FROM error_events WHERE id = ?",
                (event_id,)
            ).fetchone()

        if not row:
            return

        error_signature, tool_name, file_ext, raw_error = row

        # Simple heuristic: if same error happened 3+ times with same fix, create lesson
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                """SELECT COUNT(*) FROM error_events
                   WHERE error_signature = ? AND fix_applied = ? AND resolved = 1""",
                (error_signature, fix_applied)
            ).fetchone()[0]

        if count >= 2:  # Lowered threshold for faster learning
            self._create_lesson(error_signature, tool_name, file_ext, raw_error, fix_applied)

    def _create_lesson(
        self,
        error_pattern: str,
        tool_name: str,
        file_ext: str,
        raw_error: str,
        verified_fix: str
    ) -> None:
        """Create or update a lesson"""
        root_cause = self._infer_root_cause(raw_error, verified_fix)

        with sqlite3.connect(self.db_path) as conn:
            # Check if similar lesson exists
            existing = conn.execute(
                """SELECT id, confidence, usage_count FROM lessons
                   WHERE error_pattern = ? AND tool_name = ?""",
                (error_pattern, tool_name)
            ).fetchone()

            if existing:
                lesson_id, confidence, usage = existing
                new_confidence = min(0.95, confidence + 0.1)
                conn.execute(
                    """UPDATE lessons SET confidence = ?, verified_fix = ?, usage_count = ?, last_used = ?
                       WHERE id = ?""",
                    (new_confidence, verified_fix, usage + 1, time.time(), lesson_id)
                )
            else:
                conn.execute(
                    """INSERT INTO lessons
                       (error_pattern, root_cause, verified_fix, tool_name, file_ext, confidence, created_at, last_used)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (error_pattern, root_cause, verified_fix, tool_name, file_ext, 0.6, time.time(), time.time())
                )

    def _infer_root_cause(self, error: str, fix: str) -> str:
        """Simple heuristic to infer root cause from error and fix"""
        error_lower = error.lower()
        fix_lower = fix.lower()

        if "permission" in error_lower or "access denied" in error_lower:
            return "Permission issue - fix ensures proper permissions"
        if "not found" in error_lower or "no such file" in error_lower:
            return "Path/file missing - fix adds existence check or creates path"
        if "syntax" in error_lower or "indentation" in error_lower:
            return "Syntax error - fix corrects syntax"
        if "import" in error_lower or "modulenotfound" in error_lower:
            return "Missing dependency - fix adds import or installs package"
        if "timeout" in error_lower:
            return "Operation timeout - fix increases timeout or optimizes"
        if "connection" in error_lower or "refused" in error_lower:
            return "Network/connection issue - fix adds retry or fallback"

        return "Resolved via: " + fix[:100]

    # ==================== LESSON RETRIEVAL & INJECTION ====================

    def get_relevant_lessons(
        self,
        tool_name: str,
        file_ext: str = "",
        context: str = "",
        max_lessons: int = 3
    ) -> List[Lesson]:
        """Get top matching lessons for current context"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, error_pattern, root_cause, verified_fix, tool_name,
                          file_ext, confidence, usage_count, created_at, last_used
                   FROM lessons
                   WHERE tool_name = ?
                   ORDER BY confidence DESC, usage_count DESC
                   LIMIT ?""",
                (tool_name, max_lessons * 2)
            ).fetchall()

        lessons = [Lesson(*row) for row in rows]

        # Filter by file extension relevance
        if file_ext:
            ext_lessons = [l for l in lessons if l.file_ext == file_ext]
            if ext_lessons:
                lessons = ext_lessons[:max_lessons]

        return lessons[:max_lessons]

    def format_lessons_for_prompt(self, lessons: List[Lesson]) -> str:
        """Format lessons as prompt injection"""
        if not lessons:
            return ""

        lines = ["\n## Learned Lessons (from past mistakes):"]
        for i, lesson in enumerate(lessons, 1):
            lines.append(f"{i}. **When using {lesson.tool_name} on {lesson.file_ext or 'any'} files:**")
            lines.append(f"   - Pattern: {lesson.error_pattern}")
            lines.append(f"   - Root cause: {lesson.root_cause}")
            lines.append(f"   - Fix: {lesson.verified_fix}")
            lines.append(f"   - Confidence: {lesson.confidence:.0%} (used {lesson.usage_count}x)")
        lines.append("")
        return "\n".join(lines)

    # ==================== NEGATIVE CONSTRAINTS ====================

    def add_negative_rule(self, rule: str, context: str = "", strict: bool = True) -> bool:
        """Add a 'never do this again' rule"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO negative_rules (rule, context, created_at, strict) VALUES (?, ?, ?, ?)",
                    (rule, context, time.time(), 1 if strict else 0)
                )
            return True
        except sqlite3.IntegrityError:
            return False  # Already exists

    def check_negative_rules(self, tool_name: str, action: str, params: Dict) -> List[str]:
        """Check if any negative rules apply to this action"""
        violations = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT rule, context, strict FROM negative_rules").fetchall()

        for rule, context, strict in rows:
            if self._rule_matches(rule, tool_name, action, params):
                violations.append(f"⚠️ Negative rule violated: {rule}")
                if not strict:
                    violations[-1] += " (non-strict)"

        return violations

    def _rule_matches(self, rule: str, tool_name: str, action: str, params: Dict) -> bool:
        """Simple rule matching - can be extended with regex/pattern matching"""
        rule_lower = rule.lower()
        check_str = f"{tool_name} {action} {json.dumps(params)}".lower()

        # Support simple keywords
        keywords = rule_lower.split()
        return all(kw in check_str for kw in keywords if len(kw) > 2)

    def get_all_negative_rules(self) -> List[NegativeRule]:
        """Get all negative rules"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, rule, context, created_at, strict FROM negative_rules"
            ).fetchall()
        return [NegativeRule(*row) for row in rows]

    # ==================== MODEL PERFORMANCE TRACKING ====================

    def record_model_result(
        self,
        model_name: str,
        task_type: str,
        success: bool,
        latency_ms: float,
        tokens_used: int
    ) -> None:
        """Record model performance for dynamic re-ranking"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT success_count, total_count, avg_latency_ms, avg_tokens FROM model_performance WHERE model_name = ? AND task_type = ?",
                (model_name, task_type)
            ).fetchone()

            if row:
                s_count, t_count, avg_lat, avg_tok = row
                new_total = t_count + 1
                new_success = s_count + (1 if success else 0)
                new_avg_lat = (avg_lat * t_count + latency_ms) / new_total
                new_avg_tok = (avg_tok * t_count + tokens_used) / new_total
                conn.execute(
                    """UPDATE model_performance
                       SET success_count = ?, total_count = ?, avg_latency_ms = ?, avg_tokens = ?, last_updated = ?
                       WHERE model_name = ? AND task_type = ?""",
                    (new_success, new_total, new_avg_lat, new_avg_tok, time.time(), model_name, task_type)
                )
            else:
                conn.execute(
                    """INSERT INTO model_performance
                       (model_name, task_type, success_count, total_count, avg_latency_ms, avg_tokens, last_updated)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (model_name, task_type, 1 if success else 0, 1, latency_ms, tokens_used, time.time())
                )

    def get_model_rankings(self, task_type: str) -> List[Tuple[str, float]]:
        """Get models ranked by success rate for a task type"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT model_name, success_count, total_count, avg_latency_ms
                   FROM model_performance
                   WHERE task_type = ? AND total_count >= 3
                   ORDER BY (success_count * 1.0 / total_count) DESC, avg_latency_ms ASC""",
                (task_type,)
            ).fetchall()

        return [(row[0], row[1] / row[2]) for row in rows]

    # ==================== REPO PLAYBOOK ====================

    def save_playbook_entry(self, repo_path: str, key: str, value: str) -> None:
        """Save repo-specific convention/knowledge"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO repo_playbook (repo_path, key, value, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (repo_path, key, value, time.time())
            )

    def get_playbook(self, repo_path: str) -> Dict[str, str]:
        """Get all playbook entries for a repo"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, value FROM repo_playbook WHERE repo_path = ?",
                (repo_path,)
            ).fetchall()
        return dict(rows)

    def generate_playbook_markdown(self, repo_path: str) -> str:
        """Generate PLAYBOOK.md from learned repo conventions"""
        entries = self.get_playbook(repo_path)
        if not entries:
            return ""

        lines = ["# OrbitCode Project Playbook", f"\n*Auto-generated for {repo_path}*", ""]
        for key, value in sorted(entries.items()):
            lines.append(f"## {key}")
            lines.append(value)
            lines.append("")
        return "\n".join(lines)

    # ==================== SEARCH CACHE ====================

    def cache_search_results(self, query: str, results: List[Dict], ttl_hours: int = 72) -> None:
        """Cache search results with TTL"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        expires_at = time.time() + (ttl_hours * 3600)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO search_cache (query_hash, query, results, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (query_hash, query, json.dumps(results), time.time(), expires_at)
            )

    def get_cached_search(self, query: str) -> Optional[List[Dict]]:
        """Get cached search results if not expired"""
        query_hash = hashlib.md5(query.encode()).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT results, expires_at FROM search_cache WHERE query_hash = ?",
                (query_hash,)
            ).fetchone()

        if row and row[1] > time.time():
            return json.loads(row[0])
        return None

    # ==================== STATS & TELEMETRY ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get learning engine statistics"""
        with sqlite3.connect(self.db_path) as conn:
            error_count = conn.execute("SELECT COUNT(*) FROM error_events").fetchone()[0]
            lesson_count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            rule_count = conn.execute("SELECT COUNT(*) FROM negative_rules").fetchone()[0]
            cache_count = conn.execute("SELECT COUNT(*) FROM search_cache WHERE expires_at > ?", (time.time(),)).fetchone()[0]

            # Tokens saved estimation
            cache_hits = conn.execute(
                "SELECT COUNT(*) FROM search_cache WHERE expires_at > ?", (time.time(),)
            ).fetchone()[0]

        return {
            "errors_logged": error_count,
            "lessons_learned": lesson_count,
            "negative_rules": rule_count,
            "search_cache_entries": cache_count,
            "estimated_tokens_saved": cache_hits * 1500,  # rough estimate
        }


# Singleton instance
_learning_engine: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    """Get singleton learning engine instance"""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = LearningEngine()
    return _learning_engine