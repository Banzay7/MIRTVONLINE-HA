# MIRTVONLINE

A catalog, TV guide and search for live TV channels, inside Home Assistant.
The add-on does not ship or relay any streams: it works with your own playlists
and public free ones, and the TV takes the stream straight from its source.

## Install

See the repository README for adding the repository. Then open **MIRTVONLINE**,
press **Install** (Home Assistant builds the image, a few minutes), turn on
**Show in sidebar** and press **Start**.

Keep **Auto update** off: update with the **Update** button after reading the changelog.

## Options

| Option | Meaning |
|---|---|
| Interface language | ru, en or vi |
| Data profile | S (default, any 4 GB box), M (Pi 5, mini PC), L (mini PC) |
| Home country | two letters, e.g. `de`; empty: the wizard asks |
| Time zone | e.g. `Europe/Berlin`; empty: the one of Home Assistant |
| GitHub token | optional, widens the playlist search |

## Data

Everything lives in the add-on's own `/data`: the database, snapshots and exported lists.
Home Assistant backups include the database; snapshots and exports are left out.

## Light mode and schedule

The add-on is tuned for a home box: one background job at a time, at a lower priority
than the site; the catalog is rebuilt only when its data changed and at most once an
hour. Default schedule:

| Job | When |
|---|---|
| Playlist scout | every 30 min; the search starts over daily for 3 days, then monthly |
| Playlist packer | every 15 min, 60 streams a run |
| Your playlists | daily |
| TV guide | daily at 03:30 (add-on time zone) |
| Re-check of working streams | weekly |

Up to 4 streams are checked at once (8 in profile L).

## Watching the load

The add-on log prints, after every catalog build, how long it took and the peak memory:
`catalog built in 3.2 s: 1520 channels, peak memory 240 MB`, and then the size of the data:
`data on disk: 310 MB (database 280, snapshots 20, export 2, other 8)`.
The **Status** page shows the same under **Data on disk**. Expected for profile S: about
1 GB on disk and up to 600 MB of memory; M: 2–3.5 GB and up to 900 MB.

## Launch on a TV

The **On TV** button starts the channel on a TV that Home Assistant already knows, with
no script of your own. The add-on finds the TVs among Home Assistant's media players;
the entities of one TV (for example ADB and Google Cast of the same Android TV) show up
as one TV. It tries, in this order:

1. **ADB** (integration **Android Debug Bridge**): opens the stream in **VLC**, else in
   **Just Player**; a TV that is off is turned on first. Install one of the two players
   on the TV from Google Play.
2. **Google Cast**: the Cast integration's media player.
3. **AirPlay**: the Apple TV integration's media player.
4. Any other media player that can play a link (DLNA and the like).

Pick the TV in the site's **Settings** → **TV**: **Default TV for everyone** is kept in
the add-on, **TV in this browser** overrides it for one phone or computer. With a single
TV in Home Assistant nothing needs picking. Samsung, LG and other TVs without Android TV:
a Google TV box (Chromecast with Google TV and the like) does the job.

## Status

Early version. The site opens from the sidebar (MIRTVONLINE) with no token: Home
Assistant has already checked who you are. Not yet done: the first-run wizard, the
weekly channel directory refresh.
