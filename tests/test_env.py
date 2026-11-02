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
    assert env["MIH_BIND_PORT"] == "8765"
    assert "MIH_HA_URL" not in env
    assert "MIH_HOME_COUNTRY" not in env


def test_options_are_mapped(tmp_path):
    options = {"language": "en", "profile": "M", "home_country": "DE",
               "timezone": "Europe/Berlin", "github_token": "ghp_x"}
    env = mirtv_env.build_env(options, {"SUPERVISOR_TOKEN": "sup"}, tmp_path)
    assert env["MIH_LANG"] == "en"
    assert env["MIRTV_PROFILE"] == "M"
    assert env["MIH_DISCOVERY_MAX_STREAMS"] == "15000"
    assert env["MIH_HOME_COUNTRY"] == "de"
    assert env["MIH_TIMEZONE"] == "Europe/Berlin"
    assert env["MIH_GITHUB_TOKEN"] == "ghp_x"
    assert env["MIH_HA_URL"] == "http://supervisor/core"
    assert env["MIH_HA_TOKEN"] == "sup"


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
