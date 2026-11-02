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

## Status

Early version. The site opens from the sidebar (MIRTVONLINE) with no token: Home
Assistant has already checked who you are. Not yet done: a light mode for weak boxes,
launch on a TV, the first-run wizard.
