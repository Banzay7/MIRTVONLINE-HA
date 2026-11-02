"""Light mode for small boxes (MIH_CATALOG_EVERY, MIH_JOB_NICE): when the catalog is
rebuilt, how long that took, how much memory the process peaked at and how much disk
the data directory holds.

Building the catalog is the slowest regular step (the genres of every programme). On
a server it runs after every job; on a small home box it runs only when what the
catalog shows has changed, and at most once per ``catalog_every``. A change that comes
sooner waits, and the scheduler builds it once the time is up.

What the catalog shows is guessed from a fingerprint of the tables it reads: rows
added or removed, a stream changing status, a guide mapped or dropped, a playlist or
guide import. A stream check that only moves ``last_checked_at`` leaves it as it is.
"""

from __future__ import annotations

import hashlib
import logging
import os
import resource
import sqlite3
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mih import __version__

log = logging.getLogger(__name__)

_KEY_FINGERPRINT = "catalog:fingerprint"
_KEY_BUILT_AT = "catalog:built_at"
_KEY_SECONDS = "catalog:seconds"
_KEY_PEAK = "catalog:peak_mb"
_KEY_PENDING = "catalog:pending"

# A stream's status enters the fingerprint as length × first letter: distinct for
# every status the engine uses (new, active, unverified, suspect, quarantine, archived).
_FINGERPRINT_SQL = (
    "SELECT (SELECT max(rowid) FROM source_snapshots), (SELECT max(rowid) FROM epg_snapshots),"
    " (SELECT count(*) || '/' || COALESCE(max(rowid), 0) FROM channels),"
    " (SELECT count(*) || '/' || COALESCE(max(rowid), 0) || '/'"
    "   || total(rowid * length(status) * unicode(status)) || '/' || count(availability_reason)"
    "   FROM streams),"
    " (SELECT count(*) || '/' || COALESCE(max(rowid), 0) FROM feeds),"
    " (SELECT count(*) || '/' || COALESCE(max(rowid), 0) FROM channel_aliases),"
    " (SELECT count(*) || '/' || total(rowid * (decision IN ('auto', 'approved')))"
    "   FROM epg_mappings),"
    " (SELECT count(*) FROM directory_channels),"
    " (SELECT count(*) FROM channel_category_overrides)"
)


def fingerprint(conn: sqlite3.Connection) -> str:
    row = conn.execute(_FINGERPRINT_SQL).fetchone()
    key = repr((__version__, *tuple(row)))
    return hashlib.blake2b(key.encode(), digest_size=8).hexdigest()


def _get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _put(conn: sqlite3.Connection, key: str, value: str, now: datetime) -> None:
    conn.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, _fmt(now)),
    )


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------- When to build ----------


def catalog_decision(conn: sqlite3.Connection, every: timedelta | None, now: datetime,
                     *, guide: bool = False) -> tuple[str, datetime | None]:  # fmt: skip
    """``build``, ``unchanged`` or ``later`` (with the time it may run). ``guide``: the
    caller imported a guide, so the later build rewrites the lists' guide files too."""
    if every is None:
        return "build", None
    if _get(conn, _KEY_FINGERPRINT) == fingerprint(conn):
        return "unchanged", None
    built = _get(conn, _KEY_BUILT_AT)
    if built and now - _parse(built) < every:
        pending = _get(conn, _KEY_PENDING)
        _put(conn, _KEY_PENDING, "guide" if guide or pending == "guide" else "1", now)
        return "later", _parse(built) + every
    return "build", None


def pending_build(conn: sqlite3.Connection, every: timedelta | None,
                  now: datetime) -> str | None:  # fmt: skip
    """A build a job put off that may run now: ``guide`` or ``1``; else None."""
    if every is None:
        return None
    pending = _get(conn, _KEY_PENDING)
    if not pending:
        return None
    built = _get(conn, _KEY_BUILT_AT)
    if built and now - _parse(built) < every:
        return None
    return pending


