# The base image is fixed here on purpose. Newer Supervisor versions ignore build.yaml
# and pass BUILD_FROM=ghcr.io/home-assistant/base (Alpine without Python), so the
# Dockerfile must not take its base from that argument.
FROM docker.io/library/python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MIH_DATA_DIR=/data \
    MIH_BIND_HOST=0.0.0.0 \
    MIH_BIND_PORT=8765

# The engine lives in this repository (engine/), so the add-on needs nothing else
# from GitHub: pip only fetches the engine's dependencies from PyPI.
COPY engine/pyproject.toml engine/README.md /engine/
COPY engine/src /engine/src
RUN pip install --no-cache-dir /engine && rm -rf /engine

COPY mirtv_env.py mirtv_stdin.py /usr/local/lib/mirtv/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=amd64
# The add-on's version (Supervisor passes it on install and Update): the site's
# Settings and Status show it instead of the engine's own development number.
ENV MIRTV_VERSION="${BUILD_VERSION}"
LABEL io.hass.type="addon" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

CMD ["/run.sh"]
