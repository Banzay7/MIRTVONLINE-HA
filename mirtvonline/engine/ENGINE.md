# Where this engine comes from

- Imported from Banzay7/MIH, commit e7648d4901e2ed61a409ef7a2f89b32574612e14 (2026-11-02),
  folders `src/`, `tests/` and `pyproject.toml`; left out: the VPS stand test `test_mihctl_update.py`.
- From then on the add-on's engine is developed here. Fixes from MIH are brought over
  by hand, one PR each, naming the MIH commit.

## Changes made here

- Home Assistant Ingress: `MIH_INGRESS_PROXY` (the add-on sets the Supervisor proxy
  172.30.32.2) lets the sidebar panel in without `MIH_API_TOKEN` and allows HA's frame
  (`X-Frame-Options: SAMEORIGIN`); the web UI and `/api/docs` use relative paths.
