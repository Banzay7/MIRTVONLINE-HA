ARG BUILD_FROM=python:3.12-slim-bookworm
FROM ${BUILD_FROM}

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

COPY mirtv_env.py /usr/local/lib/mirtv/mirtv_env.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=amd64
LABEL io.hass.type="addon" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

CMD ["/run.sh"]
