"""MIRTVONLINE core (internal name MIH)."""

import os

# Inside the add-on: its version from config.yaml (the Dockerfile sets MIRTV_VERSION).
__version__ = os.environ.get("MIRTV_VERSION") or "0.1.0.dev0"
