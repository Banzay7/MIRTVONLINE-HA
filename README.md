# MIRTVONLINE for Home Assistant

Home Assistant add-on: a catalog, TV guide and search for live TV channels from your
own and public playlists, with the web UI in the sidebar.

The add-on is self-contained: its engine lives in `mirtvonline/engine`, and Home Assistant
builds the image from this repository on install and on **Update**.

Needs Home Assistant OS or Supervised. Architectures: aarch64, amd64.

## Install from this (private) repository

1. On GitHub create a fine-grained token: **Settings** → **Developer settings** →
   **Personal access tokens** → **Fine-grained tokens** → **Generate new token**;
   repository access: only this repository; permission **Contents: Read-only**.
2. In Home Assistant: **Settings** → **Apps** (Add-ons) → **Install app** (Add-on Store) →
   menu ⋮ → **Repositories**, add
   `https://<github-user>:<token>@github.com/Banzay7/MIRTVONLINE-HA`.
3. Open **MIRTVONLINE** → **Install** → turn on **Show in sidebar**, keep
   **Auto update** off → **Start**.

Without a token: copy the `mirtvonline` folder into `/addons` on the Home Assistant box
(Samba or SSH app); it shows up under **Local apps**.

## Development

    pip install -r requirements-dev.txt && pytest tests
    cd mirtvonline/engine && pip install -e '.[dev]' && pytest tests

License: AGPL-3.0-only.
