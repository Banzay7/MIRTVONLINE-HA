# Changelog

## 0.1.3

- Light mode for home boxes: background jobs run strictly one at a time and at a lower
  priority than the site; the catalog is rebuilt only when its data changed and at most
  once an hour.
- Default schedule: the guide daily at 03:30, your playlists daily, re-check of working
  streams weekly; the playlist search starts over daily for the first 3 days, then monthly.
- The log shows how long each catalog build took, the peak memory and the size of the
  add-on's data; the **Status** page shows the data size (database, snapshots, other)
  and the last catalog build.

## 0.1.2

- Fix install: Home Assistant built the add-on on its own Alpine base without Python
  (`pip: not found`); the Python base image is now fixed in the Dockerfile.

## 0.1.1

- The site opens from the Home Assistant sidebar (Ingress) with no token prompt.
- The web UI and the API docs work under the Ingress path.

## 0.1.0

- First skeleton: Ingress panel, options for language, profile, home country,
  time zone and GitHub token.
- Engine inside the add-on, imported from MIH commit `e7648d4`.
