"""Commands from Home Assistant: ``hassio.addon_stdin`` writes JSON to the add-on's stdin.

script.mirtv_channel sends ``{"play": "<channel name>", "tv": "<media_player or ''>"}``.
Each one becomes the same launch as "На ТВ" (POST /api/v1/playback/by-name on the
local server). A channel that did not start becomes a notification in Home Assistant,
so a voice command or an automation is not left without an answer.

Home Assistant writes the JSON with no newline between commands, so the stream is cut
into JSON values, not lines.
"""

from __future__ import annotations

import codecs
import json
import os
import sys
import time

API = "http://127.0.0.1:8765/api/v1"
HA_URL = os.environ.get("MIH_HA_URL", "")
ERRORS = {
    "ru": {
        "title": "MIRTVONLINE: канал не включился",
        "not_found": "Канал «{0}» не найден в каталоге.",
        "failed": "Канал «{0}» не включился: {1}.",
        "down": "Сервер дополнения ещё не запущен, попробуйте через минуту.",
    },
    "en": {
        "title": "MIRTVONLINE: the channel did not start",
        "not_found": "No channel '{0}' in the catalog.",
        "failed": "Channel '{0}' did not start: {1}.",
        "down": "The add-on is still starting, try again in a minute.",
    },
}


def values(stream) -> object:
    """Yield the JSON values in a byte stream as they arrive."""
    decoder = json.JSONDecoder()
    # A letter may be cut between two reads: decode bytes incrementally.
    text = codecs.getincrementaldecoder("utf-8")("replace")
    buf = ""
    while True:
        chunk = stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096)
        if not chunk:
            return
        buf += text.decode(chunk)
        while True:
            buf = buf.lstrip()
            if not buf:
                break
            try:
                value, end = decoder.raw_decode(buf)
            except json.JSONDecodeError:
                if len(buf) > 65536:  # garbage, not a JSON value still arriving
                    buf = ""
                break
            buf = buf[end:]
            yield value


def command(value: object) -> dict | None:
    """{"play": name, "tv": entity} from what HA sent; a bare string is a channel name."""
    if isinstance(value, str):
        value = {"play": value}
    if not isinstance(value, dict):
        return None
    name = str(value.get("play") or value.get("channel") or "").strip()
    if not name:
        return None
    tv = str(value.get("tv") or "").strip()
    return {"channel": name[:100], "tv": tv if tv.startswith("media_player.") else None}


def play(client, cmd: dict) -> tuple[bool, str]:
    """Start it; (ok, what to log)."""
    import httpx  # in the image; the repository's own tests need no httpx

    body = {k: v for k, v in cmd.items() if v}
    for attempt in range(3):
        try:
            resp = client.post(f"{API}/playback/by-name", json=body)
            break
        except httpx.ConnectError:
            if attempt == 2:
                return False, "down"
            time.sleep(5)
    if resp.status_code == 404:
        return False, "not_found"
    out = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code >= 400:
        return False, str((out.get("error") or {}).get("code") or resp.status_code)
    if out.get("state") == "failed":
        return False, str(out.get("error") or "failed")
    name = (out.get("channel") or {}).get("name") or cmd["channel"]
    return True, f"{name}: {out.get('state')} {out.get('detail') or ''}".strip()


def notify(lang: str, cmd: dict, reason: str) -> None:
    import httpx

    token = os.environ.get("MIH_HA_TOKEN")
    if not (HA_URL and token):
        return
    tx = ERRORS.get(lang, ERRORS["en"])
    key = reason if reason in ("not_found", "down") else "failed"
    text = tx[key].format(cmd["channel"], reason)
    try:
        httpx.post(f"{HA_URL}/api/services/persistent_notification/create",
                   headers={"Authorization": f"Bearer {token}"}, timeout=10,
                   json={"title": tx["title"], "message": text,
                         "notification_id": "mirtvonline_play"})  # fmt: skip
    except httpx.HTTPError:
        pass


def main() -> int:
    import httpx

    lang = os.environ.get("MIH_LANG", "en")
    headers = {"Authorization": f"Bearer {os.environ['MIH_API_TOKEN']}"}
    with httpx.Client(headers=headers, timeout=120) as client:
        for value in values(sys.stdin.buffer):
            cmd = command(value)
            if cmd is None:
                print("MIRTVONLINE: Home Assistant sent an unknown command", flush=True)
                continue
            ok, said = play(client, cmd)
            print(f"MIRTVONLINE: from Home Assistant «{cmd['channel']}»: "
                  f"{said if ok else 'not started, ' + said}", flush=True)  # fmt: skip
            if not ok:
                notify(lang, cmd, said)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
