import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mirtvonline" / "mirtv_env.py"

spec = importlib.util.spec_from_file_location("mirtv_env", SCRIPT)
mirtv_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirtv_env)


def test_defaults_are_profile_s_and_russian(tmp_path):
    env = mirtv_env.build_env({}, {}, tmp_path)
    assert env["MIRTV_PROFILE"] == "S"
    assert env["MIH_LANG"] == "ru"
    assert env["MIH_TIMEZONE"] == "UTC"
    assert env["MIH_HEALTH_CONCURRENCY"] == "4"
    assert env["MIH_SCHEDULER_MODE"] == "thread"
    assert env["MIH_EPG_SCOPE"] == "tracked"
    # Light mode (load estimate §7).
    assert env["MIH_CATALOG_EVERY"] == "1h"
    assert env["MIH_JOB_NICE"] == "10"
    assert env["MIH_EPG_AT"] == "03:30"
    assert env["MIH_EVERY_HEALTH"] == "7d"
    assert env["MIH_DISCOVERY_FRESH_DAYS"] == "3"
    assert env["MIH_BIND_PORT"] == "8765"
    assert env["MIH_INGRESS_PROXY"] == "172.30.32.2"
    assert "MIH_HA_URL" not in env
    assert env["MIH_PLAYBACK"] == "off"
    assert "MIH_HOME_COUNTRY" not in env
    # Your channels' language defaults to the add-on's language.
    assert env["MIH_CHANNEL_LANGUAGES"] == "ru"


def test_options_are_mapped(tmp_path):
    options = {"language": "ru", "profile": "M", "home_country": "DE", "channel_languages": " en ",
               "timezone": "Europe/Berlin", "github_token": "ghp_x"}
    env = mirtv_env.build_env(options, {"SUPERVISOR_TOKEN": "sup"}, tmp_path)
    assert env["MIH_LANG"] == "ru"
    assert env["MIRTV_PROFILE"] == "M"
    assert env["MIH_DISCOVERY_MAX_STREAMS"] == "15000"
    assert env["MIH_HOME_COUNTRY"] == "de"
    assert env["MIH_CHANNEL_LANGUAGES"] == "en"
    assert env["MIH_TIMEZONE"] == "Europe/Berlin"
    assert env["MIH_GITHUB_TOKEN"] == "ghp_x"
    assert env["MIH_HA_URL"] == "http://supervisor/core"
    assert env["MIH_HA_TOKEN"] == "sup"
    # With Home Assistant at hand "На ТВ" goes to its TVs, without a script.
    assert env["MIH_PLAYBACK"] == "tv"


def test_timezone_falls_back_to_supervisor_tz(tmp_path):
    env = mirtv_env.build_env({"timezone": ""}, {"TZ": "Europe/Berlin"}, tmp_path)
    assert env["MIH_TIMEZONE"] == "Europe/Berlin"


def test_unknown_values_fall_back(tmp_path):
    env = mirtv_env.build_env({"language": "xx", "profile": "Z"}, {}, tmp_path)
    assert env["MIH_LANG"] == "ru"
    assert env["MIRTV_PROFILE"] == "S"


def test_api_token_is_kept_between_starts(tmp_path):
    first = mirtv_env.api_token(tmp_path)
    assert len(first) >= 24
    assert mirtv_env.api_token(tmp_path) == first
    assert (tmp_path / ".api_token").stat().st_mode & 0o777 == 0o600


def test_script_prints_shell_exports(tmp_path):
    (tmp_path / "options.json").write_text(json.dumps({"timezone": "it's; rm -rf /"}))
    out = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={"MIRTV_DATA_DIR": str(tmp_path)},
        capture_output=True, text=True, check=True,
    ).stdout
    # The output is evaluated by sh: every value must come back exactly as given.
    shown = subprocess.run(
        ["sh", "-c", out + 'printf %s "$MIH_TIMEZONE"'],
        capture_output=True, text=True, check=True,
    ).stdout
    assert shown == "it's; rm -rf /"
    assert all(line.startswith("export ") for line in out.splitlines())
    assert shlex.split(out)  # parses as shell words


def test_addon_slug_comes_from_the_container_name(tmp_path):
    env = mirtv_env.build_env({}, {"SUPERVISOR_TOKEN": "s", "HOSTNAME": "abc123-mirtvonline"},
                              tmp_path)
    assert env["MIH_HA_ADDON"] == "abc123_mirtvonline"
    assert "MIH_HA_ADDON" not in mirtv_env.build_env({}, {}, tmp_path)
