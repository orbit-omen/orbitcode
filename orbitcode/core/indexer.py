"""Codebase indexing with local embeddings for semantic search."""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from orbitcode.config import get_settings


@dataclass
class CodeChunk:
    """A chunk of code with its embedding."""
    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    embedding: Optional[list[float]] = None


class CodeIndexer:
    """Indexes codebase for semantic search using local embeddings."""

    def __init__(self, working_dir: Path, settings=None):
        self.settings = settings or get_settings()
        self.working_dir = working_dir
        self.index_dir = self.settings.data_dir / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "code_index.db"
        self._init_db()
        self._embedder = None

    def _init_db(self):
        """Initialize SQLite database with vector support."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                language TEXT,
                embedding BLOB,
                file_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON chunks(file_hash)")
        conn.commit()
        conn.close()

    def _get_embedder(self):
        """Lazy-load the embedding model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                # Use a small, fast model for code
                self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            except ImportError:
                # Fallback: use a simple hash-based approach
                self._embedder = False
        return self._embedder

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute hash of file for change detection."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]

    def _chunk_file(self, file_path: Path, max_lines: int = 50) -> list[CodeChunk]:
        """Split a file into chunks."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        lines = content.splitlines()
        chunks = []
        language = self._detect_language(file_path)

        for i in range(0, len(lines), max_lines):
            chunk_lines = lines[i:i + max_lines]
            chunk_content = "\n".join(chunk_lines)
            if not chunk_content.strip():
                continue

            chunk_id = hashlib.sha256(f"{file_path}:{i}".encode()).hexdigest()[:16]
            chunks.append(CodeChunk(
                id=chunk_id,
                file_path=str(file_path.relative_to(self.working_dir)),
                content=chunk_content,
                start_line=i + 1,
                end_line=min(i + max_lines, len(lines)),
                language=language,
            ))
        return chunks

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from extension."""
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript", ".go": "go",
            ".rs": "rust", ".java": "java", ".cpp": "cpp", ".c": "c",
            ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".rb": "ruby",
            ".php": "php", ".swift": "swift", ".kt": "kotlin",
            ".scala": "scala", ".clj": "clojure", ".hs": "haskell",
            ".ml": "ocaml", ".fs": "fsharp", ".vue": "vue",
            ".svelte": "svelte", ".html": "html", ".css": "css",
            ".scss": "scss", ".json": "json", ".yaml": "yaml",
            ".yml": "yaml", ".toml": "toml", ".md": "markdown",
            ".sql": "sql", ".sh": "bash", ".bash": "bash",
            ".zsh": "bash", ".fish": "fish", ".dockerfile": "dockerfile",
        }
        return ext_map.get(file_path.suffix.lower(), "text")

    def _embed_text(self, text: str) -> Optional[list[float]]:
        """Generate embedding for text."""
        embedder = self._get_embedder()
        if embedder is False:
            return None
        if embedder:
            try:
                emb = embedder.encode(text, normalize_embeddings=True)
                return emb.tolist()
            except Exception:
                return None
        return None

    def index_project(self, force: bool = False) -> dict:
        """Index all code files in the project."""
        import fnmatch

        # File patterns to index
        patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.go", "**/*.rs",
                    "**/*.java", "**/*.cpp", "**/*.c", "**/*.h", "**/*.hpp",
                    "**/*.cs", "**/*.rb", "**/*.php", "**/*.swift", "**/*.kt",
                    "**/*.scala", "**/*.clj", "**/*.hs", "**/*.ml", "**/*.fs",
                    "**/*.vue", "**/*.svelte", "**/*.json", "**/*.yaml", "**/*.yml",
                    "**/*.toml", "**/*.md", "**/*.sql", "**/*.sh", "**/Dockerfile"]

        files = []
        for pattern in patterns:
            files.extend(self.working_dir.glob(pattern))

        # Filter out common ignore patterns
        ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".next", "target"}
        files = [f for f in files if not any(part in ignore_dirs for part in f.parts)]

        stats = {"indexed": 0, "skipped": 0, "chunks": 0, "errors": 0}

        conn = sqlite3.connect(self.db_path)
        for file_path in files:
            try:
                rel_path = file_path.relative_to(self.working_dir)
                file_hash = self._compute_file_hash(file_path)

                # Check if already indexed with same hash
                if not force:
                    cursor = conn.execute("SELECT file_hash FROM chunks WHERE file_path = ? LIMIT 1", (str(rel_path),))
                    row = cursor.fetchone()
                    if row and row[0] == file_hash:
                        stats["skipped"] += 1
                        continue

                # Delete old chunks for this file
                conn.execute("DELETE FROM chunks WHERE file_path = ?", (str(rel_path),))

                # Chunk and index
                chunks = self._chunk_file(file_path)
                for chunk in chunks:
                    embedding = self._embed_text(chunk.content)
                    emb_blob = json.dumps(embedding).encode() if embedding else None

                    conn.execute("""
                        INSERT INTO chunks (id, file_path, content, start_line, end_line, language, embedding, file_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (chunk.id, chunk.file_path, chunk.content, chunk.start_line, chunk.end_line, chunk.language, emb_blob, file_hash))
                    stats["chunks"] += 1

                stats["indexed"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"Error indexing {file_path}: {e}")

        conn.commit()
        conn.close()
        return stats

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search indexed code using semantic similarity or text matching."""
        query_embedding = self._embed_text(query)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        if query_embedding and NUMPY_AVAILABLE:
            # Semantic search
            cursor = conn.execute("SELECT * FROM chunks WHERE embedding IS NOT NULL")
            results = []
            query_vec = np.array(query_embedding)

            for row in cursor:
                try:
                    emb = json.loads(row["embedding"].decode())
                    chunk_vec = np.array(emb)
                    # Cosine similarity
                    sim = np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec))
                    if sim > 0.3:  # Threshold
                        results.append((sim, dict(row)))
                except Exception:
                    continue

            results.sort(key=lambda x: x[0], reverse=True)
            conn.close()
            return [r[1] for r in results[:limit]]
        else:
            # Fallback: text search
            cursor = conn.execute("""
                SELECT * FROM chunks
                WHERE content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f"%{query}%", limit))
            results = [dict(row) for row in cursor]
            conn.close()
            return results

    def get_file_context(self, file_path: str, max_chunks: int = 5) -> list[dict]:
        """Get indexed chunks for a specific file."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT * FROM chunks WHERE file_path = ?
            ORDER BY start_line
            LIMIT ?
        """, (file_path, max_chunks))
        results = [dict(row) for row in cursor]
        conn.close()
        return results

    def clear(self):
        """Clear the index."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM chunks")
        conn.commit()
        conn.close()