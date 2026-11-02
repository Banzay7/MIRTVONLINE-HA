"""Home Assistant Ingress: the sidebar panel reaches MIH through the Supervisor proxy."""

import pytest
from fastapi.testclient import TestClient

from mih.api.app import create_app
from mih.config import ConfigError, Settings

TOKEN = "t" * 32
PROXY = "172.30.32.2"


def _client(tmp_path, peer, ingress=PROXY):
    app = create_app(Settings(data_dir=tmp_path, api_token=TOKEN, ingress_proxy=ingress))
    return TestClient(app, client=(peer, 50000))


def test_the_ingress_proxy_needs_no_token(tmp_path):
    with _client(tmp_path, PROXY) as c:
        assert c.get("/api/v1/channels").status_code == 200
        assert c.get("/api/v1/channels").headers["x-frame-options"] == "SAMEORIGIN"


def test_other_addresses_still_need_the_token(tmp_path):
    with _client(tmp_path, "172.30.32.5") as c:
        # A forwarded header cannot pretend to be the proxy.
        spoof = c.get("/api/v1/channels", headers={"X-Forwarded-For": PROXY})
        assert spoof.status_code == 401
        ok = c.get("/api/v1/channels", headers={"Authorization": f"Bearer {TOKEN}"})
        assert ok.status_code == 200


def test_without_ingress_nothing_changes(tmp_path):
    with _client(tmp_path, PROXY, ingress="") as c:
        assert c.get("/api/v1/channels").status_code == 401
        assert c.get("/api/v1/health/live").headers["x-frame-options"] == "DENY"


def test_docs_load_the_schema_by_a_relative_address(tmp_path):
    with _client(tmp_path, PROXY) as c:
        page = c.get("/api/docs")
        assert page.status_code == 200
        assert "'v1/openapi.json'" in page.text or '"v1/openapi.json"' in page.text
        assert c.get("/api/v1/openapi.json").status_code == 200


def test_ui_uses_relative_paths():
    from importlib import resources

    static = resources.files("mih.ui") / "static"
    app_js = (static / "app.js").read_text(encoding="utf-8")
    assert 'const API = "api/v1";' in app_js
    assert 'href="/' not in app_js and 'fetch("/' not in app_js


def test_settings_read_and_check_the_variable():
    s = Settings.from_env({"MIH_API_TOKEN": TOKEN, "MIH_INGRESS_PROXY": PROXY})
    assert s.ingress_proxy == PROXY
    s.validate_for_serving()
    for bad in ("nope", "172.30.32.0/23"):
        with pytest.raises(ConfigError):
            Settings.from_env(
                {"MIH_API_TOKEN": TOKEN, "MIH_INGRESS_PROXY": bad}
            ).validate_for_serving()
