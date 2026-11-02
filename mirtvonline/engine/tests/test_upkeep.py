"""Light mode: catalog only on change and at most every MIH_CATALOG_EVERY, the guide by
the clock, one job at a time, data size and build numbers on the status screen."""

import dataclasses
import threading
import time
from datetime import UTC, datetime, timedelta

from mih import scheduler, upkeep
from mih.config import Settings
from mih.ids import new_id
from tests.test_epg_auto import working  # noqa: F401  (fixture)

NOW = datetime(2026, 11, 2, 18, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _add_channel(conn, name: str) -> None:
    conn.execute("INSERT INTO channels (id, canonical_name, created_at) VALUES (?, ?, ?)",
                 (new_id(), name, "2026-11-02T00:00:00Z"))  # fmt: skip


def test_catalog_is_built_on_change_and_at_most_hourly(conn):
    assert upkeep.catalog_decision(conn, HOUR, NOW) == ("build", None)
    upkeep.record_build(conn, 1.5, NOW, 0)
    assert upkeep.catalog_decision(conn, HOUR, NOW + timedelta(minutes=5)) == ("unchanged", None)

    _add_channel(conn, "Новый")
    decision, at = upkeep.catalog_decision(conn, HOUR, NOW + timedelta(minutes=10), guide=True)
    assert (decision, at) == ("later", NOW + HOUR)
    # The scheduler builds the put-off catalog once the hour is up, guide files included.
    assert upkeep.pending_build(conn, HOUR, NOW + timedelta(minutes=30)) is None
    assert upkeep.pending_build(conn, HOUR, NOW + HOUR) == "guide"
    assert upkeep.catalog_decision(conn, HOUR, NOW + HOUR) == ("build", None)
    upkeep.record_build(conn, 1.0, NOW + HOUR, 1)
    assert upkeep.pending_build(conn, HOUR, NOW + 2 * HOUR) is None


def test_without_light_mode_every_job_builds(conn):
    upkeep.record_build(conn, 1.0, NOW, 0)
    assert upkeep.catalog_decision(conn, None, NOW) == ("build", None)
    assert upkeep.pending_build(conn, None, NOW + HOUR) is None


def test_a_stream_check_that_changes_nothing_keeps_the_fingerprint(conn, working):  # noqa: F811
    before = upkeep.fingerprint(conn)
    conn.execute("UPDATE streams SET last_checked_at = '2026-11-02T18:00:00Z'")
    assert upkeep.fingerprint(conn) == before
    conn.execute("UPDATE streams SET status = 'suspect' WHERE rowid ="
                 " (SELECT min(rowid) FROM streams)")  # fmt: skip
    assert upkeep.fingerprint(conn) != before


def test_jobs_skip_the_catalog_when_nothing_changed(conn, settings, working):  # noqa: F811
    light = dataclasses.replace(settings, catalog_every=HOUR)
    data: dict = {}
    scheduler._rebuild_lists(conn, light, data)
    assert data["catalog_s"] >= 0 and data["peak_mb"] > 0 and "lists" in data
    again: dict = {}
    line = scheduler._rebuild_lists(conn, light, again)
    assert "lists" not in again and line == "lists: the catalog has not changed"
    _add_channel(conn, "Новый")
    line = scheduler._rebuild_lists(conn, light, again)
    assert "lists" not in again and line.startswith("lists: will be rebuilt at ")
    state = upkeep.catalog_state(conn)
    assert state["pending"] and state["seconds"] is not None and state["peak_mb"] > 0
    # Time up: the scheduler's tick builds it.
    later = datetime.now(UTC) + 2 * HOUR
    assert scheduler.build_pending(conn, light, later)
    assert not upkeep.catalog_state(conn)["pending"]


def test_guide_runs_at_night_when_set(settings):
    night = dataclasses.replace(settings, timezone="Europe/Berlin",
                                epg_at=datetime(2000, 1, 1, 3, 30).time())  # fmt: skip
    # 03:30 in Berlin (CET, UTC+1) is 02:30 UTC; at 18:00 UTC it is tomorrow's.
    assert scheduler.next_run(night, "epg", NOW) == datetime(2026, 11, 3, 2, 30, tzinfo=UTC)
    assert scheduler.next_run(settings, "epg", NOW) == NOW + settings.every_epg


def test_guide_by_the_clock_is_planned_for_the_night(conn, settings):
    night = dataclasses.replace(settings, timezone="UTC", scheduler_enabled=True,
                                epg_at=datetime(2000, 1, 1, 3, 30).time())  # fmt: skip
    scheduler.sync_jobs(conn, night, NOW)
    row = conn.execute("SELECT next_run_at FROM jobs WHERE name = 'epg'").fetchone()
    assert row["next_run_at"] == "2026-11-03T03:30:00Z"
    plan = {p["job"]: p for p in scheduler.plan_by_job(conn, night, NOW)}
    assert plan["epg"]["every_minutes"] is None


def test_jobs_run_one_at_a_time(conn, settings, monkeypatch):
    seen, active = [], [0]

    def slow(conn, settings, policy, now, transport):
        active[0] += 1
        seen.append(active[0])
        time.sleep(0.2)
        active[0] -= 1
        return scheduler.Outcome("ok", "routine", "done")

    monkeypatch.setitem(scheduler._RUNNERS, "drive", slow)
    monkeypatch.setitem(scheduler._RUNNERS, "pack", slow)

    def run(name: str) -> None:
        from mih import db

        c = db.connect(settings.db_path)
        try:
            scheduler.run_job(c, settings, name, manual=True)
        finally:
            c.close()

    threads = [threading.Thread(target=run, args=(n,)) for n in ("drive", "pack")]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert seen == [1, 1]


def test_disk_usage_splits_the_data_directory(settings, conn):
    (settings.snapshots_dir).mkdir(parents=True, exist_ok=True)
    (settings.snapshots_dir / "a.m3u").write_bytes(b"x" * 1000)
    (settings.data_dir / "discovery").mkdir()
    (settings.data_dir / "discovery" / "p.m3u").write_bytes(b"y" * 500)
    use = upkeep.disk_usage(settings.data_dir, db_path=settings.db_path,
                            snapshots=settings.snapshots_dir, export=settings.export_dir,
                            max_age=0)  # fmt: skip
    assert use["snapshots"] == 1000 and use["database"] > 0
    assert use["total"] == use["database"] + use["snapshots"] + use["export"] + use["other"]
    assert use["other"] >= 500


def test_status_shows_data_size_and_last_build(conn, settings):
    upkeep.record_build(conn, 2.5, NOW, 0)
    snap = scheduler.status_snapshot(conn, settings)
    assert snap["disk"]["database"] > 0
    assert snap["catalog_build"]["seconds"] == 2.5


def test_light_mode_settings_from_env(tmp_path):
    s = Settings.from_env({"MIH_DATA_DIR": str(tmp_path), "MIH_CATALOG_EVERY": "1h",
                           "MIH_EPG_AT": "03:30", "MIH_JOB_NICE": "10",
                           "MIH_DISCOVERY_FRESH_DAYS": "3"})  # fmt: skip
    assert s.catalog_every == HOUR and s.epg_at.hour == 3 and s.job_nice == 10
    assert s.discovery_fresh_days == 3
    d = Settings.from_env({"MIH_DATA_DIR": str(tmp_path)})
    assert d.catalog_every is None and d.epg_at is None and d.job_nice == 0


def test_lower_priority_raises_nice_of_this_thread_only():
    import os

    out = {}

    def work():
        upkeep.lower_priority(5)
        out["nice"] = os.getpriority(os.PRIO_PROCESS, threading.get_native_id())

    base = os.getpriority(os.PRIO_PROCESS, threading.get_native_id())
    th = threading.Thread(target=work)
    th.start()
    th.join()
    assert out["nice"] == min(19, base + 5)
    assert os.getpriority(os.PRIO_PROCESS, threading.get_native_id()) == base
