# Where this engine comes from

- Imported from Banzay7/MIH, commit e7648d4901e2ed61a409ef7a2f89b32574612e14 (2026-11-02),
  folders `src/`, `tests/` and `pyproject.toml`; left out: the VPS stand test `test_mihctl_update.py`.
- From then on the add-on's engine is developed here. Fixes from MIH are brought over
  by hand, one PR each, naming the MIH commit.

## Changes made here

- Home Assistant Ingress: `MIH_INGRESS_PROXY` (the add-on sets the Supervisor proxy
  172.30.32.2) lets the sidebar panel in without `MIH_API_TOKEN` and allows HA's frame
  (`X-Frame-Options: SAMEORIGIN`); the web UI and `/api/docs` use relative paths.
- Light mode (`mih.upkeep`): `MIH_CATALOG_EVERY` rebuilds the catalog only when its data
  changed and at most that often (a put-off build runs from the scheduler's tick);
  `MIH_EPG_AT` runs the guide at a local time; `MIH_JOB_NICE` lowers the jobs' thread;
  `MIH_DISCOVERY_FRESH_DAYS` (default 60) sets how long the search starts over daily.
  Jobs of one process run strictly one at a time. Each catalog build logs its time and
  the peak memory; the data size is logged and shown on the status screen.
- Launch on a TV without a script (`mih.tv`, `MIH_PLAYBACK=tv`, the add-on's default):
  the TVs are HA's `media_player` entities grouped by device; a launch tries ADB
  (`androidtv.adb_command`, VIEW intent to VLC, then Just Player), Google Cast, AirPlay,
  then any player with `play_media`. `GET /api/v1/tv`, `PUT /api/v1/settings/tv` (the
  default TV, in `app_settings`), `tv` in `POST /api/v1/playback/commands`.
- Help for the add-on (`ui/static/help`): written for Home Assistant (sidebar, light mode,
  launch on a TV, the access token explained); only ru, en and vi are kept, the other
  interface languages read the English guide. `GET /api/v1/health/live` tells the web UI
  how the browser got in (`access`: ha, token or open), and Settings shows the token
  field only when the server asks for one.
