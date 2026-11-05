"""Launch on a TV through Home Assistant's media players (mih.tv), without a script."""

import json
import shlex

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
    """Home Assistant's REST API: the template, services and states. A stream sent to a
    TV plays at once unless its address has one of ``dead`` in it (it keeps buffering);
    ``silent`` TVs never report ``playing``."""

    def __init__(self, rows=ROWS, adb_answers=("Starting: Intent",), fail=(), dead=(),
                 silent=False, state="idle"):  # fmt: skip
        self.rows, self.adb_answers, self.fail = rows, list(adb_answers), set(fail)
        self.dead, self.silent = tuple(dead), silent
        self.calls: list[tuple[str, dict]] = []
        self.adb_response = ""
        self.state, self.content, self.app = state, None, None

    def _send(self, url, app=None):
        self.content, self.app = url, app
        if self.silent:
            self.state, self.content = "on", None
        else:
            self.state = "buffering" if any(d in url for d in self.dead) else "playing"

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
                if "error" not in self.adb_response.lower():
                    args = shlex.split(body["command"])
                    self._send(args[args.index("-d") + 1], args[-1])
            if service == "media_player.play_media":
                self._send(body["media_content_id"])
            return httpx.Response(200, json=[])
        if path.startswith("/api/states/"):
            return httpx.Response(200, json={"state": self.state, "attributes": {
                "adb_response": self.adb_response, "media_content_id": self.content,
                "app_id": self.app}})  # fmt: skip
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def no_real_wait(monkeypatch):
    """Waiting for the picture runs on a clock that sleeping moves forward."""
    clock = [0.0]
    monkeypatch.setattr(tv, "_clock", lambda: clock[0])
    monkeypatch.setattr(tv, "_sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    return clock


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


def test_addon_without_mcp_offers_no_agent(tmp_path):
    """In the add-on no agent can take a command unless its MCP port is on: the web UI
    does not offer the agent, and a browser that kept it gets the TV instead."""
    fake = FakeHa()
    c = _client(tmp_path, fake, ha_addon="abc123_mirtvonline")
    assert c.get("/api/v1/playback/adapters").json()["available"] == ["ha", "tv"]
    c.put("/api/v1/settings/tv", json={"tv": "media_player.living_room_cast"})
    cmd = _play(c, adapter="agent").json()
    assert (cmd["state"], cmd["adapter"]) == ("started", "tv")
    c.__exit__(None, None, None)

    c = _client(tmp_path / "mcp", FakeHa(), ha_addon="abc123_mirtvonline", mcp_port=8766)
    assert c.get("/api/v1/playback/adapters").json()["available"] == ["agent", "ha", "tv"]
    c.__exit__(None, None, None)


def _opens(c):
    conn = db.connect(c.app.state.settings.db_path)
    rows = conn.execute("SELECT stream_id, source, outcome, open_ms FROM open_times").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_open_time_runs_until_the_tv_plays(tmp_path):
    """The open time ends when HA says the stream plays, not when it accepted the call."""

    class Slow(FakeHa):
        polls = 0

        def __call__(self, request):
            resp = super().__call__(request)
            if request.url.path.endswith("/api/states/media_player.living_room_cast"):
                self.polls += 1
                if self.content and self.polls < 6:  # 2 s of buffering first
                    body = resp.json() | {"state": "buffering"}
                    return httpx.Response(200, json=body)
            return resp

    c = _client(tmp_path, Slow(rows=[ROWS[0]]))
    cmd = _play(c).json()
    assert (cmd["state"], cmd["detail"]) == ("started", "cast")
    assert "playing" in cmd["stages"]
    [row] = _opens(c)
    assert (row["source"], row["outcome"]) == ("tv", "opened")
    assert row["stream_id"] == cmd["stream_id"]
    c.__exit__(None, None, None)


def test_a_stream_that_does_not_play_gives_way_to_the_next(tmp_path, no_real_wait):
    fake = FakeHa(rows=[ROWS[0]], dead=["/1tv/"])
    c = _client(tmp_path, fake)
    cmd = _play(c).json()
    assert (cmd["state"], cmd["detail"]) == ("started", "cast")
    sent = [b["media_content_id"] for s, b in fake.calls if s == "media_player.play_media"]
    assert len(sent) == 2 and "/1tv/" in sent[0] and "/1tv_plus2/" in sent[1]
    assert no_real_wait[0] >= 15  # the first one had its 15 s
    conn = db.connect(c.app.state.settings.db_path)
    row = conn.execute("SELECT stream_id, offered, failed FROM playback_commands").fetchone()
    conn.close()
    offered = json.loads(row["offered"])
    assert row["stream_id"] == offered[1] and json.loads(row["failed"]) == [offered[0]]
    assert [r["outcome"] for r in _opens(c)] == ["opened"]
    c.__exit__(None, None, None)


def test_a_tv_that_never_says_it_plays_is_started_unconfirmed(tmp_path):
    fake = FakeHa(rows=[ROWS[0]], silent=True)
    c = _client(tmp_path, fake)
    cmd = _play(c).json()
    assert (cmd["state"], cmd["detail"]) == ("started", "unconfirmed")
    assert sum(s == "media_player.play_media" for s, _ in fake.calls) == 2
    assert [r["outcome"] for r in _opens(c)] == ["slow"]
    c.__exit__(None, None, None)


def test_adb_spare_goes_to_the_same_player(tmp_path):
    fake = FakeHa(
        dead=["/1tv/"],
        adb_answers=["Error: unable to resolve Intent", "Starting: Intent", "Starting: Intent"],
    )
    c = _client(tmp_path, fake)
    cmd = _play(c, tv="media_player.living_room_adb").json()
    assert (cmd["state"], cmd["detail"]) == ("started", "adb:just")
    adb = [b["command"] for s, b in fake.calls if s == "androidtv.adb_command"]
    assert len(adb) == 3 and "/1tv_plus2/" in adb[2] and "com.brouken.player" in adb[2]
    assert [s for s, _ in fake.calls].count("media_player.turn_on") == 1
    c.__exit__(None, None, None)


@pytest.mark.parametrize(("state", "way", "fresh", "ours"), [
    ({"state": "playing", "attributes": {"media_content_id": "u"}}, "cast", False, True),
    ({"state": "playing", "attributes": {"media_content_id": "old"}}, "cast", True, False),
    ({"state": "buffering", "attributes": {"media_content_id": "u"}}, "cast", True, False),
    ({"state": "playing", "attributes": {}}, "airplay", True, True),
    ({"state": "playing", "attributes": {}}, "airplay", False, False),
    ({"state": "playing", "attributes": {"app_id": "org.videolan.vlc"}}, "adb:vlc", True, True),
    ({"state": "playing", "attributes": {"app_id": "com.netflix"}}, "adb:vlc", True, False),
])  # fmt: skip
def test_which_playing_is_our_stream(state, way, fresh, ours):
    assert tv.is_ours(state, "u", way, fresh) is ours
