"""Add-on options (/data/options.json) -> MIH_* environment, printed as shell exports.

run.sh evaluates the output and starts ``mih serve``. Kept in Python so the mapping is
tested without Home Assistant (tests/test_env.py).
"""

from __future__ import annotations

import json
import os
import secrets
import shlex
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get("MIRTV_DATA_DIR", "/data"))
# Inside the add-on Home Assistant Core is reached through the Supervisor proxy,
# with the token the Supervisor gives every add-on that sets homeassistant_api.
HA_URL = "http://supervisor/core"
# The Supervisor's Ingress proxy: the only address the sidebar panel's requests come from.
# Home Assistant has already checked the user, so MIH asks it for no token.
INGRESS_PROXY = "172.30.32.2"

# Light mode (load estimate §7): one job at a time in the server's own process, at a
# lower priority than the web UI; the catalog rebuilt only when its data changed and at
# most hourly; rare updates; few parallel stream checks.
COMMON = {
    "MIH_SCHEDULER_MODE": "thread",
    "MIH_JOB_NICE": "10",
    "MIH_CATALOG_EVERY": "1h",
    "MIH_EPG_SCOPE": "tracked",
    "MIH_EPG_RETENTION_DAYS": "3",
    "MIH_HISTORY_DAYS": "90",
    # Playlists you added: daily. The guide: daily at night.
    "MIH_EVERY_SOURCES": "24h",
    "MIH_EVERY_EPG": "24h",
    "MIH_EPG_AT": "03:30",
    # Re-check of working streams: weekly.
    "MIH_EVERY_HEALTH": "7d",
    # The playlist search starts over daily for the first 3 days, then monthly; the
    # scout and packer keep working through what it found.
    "MIH_DISCOVERY_FRESH_DAYS": "3",
    "MIH_HEALTH_PER_SOURCE": "1",
    "MIH_WORKERS": "1",
    # Without Home Assistant (a test run) "На ТВ" only picks the stream.
    "MIH_PLAYBACK": "off",
}
PROFILES = {
    "S": {"MIH_HEALTH_CONCURRENCY": "4", "MIH_DISCOVERY_MAX_STREAMS": "6000"},
    "M": {"MIH_HEALTH_CONCURRENCY": "4", "MIH_DISCOVERY_MAX_STREAMS": "15000"},
    "L": {"MIH_HEALTH_CONCURRENCY": "8", "MIH_DISCOVERY_MAX_STREAMS": "30000"},
}
LANGUAGES = ("ru", "en", "vi")


def load_options(data_dir: Path) -> dict:
    path = data_dir / "options.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def api_token(data_dir: Path) -> str:
    """A random token kept in /data, so MIH may listen on the add-on network.

    The sidebar panel (Ingress) needs no token; it keeps every other container on the
    same network out.
    """
    path = data_dir / ".api_token"
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= 24:
            return token
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="utf-8")
    path.chmod(0o600)
    return token


def build_env(options: dict, environ: dict[str, str], data_dir: Path) -> dict[str, str]:
    profile = str(options.get("profile") or "S").upper()
    if profile not in PROFILES:
        profile = "S"
    language = str(options.get("language") or "ru").lower()
    if language not in LANGUAGES:
        language = "ru"

    env = dict(COMMON)
    env.update(PROFILES[profile])
    env["MIRTV_PROFILE"] = profile
    env["MIH_LANG"] = language
    env["MIH_DATA_DIR"] = str(data_dir)
    env["MIH_BIND_HOST"] = "0.0.0.0"
    env["MIH_BIND_PORT"] = "8765"
    env["MIH_API_TOKEN"] = api_token(data_dir)
    env["MIH_INGRESS_PROXY"] = INGRESS_PROXY
    # Time zone: the option, else the one the Supervisor passes to every add-on.
    env["MIH_TIMEZONE"] = (options.get("timezone") or environ.get("TZ") or "UTC").strip()

    country = str(options.get("home_country") or "").strip().lower()
    if country:
        env["MIH_HOME_COUNTRY"] = country[:2]
    if options.get("github_token"):
        env["MIH_GITHUB_TOKEN"] = str(options["github_token"])

    supervisor_token = environ.get("SUPERVISOR_TOKEN")
    if supervisor_token:
        env["MIH_HA_URL"] = HA_URL
        env["MIH_HA_TOKEN"] = supervisor_token
        # "На ТВ" starts the channel on a TV of Home Assistant itself (ADB, Cast, AirPlay).
        env["MIH_PLAYBACK"] = "tv"
    return env


def render(env: dict[str, str]) -> str:
    return "".join(f"export {k}={shlex.quote(v)}\n" for k, v in sorted(env.items()))


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = build_env(load_options(DATA_DIR), dict(os.environ), DATA_DIR)
    sys.stdout.write(render(env))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
