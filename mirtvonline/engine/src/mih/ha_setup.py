"""What the add-on puts into Home Assistant so channels start from HA itself.

The button «Создать в Home Assistant» (Settings → Home Assistant) adds, through HA's
config API, what is missing of:

- ``script.mirtv_channel``: turn a channel on by its name. Fields ``channel`` and
  optional ``tv``. It hands the name to the add-on (``hassio.addon_stdin``), and the
  add-on starts the channel the way «На ТВ» does. Assist with an AI, automations, the
  dashboard and an outside agent (through HA's MCP Server) all use it.
- ``automation.mirtvonline_voice``: Assist without an AI. Phrases like «включи канал
  Первый» run the script.
- ``script.mih_play``: the script the «Через свой скрипт HA» way of «На ТВ» calls with
  the stream URLs; a template that plays the stream on the TV, to change at will.

Nothing that exists is changed: the user may have edited it. Only works inside the
add-on (MIH_HA_ADDON names it), where the Supervisor token may edit HA's config.
"""

from __future__ import annotations

import httpx

from mih.config import Settings
from mih.ha import _HTTP_ERRORS, HaError, _client, _message, clean

CHANNEL_SCRIPT = "mirtv_channel"
VOICE_AUTOMATION = "mirtvonline_voice"

_TEXT = {
    "ru": {
        "channel_alias": "MIRTVONLINE: включить канал",
        "channel_desc": (
            "Включает телеканал из каталога MIRTVONLINE на телевизоре. channel: название "
            "канала, как его называют люди (например «Первый канал», «Матч ТВ»). tv: "
            "необязательно, media_player телевизора; без него канал включится на "
            "телевизоре по умолчанию из настроек MIRTVONLINE."
        ),
        "channel": "Канал",
        "channel_field": "Название канала, например «Первый канал»",
        "channel_example": "Первый канал",
        "tv": "Телевизор",
        "tv_field": "Необязательно. Без него: телевизор по умолчанию из настроек MIRTVONLINE",
        "voice_alias": "MIRTVONLINE: голосом «включи канал …»",
        "voice_desc": "Фразы для Assist. Создано MIRTVONLINE; можно менять и добавлять фразы.",
        "voice_commands": [
            "включи канал {channel}",
            "включи на телевизоре {channel}",
            "поставь канал {channel}",
            "переключи на канал {channel}",
            "канал {channel}",
        ],
        "voice_answer": "Включаю {{ trigger.slots.channel }}",
        "play_alias": "MIRTVONLINE: свой запуск потока",
        "play_desc": (
            "Вызывается кнопкой «На ТВ», когда на сайте выбран способ «Через свой скрипт "
            "HA». Получает url (лучший поток), urls (до трёх), channel (название) и tv "
            "(телевизор по умолчанию). Меняйте шаги как нужно: включить ТВ, сменить вход, "
            "открыть плеер."
        ),
    },
    "en": {
        "channel_alias": "MIRTVONLINE: turn on a channel",
        "channel_desc": (
            "Turns on a TV channel from the MIRTVONLINE catalog on a TV. channel: the "
            "channel's name as people say it (e.g. 'BBC One'). tv: optional, the TV's "
            "media_player; without it the default TV from MIRTVONLINE settings is used."
        ),
        "channel": "Channel",
        "channel_field": "The channel's name, e.g. 'BBC One'",
        "channel_example": "BBC One",
        "tv": "TV",
        "tv_field": "Optional. Without it: the default TV from MIRTVONLINE settings",
        "voice_alias": "MIRTVONLINE: voice 'play channel …'",
        "voice_desc": "Phrases for Assist. Made by MIRTVONLINE; change or add phrases freely.",
        "voice_commands": [
            "play channel {channel}",
            "turn on channel {channel}",
            "put on channel {channel}",
            "switch to channel {channel}",
            "watch {channel} on tv",
        ],
        "voice_answer": "Turning on {{ trigger.slots.channel }}",
        "play_alias": "MIRTVONLINE: own stream launch",
        "play_desc": (
            "Called by «On TV» when the site uses the 'own HA script' way. Gets url (the "
            "best stream), urls (up to three), channel (the name) and tv (the default "
            "TV). Change the steps as you need: turn the TV on, switch input, open a player."
        ),
    },
}


def _text(settings: Settings) -> dict:
    return _TEXT.get(settings.lang, _TEXT["en"])


