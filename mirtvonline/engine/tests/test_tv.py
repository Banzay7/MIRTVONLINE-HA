"""Launch on a TV through Home Assistant's media players (mih.tv), without a script."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from mih import db, tv
from mih.api.app import create_app
from mih.config import Settings
from tests.conftest import fixture_bytes

TOKEN = "t" * 32

# One Android TV seen by ADB and by Cast (two devices of the same name), a Cast speaker,
# a TV with AirPlay only, and a player that cannot start a URL.
ROWS = [
    {"entity_id": "media_player.living_room_cast", "name": "Living Room TV", "state": "off",
     "features": 152463, "device_class": "tv", "device": "d2", "device_name": "Living Room TV",
     "integration": "cast"},
    {"entity_id": "media_player.living_room_adb", "name": "Living Room TV", "state": "off",
     "features": 0, "device_class": None, "device": "d1", "device_name": "Living room TV",
     "integration": "androidtv"},
    {"entity_id": "media_player.kitchen_speaker", "name": "Kitchen", "state": "idle",
     "features": 152463, "device_class": "speaker", "device": "d3", "device_name": "Kitchen",
     "integration": "cast"},
    {"entity_id": "media_player.bedroom", "name": "Bedroom", "state": "idle",
     "features": 512, "device_class": None, "device": "d4", "device_name": "Bedroom Apple TV",
     "integration": "apple_tv"},
    {"entity_id": "media_player.radio", "name": "Radio", "state": "idle", "features": 4,
     "device_class": None, "device": None, "device_name": None, "integration": None},
]  # fmt: skip


def test_media_players_are_grouped_into_tvs_adb_first():
    tvs = [t.as_dict() for t in tv.group(ROWS)]
    assert [t["name"] for t in tvs] == ["Bedroom Apple TV", "Living Room TV"]
    living = tvs[1]
    assert living["id"] == "media_player.living_room_adb"
    assert living["methods"] == ["adb", "cast"] and living["state"] == "off"
    assert tvs[0]["methods"] == ["airplay"]


def test_intent_quotes_the_url_for_the_shell():
    cmd = tv.intent("http://a.example/x.m3u8?a=1&b='2'", "org.videolan.vlc")
    assert cmd.startswith("am start -a android.intent.action.VIEW -d '")
    assert "-t video/* -p org.videolan.vlc" in cmd
    assert "&b=" in cmd and "'\"'\"'" in cmd  # the quote cannot end the argument
    assert tv.mime("http://a/x.m3u8?t=1") == "application/x-mpegURL"
    assert tv.mime("http://a/x.ts") == "video/mp2t"


class FakeHa:
    """Home Assistant's REST API: the template, services and states."""

    def __init__(self, rows=ROWS, adb_answers=("Starting: Intent",), fail=()):
        self.rows, self.adb_answers, self.fail = rows, list(adb_answers), set(fail)
        self.calls: list[tuple[str, dict]] = []
        self.adb_response = ""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/core")
        if path == "/api/template":
            return httpx.Response(200, text=json.dumps(self.rows))
        if path.startswith("/api/services/"):
            service = path.removeprefix("/api/services/").replace("/", ".")
            body = json.loads(request.content)
            self.calls.append((service, body))
            if service in self.fail:
                return httpx.Response(500, json={"message": "Failed to cast http://x.example"})
            if service == "androidtv.adb_command":
                self.adb_response = self.adb_answers.pop(0) if self.adb_answers else ""
            return httpx.Response(200, json=[])
        if path.startswith("/api/states/"):
            return httpx.Response(200, json={"attributes": {"adb_response": self.adb_response}})
        return httpx.Response(404)


def _client(tmp_path, fake, **kw):
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, playback="tv",
                        ha_url="http://supervisor/core", ha_token="s" * 40, **kw)  # fmt: skip
    app = create_app(settings)
    app.state.ha_transport = httpx.MockTransport(fake)
    c = TestClient(app)
    c.__enter__()
    c.headers["Authorization"] = f"Bearer {TOKEN}"
    src = c.post("/api/v1/sources", json={"name": "a"}).json()
    files = {"file": ("a.m3u", fixture_bytes("provider_a.m3u"), "audio/x-mpegurl")}
    c.post(f"/api/v1/sources/{src['id']}/upload", files=files)
    return c


def _play(c, **body):
    perviy = c.get("/api/v1/channels", params={"q": "первый"}).json()["items"][0]["id"]
    return c.post("/api/v1/playback/commands", json={"target": {"channel_id": perviy}, **body})


