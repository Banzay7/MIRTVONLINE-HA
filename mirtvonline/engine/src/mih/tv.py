"""Launch on a TV through Home Assistant's own media players, with no script of the user.

Inside the add-on MIH reaches Home Assistant with the Supervisor token (MIH_HA_URL =
http://supervisor/core). The TVs are the ``media_player`` entities HA already has; one TV
is often several entities (the ADB integration and Google Cast see the same Android TV),
so entities of one device, or of devices with the same name, make one TV.

A launch tries the TV's ways in this order and stops at the first that HA accepts:

1. **ADB** (integration ``androidtv``): ``androidtv.adb_command`` sends a VIEW intent with
   the stream to VLC, then to Just Player. A TV that is off is turned on first. HA keeps
   the command's output in the entity's ``adb_response``; "Error" there means the player
   is not installed, and the next one is tried.
2. **Google Cast** (``cast``): ``media_player.play_media`` with the stream's MIME type.
3. **AirPlay** (``apple_tv``): ``media_player.play_media``.
4. Any other media player that can play a URL (DLNA and the like).

HA accepting the call is not the picture yet. After it MIH watches the entity in HA until
it says ``playing`` this very stream (``media_content_id`` is the stream's address, or the
player went from something else to ``playing``). That moment is the real open time. A
stream that does not play within ``MIH_TV_WAIT_S`` seconds (15 by default) is replaced by
the next of the picked ones on the same way, up to three in all. When none was seen
playing, the launch counts as started but unconfirmed: some TVs never report it.
"""

from __future__ import annotations

import json
import re
import shlex
import sqlite3
import time
from dataclasses import dataclass, field

import httpx

from mih.config import Settings
from mih.ha import _HTTP_ERRORS, HaError, _client, _message, clean
from mih.ids import utc_now

# The order of the ways a TV is tried, best first.
METHODS = ("adb", "cast", "airplay", "media")
_BY_INTEGRATION = {"androidtv": "adb", "cast": "cast", "apple_tv": "airplay"}
# media_player feature bit: can play a URL (MediaPlayerEntityFeature.PLAY_MEDIA).
PLAY_MEDIA = 512
# Players on the TV that take a stream from an intent: package names, best first.
PLAYERS = (("vlc", "org.videolan.vlc"), ("just", "com.brouken.player"))
ENTITY = re.compile(r"^media_player\.[a-z0-9_]{1,120}$")
# How often the entity's state is asked while waiting for the picture, seconds.
POLL_S = 0.5
# Replaced in tests, so waiting takes no real time.
_clock = time.monotonic
_sleep = time.sleep

# One request gives every media player with its device and integration.
_TEMPLATE = """{%- set ns = namespace(rows=[]) -%}
{%- set by = {'androidtv': integration_entities('androidtv'),
  'cast': integration_entities('cast'), 'apple_tv': integration_entities('apple_tv')} -%}
{%- for s in states.media_player -%}
{%- set d = device_id(s.entity_id) -%}
{%- set ns.rows = ns.rows + [{'entity_id': s.entity_id, 'name': s.name, 'state': s.state,
  'features': s.attributes.supported_features | default(0) | int,
  'device_class': s.attributes.device_class | default(none),
  'device': d, 'device_name': (device_attr(d, 'name_by_user') or device_attr(d, 'name'))
    if d else none,
  'integration': 'androidtv' if s.entity_id in by.androidtv else 'cast'
    if s.entity_id in by.cast else 'apple_tv' if s.entity_id in by.apple_tv else none}] -%}
{%- endfor -%}
{{ ns.rows | tojson }}"""


@dataclass
class Tv:
    id: str  # the entity tried first; stable enough to keep as the choice
    name: str
    entities: list[dict] = field(default_factory=list)  # {entity_id, method, state}

    def as_dict(self) -> dict:
        states = [e["state"] for e in self.entities]
        state = next((s for s in states if s not in ("unavailable", "unknown")), states[0])
        return {"id": self.id, "name": self.name, "state": state,
                "methods": list(dict.fromkeys(e["method"] for e in self.entities)),
                "entities": self.entities}  # fmt: skip

    def has(self, entity_id: str) -> bool:
        return any(e["entity_id"] == entity_id for e in self.entities)


def method_of(row: dict) -> str | None:
    """How this media player can start a stream; None = it cannot."""
    method = _BY_INTEGRATION.get(row.get("integration") or "")
    if method:
        return method
    return "media" if int(row.get("features") or 0) & PLAY_MEDIA else None


