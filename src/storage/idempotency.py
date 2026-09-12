"""
Persistent, Distributed-Safe Idempotency Store.

Responsibilities:
- Provide atomic "claim if unseen" deduplication across concurrent crawler workers.
- Ensure the same article or job URL is never processed multiple times across
  distributed nodes or parallel worker processes.
- Keyed on stable identity: source + normalized item URL.
- Backed by SQLite with atomic UNIQUE constraints and WAL (Write-Ahead Logging) mode.

Enterprise / Scale Extrapolation:
- In local development and single-node pipelines, SQLite provides full ACID transactions,
  zero external dependencies, and atomic multi-process safety.
- In distributed enterprise architectures, this interface maps directly to:
    * Redis: SET claim:{source}:{normalized_url} {worker_id} NX EX 86400
    * PostgreSQL: INSERT INTO idempotency_claims (source, normalized_url, worker_id)
                  VALUES ($1, $2, $3) ON CONFLICT (source, normalized_url) DO NOTHING RETURNING id;
"""

import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


def _utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def normalize_storage_url(url: str, base_url: str = "") -> str:
    """
    Deterministically normalize an item URL for storage deduplication.
    - Resolves relative paths against base_url.
    - Lowercases scheme and netloc.
    - Strips URL fragments (#...).
    - Removes common marketing / tracking query parameters (utm_*, ref, promo, fbclid).
    - Strips trailing slashes from path for consistency.
    """
    if not url:
        return ""

    full = urljoin(base_url, url.strip()) if base_url else url.strip()
    parsed = urlparse(full)
    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    # Filter tracking query parameters
    tracking_keys = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term",
        "utm_content", "ref", "promo", "fbclid", "gclid",
    }
    q_params = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        if k.lower() not in tracking_keys:
            q_params.append((k, v))
    clean_query = urlencode(q_params)

    # Normalize trailing slash
    norm_path = parsed.path.rstrip("/")
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        norm_path,
        parsed.params,
        clean_query,
        "",
    ))


class PersistentIdempotencyStore:
    """
    SQLite-backed persistent idempotency and claim store.
    Guarantees atomic, race-free claim-if-unseen semantics using database-level
    UNIQUE constraints and transactions.
    """

    def __init__(self, db_path: str = "data/idempotency.db"):
        self.db_path = db_path
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Obtain a thread-local SQLite connection configured for concurrent safety."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.db_path,
                timeout=20.0,
                check_same_thread=False,
                isolation_level=None,  # autocommit mode; we manage transactions explicitly
            )
            # Enable WAL mode for high concurrency across threads and processes
            if self.db_path != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        """Create claims table and unique index if not already present."""
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    normalized_url TEXT NOT NULL,
                    worker_id TEXT NOT NULL DEFAULT 'default',
                    status TEXT NOT NULL DEFAULT 'CLAIMED',
                    claimed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source, normalized_url)
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_key
                ON idempotency_claims(source, normalized_url);
            """)

    def claim_if_unseen(
        self,
        source: str,
        url: str,
        worker_id: str = "default",
    ) -> bool:
        """
        Atomically attempt to claim a URL for processing.

        Returns:
            True  - If this worker successfully claimed the URL (first time seen).
            False - If the URL was already claimed by this or another worker/node.

        Concurrency Safety:
            Enforced by the SQLite UNIQUE(source, normalized_url) constraint.
            If two concurrent workers execute this simultaneously, the database
            engine permits exactly ONE insert and raises an IntegrityError on the other.
        """
        if not url:
            return False

        norm_url = normalize_storage_url(url)
        norm_source = source.strip()
        now = _utc_now_iso()
        conn = self._get_connection()

        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT INTO idempotency_claims (
                    source, normalized_url, worker_id, status, claimed_at, updated_at
                ) VALUES (?, ?, ?, 'CLAIMED', ?, ?);
                """,
                (norm_source, norm_url, worker_id, now, now),
            )
            conn.execute("COMMIT;")
            return True
        except sqlite3.IntegrityError:
            # UNIQUE constraint violation: already claimed!
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            return False
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise

    def is_claimed(self, source: str, url: str) -> bool:
        """Check if a URL has already been claimed or processed."""
        if not url:
            return False
        norm_url = normalize_storage_url(url)
        norm_source = source.strip()
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT 1 FROM idempotency_claims
            WHERE source = ? AND normalized_url = ?
            LIMIT 1;
            """,
            (norm_source, norm_url),
        )
        return cursor.fetchone() is not None

    def mark_completed(
        self,
        source: str,
        url: str,
        worker_id: Optional[str] = None,
    ) -> bool:
        """Mark a claimed item as successfully completed."""
        if not url:
            return False
        norm_url = normalize_storage_url(url)
        norm_source = source.strip()
        now = _utc_now_iso()
        conn = self._get_connection()

        cursor = conn.execute(
            """
            UPDATE idempotency_claims
            SET status = 'COMPLETED', updated_at = ?
            WHERE source = ? AND normalized_url = ?;
            """,
            (now, norm_source, norm_url),
        )
        return cursor.rowcount > 0

    def mark_failed(
        self,
        source: str,
        url: str,
        allow_retry: bool = False,
    ) -> bool:
        """
        Record that processing failed.
        If allow_retry is True, deletes the claim so another worker can retry it.
        """
        if not url:
            return False
        norm_url = normalize_storage_url(url)
        norm_source = source.strip()
        conn = self._get_connection()

        if allow_retry:
            cursor = conn.execute(
                """
                DELETE FROM idempotency_claims
                WHERE source = ? AND normalized_url = ?;
                """,
                (norm_source, norm_url),
            )
            return cursor.rowcount > 0
        else:
            now = _utc_now_iso()
            cursor = conn.execute(
                """
                UPDATE idempotency_claims
                SET status = 'FAILED', updated_at = ?
                WHERE source = ? AND normalized_url = ?;
                """,
                (now, norm_source, norm_url),
            )
            return cursor.rowcount > 0

    def count_claims(self, source: Optional[str] = None) -> int:
        """Return total number of recorded claims."""
        conn = self._get_connection()
        if source:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM idempotency_claims WHERE source = ?;",
                (source.strip(),),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM idempotency_claims;")
        row = cursor.fetchone()
        return row[0] if row else 0

    def clear(self, source: Optional[str] = None) -> int:
        """Clear claims (useful for resetting tests or fresh benchmarks)."""
        conn = self._get_connection()
        if source:
            cursor = conn.execute(
                "DELETE FROM idempotency_claims WHERE source = ?;",
                (source.strip(),),
            )
        else:
            cursor = conn.execute("DELETE FROM idempotency_claims;")
        return cursor.rowcount