def test_tv_list_and_default_tv(tmp_path):
    c = _client(tmp_path, FakeHa())
    out = c.get("/api/v1/tv").json()
    assert out["error"] is None and out["default"] is None
    assert [t["id"] for t in out["items"]] == [
        "media_player.bedroom",
        "media_player.living_room_adb",
    ]
    assert c.get("/api/v1/playback/adapters").json()["available"] == ["agent", "ha", "tv"]
    put = c.put("/api/v1/settings/tv", json={"tv": "media_player.living_room_cast"})
    assert put.json() == {"default": "media_player.living_room_cast"}
    assert c.put("/api/v1/settings/tv", json={"tv": "light.x"}).status_code == 422
    assert c.put("/api/v1/settings/tv", json={"tv": None}).json() == {"default": None}
    c.__exit__(None, None, None)


def test_adb_wakes_the_tv_and_opens_vlc(tmp_path):
    fake = FakeHa()
    c = _client(tmp_path, fake)
    c.put("/api/v1/settings/tv", json={"tv": "media_player.living_room_cast"})
    resp = _play(c)
    cmd = resp.json()
    assert (cmd["state"], cmd["adapter"], cmd["detail"]) == ("started", "tv", "adb:vlc")
    assert cmd["device_id"] == "media_player.living_room_cast"
    assert "a.example" not in resp.text  # the stream URL stays on the server
    assert [s for s, _ in fake.calls] == ["media_player.turn_on", "androidtv.adb_command"]
    body = fake.calls[1][1]
    assert body["entity_id"] == "media_player.living_room_adb"
    assert "-p org.videolan.vlc" in body["command"]
    # The agent never sees it.
    from mih import playback

    conn = db.connect(c.app.state.settings.db_path)
    assert playback.take_commands(conn) == []
    conn.close()
    c.__exit__(None, None, None)


def test_no_vlc_tries_just_player_then_cast(tmp_path):
    fake = FakeHa(adb_answers=["Error: Activity not started, unable to resolve Intent",
                               "Starting: Intent"])  # fmt: skip
    c = _client(tmp_path, fake)
    cmd = _play(c, tv="media_player.living_room_adb").json()
    assert cmd["detail"] == "adb:just"

    fake = FakeHa(adb_answers=["Error: unable to resolve Intent"] * 2)
    c = _client(tmp_path / "2", fake)
    cmd = _play(c, tv="media_player.living_room_adb").json()
    assert (cmd["state"], cmd["detail"]) == ("started", "cast")
    service, body = fake.calls[-1]
    assert service == "media_player.play_media"
    assert body["entity_id"] == "media_player.living_room_cast"
    assert body["media_content_id"].startswith("http")
    c.__exit__(None, None, None)


def test_every_way_failing_fails_with_a_clean_reason(tmp_path):
    fake = FakeHa(fail={"media_player.play_media"})
    c = _client(tmp_path, fake)
    cmd = _play(c, tv="media_player.bedroom").json()
    assert (cmd["state"], cmd["error"]) == ("failed", "tv_failed")
    assert "http" not in cmd["detail"] and "<url>" in cmd["detail"]
    c.__exit__(None, None, None)


@pytest.mark.parametrize(("rows", "tv_id", "error"), [
    (ROWS, None, "tv_not_chosen"),
    ([], None, "tv_none"),
    (ROWS, "media_player.gone", "tv_not_found"),
])  # fmt: skip
def test_which_tv_when_none_or_a_missing_one_is_named(tmp_path, rows, tv_id, error):
    c = _client(tmp_path, FakeHa(rows=rows))
    cmd = _play(c, **({"tv": tv_id} if tv_id else {})).json()
    assert (cmd["state"], cmd["error"]) == ("failed", error)
    c.__exit__(None, None, None)


def test_the_only_tv_needs_no_choice(tmp_path):
    fake = FakeHa(rows=[ROWS[3]])
    c = _client(tmp_path, fake)
    cmd = _play(c).json()
    assert (cmd["state"], cmd["detail"]) == ("started", "airplay")
    assert fake.calls[0][1]["media_content_type"] == "video"
    c.__exit__(None, None, None)


def test_tv_list_falls_back_to_states_and_reports_ha_errors(tmp_path):
    def states(request):
        if request.url.path.endswith("/api/template"):
            return httpx.Response(404)
        return httpx.Response(200, json=[
            {"entity_id": "media_player.box", "state": "on",
             "attributes": {"friendly_name": "Box", "adb_response": None}},
            {"entity_id": "light.x", "state": "on", "attributes": {}},
        ])  # fmt: skip

    c = _client(tmp_path, states)
    items = c.get("/api/v1/tv").json()["items"]
    assert [(t["id"], t["methods"]) for t in items] == [("media_player.box", ["adb"])]
    c.__exit__(None, None, None)

    c = _client(tmp_path / "2", lambda r: httpx.Response(401))
    assert c.get("/api/v1/tv").json() == {"items": [], "default": None,
                                          "error": "ha_unauthorized"}  # fmt: skip
    c.__exit__(None, None, None)