def _norm(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def group(rows: list[dict]) -> list[Tv]:
    """Media players -> TVs: one device, or devices of the same name, is one TV.
    Speakers and players that cannot start a stream are left out."""
    groups: dict[str, Tv] = {}
    for row in rows:
        method = method_of(row)
        if method is None or row.get("device_class") == "speaker":
            continue
        name = (row.get("device_name") or row.get("name") or row["entity_id"]).strip()
        key = _norm(name) or row["entity_id"]
        tv = groups.setdefault(key, Tv(id="", name=name))
        tv.entities.append({"entity_id": row["entity_id"], "method": method,
                            "state": row.get("state") or "unknown"})  # fmt: skip
    out = []
    for tv in groups.values():
        tv.entities.sort(key=lambda e: (METHODS.index(e["method"]), e["entity_id"]))
        tv.id = tv.entities[0]["entity_id"]
        out.append(tv)
    return sorted(out, key=lambda t: t.name.casefold())


def _call(client: httpx.Client, settings: Settings, path: str, **kw) -> httpx.Response:
    try:
        resp = client.request(kw.pop("method", "POST"), f"{settings.ha_url}{path}", **kw)
    except httpx.TimeoutException as exc:
        raise HaError("ha_timeout", "Home Assistant did not answer in time") from exc
    except httpx.HTTPError as exc:
        raise HaError("ha_unreachable", f"Home Assistant is unreachable: {type(exc).__name__}"
                      ) from exc  # fmt: skip
    if resp.status_code in (401, 403):
        raise HaError("ha_unauthorized", f"Home Assistant answered {resp.status_code}")
    return resp


def _rows(client: httpx.Client, settings: Settings) -> list[dict]:
    resp = _call(client, settings, "/api/template", json={"template": _TEMPLATE})
    if resp.status_code < 400:
        try:
            rows = json.loads(resp.text)
            if isinstance(rows, list):
                return rows
        except ValueError:
            pass
    # No template endpoint: plain states, the integration guessed from the attributes.
    resp = _call(client, settings, "/api/states", method="GET")
    if resp.status_code >= 400:
        raise HaError(_HTTP_ERRORS.get(resp.status_code, "ha_error"), str(resp.status_code))
    out = []
    for s in resp.json() if isinstance(resp.json(), list) else []:
        eid = s.get("entity_id", "")
        if not eid.startswith("media_player."):
            continue
        attrs = s.get("attributes") or {}
        out.append({"entity_id": eid, "name": attrs.get("friendly_name") or eid,
                    "state": s.get("state"), "features": attrs.get("supported_features") or 0,
                    "device_class": attrs.get("device_class"),
                    "integration": "androidtv" if "adb_response" in attrs else None})  # fmt: skip
    return out


def list_tvs(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> list[Tv]:
    """The TVs Home Assistant knows. Raises HaError when it cannot be asked."""
    if not settings.ha_ready:
        raise HaError("ha_not_configured", "Home Assistant is not set up")
    with _client(settings, transport) as client:
        return group(_rows(client, settings))


def find(tvs: list[Tv], wanted: str | None) -> Tv:
    """The TV named by any of its entities; with none named, the only TV there is."""
    if wanted:
        tv = next((t for t in tvs if t.has(wanted)), None)
        if tv is None:
            raise HaError("tv_not_found", "the chosen TV is not in Home Assistant", wanted)
        return tv
    if len(tvs) == 1:
        return tvs[0]
    raise HaError("tv_not_chosen" if tvs else "tv_none", "no TV chosen")


def mime(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    if path.endswith((".m3u8", ".m3u")):
        return "application/x-mpegURL"
    if path.endswith(".mpd"):
        return "application/dash+xml"
    if path.endswith(".ts"):
        return "video/mp2t"
    return "video/mp4"


def intent(url: str, package: str) -> str:
    """The shell command that opens the stream in this player (adb shell runs it in sh)."""
    return (f"am start -a android.intent.action.VIEW -d {shlex.quote(url)}"
            f" -t video/* -p {package}")  # fmt: skip


def _service(client, settings, domain: str, service: str, data: dict) -> None:
    resp = _call(client, settings, f"/api/services/{domain}/{service}", json=data)
    if resp.status_code >= 400:
        raise HaError("tv_failed", f"{domain}.{service}: {resp.status_code}",
                      clean(_message(resp)))  # fmt: skip


def _state(client, settings, entity_id: str) -> dict:
    resp = _call(client, settings, f"/api/states/{entity_id}", method="GET")
    if resp.status_code >= 400:
        return {}
    body = resp.json()
    return body if isinstance(body, dict) else {}


def _adb(client, settings, entity: dict, url: str, only: str | None = None) -> str:
    """Open the stream in VLC, else Just Player; ``only`` = the player that worked before."""
    eid = entity["entity_id"]
    if entity["state"] in ("off", "standby"):
        _service(client, settings, "media_player", "turn_on", {"entity_id": eid})
        entity["state"] = "on"  # a spare stream needs no second wake-up
    for name, package in PLAYERS:
        if only and f"adb:{name}" != only:
            continue
        _service(client, settings, "androidtv", "adb_command",
                 {"entity_id": eid, "command": intent(url, package)})  # fmt: skip
        answer = str((_state(client, settings, eid).get("attributes") or {})
                     .get("adb_response") or "")  # fmt: skip
        if "error" not in answer.lower():
            return f"adb:{name}"
    raise HaError("tv_no_player", "neither VLC nor Just Player is installed on the TV")


def _start(client, settings, entity: dict, url: str, only: str | None = None) -> str:
    """Hand one stream to one entity; returns the way (adb:vlc, cast, airplay, media)."""
    if entity["method"] == "adb":
        return _adb(client, settings, entity, url, only)
    _service(client, settings, "media_player", "play_media", {
        "entity_id": entity["entity_id"], "media_content_id": url,
        "media_content_type": "video" if entity["method"] == "airplay" else mime(url),
    })  # fmt: skip
    return entity["method"]


def is_ours(state: dict, url: str, way: str, fresh: bool) -> bool:
    """Does this HA state say our stream plays? ``fresh``: the entity was seen not
    playing since the stream was sent, so ``playing`` now is the new stream."""
    if state.get("state") != "playing":
        return False
    attrs = state.get("attributes") or {}
    content = attrs.get("media_content_id")
    if content == url:
        return True
    if way.startswith("adb:"):
        package = dict(PLAYERS).get(way.removeprefix("adb:"))
        app = attrs.get("app_id")
        if app and app != package:
            return False
    elif content and way == "cast":
        return False  # Cast still shows the stream that played before
    return fresh


def _wait(client, settings, entity_id: str, url: str, way: str, before: dict,
          wait_s: float) -> bool:  # fmt: skip
    """Wait until the entity plays this stream; False when the time is up."""
    fresh = before.get("state") != "playing"
    deadline = _clock() + wait_s
    while True:
        state = _state(client, settings, entity_id)
        if is_ours(state, url, way, fresh):
            return True
        if state.get("state") != "playing":
            fresh = True
        if _clock() >= deadline:
            return False
        _sleep(POLL_S)


@dataclass
class Launch:
    way: str  # adb:vlc, adb:just, cast, airplay, media
    index: int  # which of the URLs plays (or was tried last, when not confirmed)
    confirmed: bool  # HA said it plays; False = accepted, but no picture was seen


def play(
    settings: Settings, tv_id: str | None, urls: list[str], *,
    transport: httpx.BaseTransport | None = None,
) -> Launch:  # fmt: skip
    """Start the first stream on the TV and wait for the picture; a stream that does not
    play in ``settings.tv_wait_s`` gives way to the next one on the same way. Raises
    HaError with the reason of the last way tried when no way accepted the first stream."""
    if not settings.ha_ready:
        raise HaError("ha_not_configured", "Home Assistant is not set up")
    if not urls:
        raise HaError("tv_failed", "no stream to start")
    with _client(settings, transport) as client:
        tv = find(group(_rows(client, settings)), tv_id)
        last: HaError | None = None
        for entity in tv.entities:
            if entity["state"] in ("unavailable",):
                last = last or HaError("tv_unavailable", "the TV is unavailable in HA")
                continue
            eid = entity["entity_id"]
            before = _state(client, settings, eid)
            try:
                way = _start(client, settings, entity, urls[0])
            except HaError as exc:
                if exc.code in ("ha_unauthorized", "ha_unreachable", "ha_timeout"):
                    raise
                last = exc
                continue
            # This way works: the spares go the same way.
            tried = 0
            for i, url in enumerate(urls):
                if i:
                    before = _state(client, settings, eid)
                    try:
                        _start(client, settings, entity, url, way)
                    except HaError as exc:
                        if exc.code in ("ha_unauthorized", "ha_unreachable", "ha_timeout"):
                            raise
                        continue
                tried = i
                if _wait(client, settings, eid, url, way, before, settings.tv_wait_s):
                    return Launch(way, i, True)
            return Launch(way, tried, False)
        raise last or HaError("tv_failed", "no way to start the stream on this TV")


# The TV everyone's "На ТВ" goes to unless a browser picked its own (app_settings).
_KEY_DEFAULT = "tv_default"


def default_tv(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (_KEY_DEFAULT,)).fetchone()
    return row["value"] if row else None


def set_default_tv(conn: sqlite3.Connection, entity_id: str | None) -> None:
    if not entity_id:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (_KEY_DEFAULT,))
        return
    conn.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)"
        " ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (_KEY_DEFAULT, entity_id, utc_now()),
    )
