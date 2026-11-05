# Changelog

## 0.1.9

- **Status** no longer lists "Upload to Google Drive": the add-on has no Drive set up,
  so the job could only fail. The **Pushes** line says pushes are not in the add-on and
  that reminders and results are under **Events**, instead of naming `MIH_NTFY_URL`.
- Topics and "Run" no longer promise a push: the reminder shows up under **Events**.
- The playlist search is called the same everywhere ("Playlist scout"), not "grabber".
- The site's **Settings** and **Status** show the add-on's version, not `0.1.0.dev0`.

## 0.1.8

- **Settings** → **The "On TV" button** shows only what works in the add-on: the
  "Through the agent" choice is gone (no agent can take commands here), and a browser
  that kept it gets "Straight to the TV". The script way is now called "Through your
  own HA script" with its script's name.
- Error texts for this button speak of the add-on, not of server variables
  (`MIH_HA_URL`, `MIH_HA_SCRIPT`, Tailscale). "No TV chosen" points to **TV**.
- The open speed says honestly that with "Straight to the TV" it only times how long
  Home Assistant takes to accept the command; the channel page names this way.

## 0.1.7

- The **Configuration** tab tells what each option really does. `language` is now
  called "Notification and script language" (the site's own language is picked in the
  browser); the home country no longer promises a setup wizard; the profiles name their
  stream limits; channel languages explain the format and the order at the limit.

## 0.1.6

- Your channels first at the stream limit. The profile caps found streams (S 6,000,
  M 15,000, L 30,000); your own playlists are not counted. Channels of the home country,
  in your channels' languages and favourites are checked first; once the limit is
  reached, only they are added, and found streams of other channels (broken ones first)
  make room for them. Your channels are never removed.
- New option `channel_languages` (e.g. `ru, en`); empty means the add-on's language.

## 0.1.5

- Channels start from Home Assistant itself. The site's **Settings** → **Scripts and
  voice commands** → **Create in Home Assistant** adds, if missing:
  `script.mirtv_channel` (turn a channel on by its name; Assist, automations,
  dashboards and an outside agent through HA's MCP Server call it), the automation
  `automation.mirtvonline_voice` (Assist phrases "play channel …") and the template
  `script.mih_play` for the "own HA script" way. Existing ones are never overwritten.
- A channel asked from Home Assistant that did not start shows up as a Home Assistant
  notification.
- The help on the site was reworked (sign-in, token, light mode, launch on a TV).

## 0.1.4

- **On TV** starts the channel on a TV of Home Assistant itself, no script needed: ADB
  intent to VLC or Just Player first, then Google Cast, then AirPlay. The TV list comes
  from Home Assistant; pick the TV in the site's **Settings** → **TV** (a default TV for
  everyone, and one per browser).

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
