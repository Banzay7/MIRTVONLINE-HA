"""The add-on's scripts in Home Assistant (mih.ha_setup) and a channel started by name."""

import json

import httpx

from mih import ha_setup
from mih.config import Settings
from tests.test_tv import ROWS, FakeHa, _client


class FakeConfig(FakeHa):
    """FakeHa plus HA's config API for scripts and automations."""

    def __init__(self, existing=(), **kw):
        super().__init__(**kw)
        self.existing = set(existing)
        self.written: dict[str, dict] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/core")
        if path.startswith("/api/config/"):
            kind, _, key = path.removeprefix("/api/config/").split("/")
            name = f"{kind}.{key}"
            if request.method == "GET":
                return httpx.Response(200 if name in self.existing else 404, json={})
            self.written[name] = json.loads(request.content)
            self.existing.add(name)
            return httpx.Response(200, json={"result": "ok"})
        return super().__call__(request)


def test_setup_creates_only_what_is_missing(tmp_path):
    fake = FakeConfig(existing={"script.mih_play"})
    c = _client(tmp_path, fake, ha_addon="abc123_mirtvonline", lang="ru")
    assert c.get("/api/v1/playback/adapters").json()["ha_setup"] is True
    status = c.get("/api/v1/ha/setup").json()
    assert status["ok"] and [i["exists"] for i in status["items"]] == [False, False, True]

    out = c.post("/api/v1/ha/setup").json()
    assert out == {"created": ["script.mirtv_channel", "automation.mirtvonline_voice"],
                   "kept": ["script.mih_play"]}  # fmt: skip
    script = fake.written["script.mirtv_channel"]
    step = script["sequence"][0]
    assert step["action"] == "hassio.addon_stdin"
    assert step["data"]["addon"] == "abc123_mirtvonline"
    assert step["data"]["input"]["play"] == "{{ channel }}"
    voice = fake.written["automation.mirtvonline_voice"]
    assert voice["id"] == "mirtvonline_voice"
    assert "включи канал {channel}" in voice["triggers"][0]["command"]
    # Nothing is written twice.
    assert c.post("/api/v1/ha/setup").json()["created"] == []
    c.__exit__(None, None, None)


def test_setup_needs_the_add_on(tmp_path):
    c = _client(tmp_path, FakeConfig())
    assert c.get("/api/v1/ha/setup").json()["error"] == "ha_not_addon"
    resp = c.post("/api/v1/ha/setup")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "ha_not_addon"
    c.__exit__(None, None, None)


def test_play_script_template_plays_on_the_tv(tmp_path):
    s = Settings(data_dir=tmp_path, ha_addon="x", lang="en")
    step = ha_setup.play_script(s)["sequence"][0]
    assert step["action"] == "media_player.play_media"
    assert step["target"] == {"entity_id": "{{ tv }}"}


def test_play_by_name_starts_the_best_match_on_the_tv(tmp_path):
    fake = FakeHa(rows=[ROWS[3]])
    c = _client(tmp_path, fake)
    resp = c.post("/api/v1/playback/by-name", json={"channel": "Первый"})
    cmd = resp.json()
    assert resp.status_code == 202, cmd
    assert (cmd["state"], cmd["detail"]) == ("started", "airplay")
    assert cmd["channel"]["name"].lower().startswith("первый")
    miss = c.post("/api/v1/playback/by-name", json={"channel": "нет такого канала xyz"})
    assert miss.status_code == 404
    c.__exit__(None, None, None)