def record_build(conn: sqlite3.Connection, seconds: float, now: datetime,
                 channels: int) -> dict:  # fmt: skip
    """Remember the build (its fingerprint clears the need for the next one) and print
    its time, the peak memory and the size of the data directory to the log."""
    peak = peak_memory_mb()
    _put(conn, _KEY_FINGERPRINT, fingerprint(conn), now)
    _put(conn, _KEY_BUILT_AT, _fmt(now), now)
    _put(conn, _KEY_SECONDS, f"{seconds:.1f}", now)
    _put(conn, _KEY_PEAK, str(peak), now)
    conn.execute("DELETE FROM app_settings WHERE key = ?", (_KEY_PENDING,))
    log.info("catalog built in %.1f s: %d channels, peak memory %d MB", seconds, channels, peak)
    return {"catalog_s": round(seconds, 1), "peak_mb": peak}


def catalog_state(conn: sqlite3.Connection) -> dict:
    built = _get(conn, _KEY_BUILT_AT)
    seconds = _get(conn, _KEY_SECONDS)
    peak = _get(conn, _KEY_PEAK)
    return {
        "built_at": built,
        "seconds": float(seconds) if seconds else None,
        "peak_mb": int(peak) if peak else None,
        "pending": bool(_get(conn, _KEY_PENDING)),
    }


# ---------- Memory and disk ----------


def peak_memory_mb() -> int:
    """The process's peak resident memory since it started (kB on Linux, bytes on macOS)."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024)


def _tree_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total


_DISK_EVERY = 300.0  # seconds; walking the data directory is cheap but not free
_disk_cache: dict[str, tuple[float, dict]] = {}
_disk_lock = threading.Lock()


def disk_usage(data_dir: Path, *, db_path: Path, snapshots: Path, export: Path,
               max_age: float = _DISK_EVERY) -> dict:  # fmt: skip
    """Bytes in the data directory: the database (with its journal), snapshots,
    exported lists and everything else (discovery copies, caches)."""
    key = str(data_dir)
    with _disk_lock:
        hit = _disk_cache.get(key)
        if hit and time.monotonic() - hit[0] < max_age:
            return hit[1]
    database = sum(
        p.stat().st_size for p in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm"))
        if p.exists()
    )  # fmt: skip
    snap = _tree_bytes(snapshots) if snapshots.exists() else 0
    exp = _tree_bytes(export) if export.exists() else 0
    total = _tree_bytes(data_dir) if data_dir.exists() else 0
    # snapshots/export may live outside data_dir; "other" never goes below zero.
    inside = sum(_inside(p, data_dir) * n for p, n in ((snapshots, snap), (export, exp)))
    out = {"total": total, "database": database, "snapshots": snap, "export": exp,
           "other": max(0, total - database - inside)}  # fmt: skip
    with _disk_lock:
        _disk_cache[key] = (time.monotonic(), out)
    return out


def log_disk(data_dir: Path, *, db_path: Path, snapshots: Path, export: Path) -> dict:
    """Print the data directory's size to the log (fresh, not cached)."""
    use = disk_usage(data_dir, db_path=db_path, snapshots=snapshots, export=export, max_age=0)
    mb = {k: round(v / 1_000_000) for k, v in use.items()}
    log.info("data on disk: %d MB (database %d, snapshots %d, export %d, other %d)",
             mb["total"], mb["database"], mb["snapshots"], mb["export"], mb["other"])  # fmt: skip
    return use


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


# ---------- Priority ----------


def lower_priority(nice: int) -> None:
    """Lower this thread's CPU priority (Linux sets nice per thread), so a job never
    makes the web UI wait. Threads it starts inherit it. No-op where unsupported."""
    if nice <= 0:
        return
    try:
        tid = threading.get_native_id()
        current = os.getpriority(os.PRIO_PROCESS, tid)
        os.setpriority(os.PRIO_PROCESS, tid, min(19, current + nice))
    except (AttributeError, OSError):
        pass
