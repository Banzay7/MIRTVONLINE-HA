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
