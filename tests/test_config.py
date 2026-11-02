from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "mirtvonline"
CONFIG = yaml.safe_load((ADDON / "config.yaml").read_text(encoding="utf-8"))


def test_repository_file():
    repo = yaml.safe_load((ROOT / "repository.yaml").read_text(encoding="utf-8"))
    assert repo["name"] and repo["url"].startswith("https://github.com/")


def test_ingress_without_published_ports():
    assert CONFIG["ingress"] is True
    assert CONFIG["ingress_port"] == 8765
    assert "ports" not in CONFIG
    assert CONFIG["homeassistant_api"] is True
    assert set(CONFIG["arch"]) == {"aarch64", "amd64"}
    assert "image" not in CONFIG  # built locally from this repository


def test_every_option_has_a_schema_entry():
    assert set(CONFIG["options"]) <= set(CONFIG["schema"])


def test_translations_cover_the_schema():
    for lang in ("en", "ru"):
        tr = yaml.safe_load((ADDON / "translations" / f"{lang}.yaml").read_text("utf-8"))
        assert set(tr["configuration"]) == set(CONFIG["schema"]), lang
        for key, item in tr["configuration"].items():
            assert item["name"] and item["description"], (lang, key)


def test_changelog_has_the_current_version():
    changelog = (ADDON / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {CONFIG['version']}" in changelog


def test_engine_is_inside_the_addon():
    assert (ADDON / "engine" / "src" / "mih" / "cli.py").exists()
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    assert "github.com" not in dockerfile  # nothing fetched from GitHub at build time


def test_base_image_has_python_and_ignores_build_from():
    # Supervisor may pass BUILD_FROM=ghcr.io/home-assistant/base (no Python).
    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    froms = [line for line in dockerfile.splitlines() if line.startswith("FROM ")]
    assert froms == ["FROM docker.io/library/python:3.12-slim-bookworm"]
    assert not (ADDON / "build.yaml").exists()