def channel_script(settings: Settings) -> dict:
    tx = _text(settings)
    return {
        "alias": tx["channel_alias"],
        "description": tx["channel_desc"],
        "icon": "mdi:television-play",
        "mode": "queued",
        "fields": {
            "channel": {"name": tx["channel"], "description": tx["channel_field"],
                        "required": True, "example": tx["channel_example"],
                        "selector": {"text": {}}},
            "tv": {"name": tx["tv"], "description": tx["tv_field"], "required": False,
                   "selector": {"entity": {"domain": "media_player"}}},
        },  # fmt: skip
        "sequence": [{
            "action": "hassio.addon_stdin",
            "data": {"addon": settings.ha_addon,
                     "input": {"play": "{{ channel }}", "tv": "{{ tv | default('') }}"}},
        }],  # fmt: skip
    }


def voice_automation(settings: Settings) -> dict:
    tx = _text(settings)
    return {
        "alias": tx["voice_alias"],
        "description": tx["voice_desc"],
        "mode": "queued",
        "triggers": [{"trigger": "conversation", "command": tx["voice_commands"]}],
        "conditions": [],
        "actions": [
            {"action": f"script.{CHANNEL_SCRIPT}",
             "data": {"channel": "{{ trigger.slots.channel }}"}},
            {"set_conversation_response": tx["voice_answer"]},
        ],  # fmt: skip
    }


def play_script(settings: Settings) -> dict:
    tx = _text(settings)
    return {
        "alias": tx["play_alias"],
        "description": tx["play_desc"],
        "icon": "mdi:script-text-play",
        "mode": "restart",
        "fields": {name: {"selector": {"text": {}}} for name in ("url", "channel", "tv")},
        "sequence": [{
            "action": "media_player.play_media",
            "target": {"entity_id": "{{ tv }}"},
            "data": {"media_content_id": "{{ url }}", "media_content_type": "video"},
        }],  # fmt: skip
    }


def items(settings: Settings) -> list[tuple[str, str, dict]]:
    """(kind, id, config) of everything the add-on offers to create."""
    script = settings.ha_script.strip().removeprefix("script.") or "mih_play"
    return [
        ("script", CHANNEL_SCRIPT, channel_script(settings)),
        ("automation", VOICE_AUTOMATION, voice_automation(settings)),
        ("script", script, play_script(settings)),
    ]


def _entity(kind: str, key: str) -> str:
    return f"{kind}.{key}"


def _exists(client: httpx.Client, settings: Settings, kind: str, key: str) -> bool:
    resp = _get(client, f"{settings.ha_url}/api/config/{kind}/config/{key}")
    if resp.status_code == 404:
        return False
    if resp.status_code >= 400:
        raise HaError(_HTTP_ERRORS.get(resp.status_code, "ha_error"), str(resp.status_code))
    return True


def _get(client: httpx.Client, url: str) -> httpx.Response:
    try:
        return client.get(url)
    except httpx.TimeoutException as exc:
        raise HaError("ha_timeout", "Home Assistant did not answer in time") from exc
    except httpx.HTTPError as exc:
        raise HaError("ha_unreachable", type(exc).__name__) from exc


def _ready(settings: Settings) -> None:
    if not settings.ha_ready:
        raise HaError("ha_not_configured", "Home Assistant is not set up")
    if not settings.ha_addon:
        raise HaError("ha_not_addon", "only the Home Assistant add-on can set this up")


def status(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> dict:
    """What of it is in Home Assistant already. Reads only."""
    out = {"ok": False, "error": None, "addon": settings.ha_addon, "items": []}
    try:
        _ready(settings)
        with _client(settings, transport) as client:
            for kind, key, _ in items(settings):
                out["items"].append({"entity_id": _entity(kind, key),
                                     "exists": _exists(client, settings, kind, key)})  # fmt: skip
    except HaError as exc:
        out["error"] = exc.code
        return out
    out["ok"] = True
    return out


def create(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> dict:
    """Add what is missing; what exists stays as the user left it."""
    _ready(settings)
    made, kept = [], []
    with _client(settings, transport) as client:
        for kind, key, config in items(settings):
            if _exists(client, settings, kind, key):
                kept.append(_entity(kind, key))
                continue
            body = {"id": key, **config} if kind == "automation" else config
            try:
                resp = client.post(f"{settings.ha_url}/api/config/{kind}/config/{key}", json=body)
            except httpx.HTTPError as exc:
                raise HaError("ha_unreachable", type(exc).__name__) from exc
            if resp.status_code in (401, 403):
                raise HaError("ha_unauthorized", f"{kind} {key}: {resp.status_code}")
            if resp.status_code >= 400:
                raise HaError("ha_setup_failed", f"{kind} {key}: {resp.status_code}",
                              clean(_message(resp)))  # fmt: skip
            made.append(_entity(kind, key))
    return {"created": made, "kept": kept}
