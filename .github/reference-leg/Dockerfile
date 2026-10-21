# The CI reference leg (the `reference: true` entry of the `test` matrix in
# .github/workflows/ci.yml) as a container: Linux on x86_64, CPython
# installed by uv from python-build-standalone, as astral-sh/setup-uv does.
# Goldens are recorded there, and failures that only show on x86_64 Linux
# (a SQLAlchemy or greenlet build) reproduce here. Use it through run.sh.
FROM --platform=linux/amd64 ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git build-essential swi-prolog-nox graphviz \
 && rm -rf /var/lib/apt/lists/*

# CI installs the latest uv too (setup-uv without a version).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ARG PYTHON
ENV PYTHON=${PYTHON} \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_CACHE_DIR=/opt/uv-cache \
    UV_LINK_MODE=copy \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    HOME=/tmp/home
RUN uv python install "${PYTHON}" && chmod -R a+rX /opt/uv-python
WORKDIR /work
