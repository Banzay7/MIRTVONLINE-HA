"""Your channels first when found playlists hit the stream limit (MIH_DISCOVERY_MAX_STREAMS).

The limit counts only streams of found playlists ("auto: ..." sources); playlists you
added yourself are never counted and never touched. Below the limit the packer checks
preferred streams of a playlist first. At the limit it keeps going only for preferred
streams: the scout samples only those, the packer imports only those and makes room by
removing other found streams, the worst first (gone from the playlist, archived,
quarantined, suspect, never checked, oldest working).

Preferred: a channel of the home country (MIH_HOME_COUNTRY) or in one of the chosen
languages (MIH_CHANNEL_LANGUAGES), and channels you marked as favourites. Their streams
are never removed to make room. The country and languages come from the stream itself
(tvg-id "ZDF.de", tvg-country, tvg-language, a group named after a country) and from
the iptv-org directory.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

from mih.config import Settings
from mih.identity.normalize import tvg_base
from mih.lists import normalize_lang
from mih.places import country_of_group
from mih.sources.m3u import M3UEntry

_COUNTRY_RE = re.compile(r"\.([a-z]{2})$")
_SPLIT_RE = re.compile(r"[;,|]")
# Removed first when room is needed: gone from the playlist, then by health.
_WORST_FIRST = (
    "CASE WHEN s.availability_reason IS NOT NULL THEN 0 ELSE 1 END,"
    " CASE s.status WHEN 'archived' THEN 0 WHEN 'quarantine' THEN 1 WHEN 'suspect' THEN 2"
    " WHEN 'unverified' THEN 3 WHEN 'new' THEN 4 ELSE 5 END,"
    " coalesce(s.last_ok_at, ''), s.first_seen_at"
)


@dataclass(frozen=True)
class Preference:
    home: str | None = None
    languages: frozenset[str] = frozenset()
    # tvg-id bases (casefolded) of favourite channels.
    favourites: frozenset[str] = frozenset()

    @property
    def active(self) -> bool:
        return bool(self.home or self.languages or self.favourites)


def load(conn: sqlite3.Connection, settings: Settings) -> Preference:
    favourites = frozenset(
        r[0].casefold() for r in conn.execute(
            "SELECT a.value FROM channel_aliases a JOIN favorites f"
            " ON f.target_kind = 'channel' AND f.target_id = a.channel_id"
            " WHERE a.kind = 'tvg-id'"
        )
    )  # fmt: skip
    return Preference(
        home=(settings.home_country or "").lower() or None,
        languages=frozenset(settings.channel_languages),
        favourites=favourites,
    )


def wanted(conn: sqlite3.Connection, pref: Preference, entries: list[M3UEntry]) -> list[bool]:
    """For each playlist entry: is it one of yours?"""
    if not pref.active:
        return [False] * len(entries)
    bases = [tvg_base(e.tvg_id) if e.tvg_id else "" for e in entries]
    directory = _directory(conn, sorted({b for b in bases if b}))
    out = []
    for e, base in zip(entries, bases, strict=True):
        countries, langs = set(), set()
        if m := _COUNTRY_RE.search(base):
            countries.add(m.group(1))
        countries |= {v.strip().lower() for v in _SPLIT_RE.split(e.attrs.get("tvg-country", ""))}
        langs |= {normalize_lang(v) for v in _SPLIT_RE.split(e.attrs.get("tvg-language", ""))
                  if v.strip()}  # fmt: skip
        if base in directory:
            country, dir_langs = directory[base]
            countries.add(country)
            langs |= dir_langs
        if pref.home and pref.home not in countries:
            for g in _SPLIT_RE.split(e.group or ""):
                if g.strip() and (c := country_of_group(g.strip())):
                    countries.add(c.lower())
        out.append(
            base in pref.favourites
            or (pref.home is not None and pref.home in countries)
            or bool(pref.languages & langs)
        )
    return out


def protected_channels(conn: sqlite3.Connection, pref: Preference) -> set[str]:
    """Channels whose found streams are never removed to make room."""
    out = {r[0] for r in conn.execute(
        "SELECT target_id FROM favorites WHERE target_kind = 'channel'")}  # fmt: skip
    home, langs = pref.home, pref.languages
    if home:
        for r in conn.execute(
            "SELECT c.id, c.country, d.country FROM channels c"
            " LEFT JOIN directory_channels d ON d.id = c.directory_id"
        ):
            if home in ((r[1] or "").lower(), (r[2] or "").lower()):
                out.add(r[0])
        aliases = "SELECT channel_id, value FROM channel_aliases WHERE kind = 'tvg-id'"
        for r in conn.execute(aliases):
            m = _COUNTRY_RE.search(tvg_base(r[1]))
            if m and m.group(1) == home:
                out.add(r[0])
    if langs:
        marks = ",".join("?" * len(langs))
        out |= {r[0] for r in conn.execute(
            f"SELECT channel_id FROM channel_tags WHERE kind = 'language' AND value IN ({marks})"
            f" UNION SELECT channel_id FROM feeds WHERE audio_lang IN ({marks})",
            (*langs, *langs),
        )}  # fmt: skip
        for r in conn.execute(
            "SELECT c.id, d.languages FROM channels c"
            " JOIN directory_channels d ON d.id = c.directory_id WHERE d.languages IS NOT NULL"
        ):
            if langs & {normalize_lang(v) for v in json.loads(r[1] or "[]")}:
                out.add(r[0])
    return out


def make_room(conn: sqlite3.Connection, pref: Preference, need: int) -> int:
    """Remove up to ``need`` found streams of channels that are not yours, the worst
    first. Returns how many went. Your own playlists are never touched."""
    if need <= 0:
        return 0
    keep = protected_channels(conn, pref)
    victims: list[str] = []
    touched: set[str] = set()
    for r in conn.execute(
        "SELECT s.id, f.channel_id FROM streams s JOIN feeds f ON f.id = s.feed_id"
        " WHERE s.source_id IN"
        " (SELECT source_id FROM discovered_playlists WHERE source_id IS NOT NULL)"
        f" ORDER BY {_WORST_FIRST}"
    ):
        if r[1] in keep:
            continue
        victims.append(r[0])
        touched.add(r[1])
        if len(victims) >= need:
            break
    if not victims:
        return 0
    conn.execute("BEGIN")
    try:
        for chunk in _chunks(victims):
            marks = ",".join("?" * len(chunk))
            conn.execute(f"UPDATE source_records SET stream_id = NULL WHERE stream_id IN ({marks})",
                         chunk)  # fmt: skip
            conn.execute(f"DELETE FROM streams WHERE id IN ({marks})", chunk)
        # A channel left with no stream at all goes too (its feeds and tags with it).
        for chunk in _chunks(sorted(touched)):
            marks = ",".join("?" * len(chunk))
            conn.execute(
                f"DELETE FROM channels WHERE id IN ({marks}) AND NOT EXISTS (SELECT 1 FROM"
                " streams s JOIN feeds f ON f.id = s.feed_id WHERE f.channel_id = channels.id)",
                chunk,
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(victims)


def _directory(conn, bases: list[str]) -> dict[str, tuple[str, set[str]]]:
    out = {}
    for chunk in _chunks(bases):
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(
            f"SELECT lower(id), country, languages FROM directory_channels"
            f" WHERE lower(id) IN ({marks})", chunk,
        ):  # fmt: skip
            langs = {normalize_lang(v) for v in json.loads(r[2] or "[]")}
            out[r[0]] = ((r[1] or "").lower(), langs)
    return out


def _chunks(items: list[str], size: int = 500):
    for i in range(0, len(items), size):
        yield items[i : i + size]
