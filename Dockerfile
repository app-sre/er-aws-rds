FROM quay.io/redhat-services-prod/app-sre-tenant/er-base-cdktf-main/er-base-cdktf-main:cdktf-0.20.11-tf-1.6.6-py-3.12-v0.6.0-1@sha256:cbd7d366bd573c7346956083fe94f3145198be0630744d30bea3271925fcfe9a AS base
# keep in sync with pyproject.toml
LABEL konflux.additional-tags="0.3.1"

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5.25@sha256:a73176b27709bff700a1e3af498981f31a83f27552116f21ae8371445f0be710 /uv /bin/uv

# Python and UV related variables
ENV \
    # compile bytecode for faster startup
    UV_COMPILE_BYTECODE="true" \
    # disable uv cache. it doesn't make sense in a container
    UV_NO_CACHE=true \
    UV_NO_PROGRESS=true \
    VIRTUAL_ENV="${APP}/.venv" \
    PATH="${APP}/.venv/bin:${PATH}"

COPY cdktf.json pyproject.toml uv.lock ./
# Test lock file is up to date
RUN uv lock --locked
# Install dependencies
RUN uv sync --frozen --no-group dev --no-install-project --python /usr/bin/python3
# Download all necessary terraform providers
RUN cdktf-provider-sync

# the source code
COPY README.md  ./
COPY hooks ./hooks
COPY er_aws_rds ./er_aws_rds
# Sync the project
RUN uv sync --frozen --no-group dev

FROM builder as test
# install test dependencies
RUN uv sync --frozen

COPY Makefile ./
COPY tests ./tests
# Empty $JSII_RUNTIME_PACKAGE_CACHE_ROOT (/tmp/jsii-runtime-cache) again because the test stage created files there,
# and we want to run this test image in the dev environment, requires files owned by a random uid
RUN make test && rm -rf "$JSII_RUNTIME_PACKAGE_CACHE_ROOT"

FROM base AS prod
# get cdktf providers
COPY --from=builder ${TF_PLUGIN_CACHE_DIR} ${TF_PLUGIN_CACHE_DIR}
# get our app with the dependencies
COPY --from=builder ${APP} ${APP}

ENV \
    VIRTUAL_ENV="${APP}/.venv" \
    PATH="${APP}/.venv/bin:${PATH}"
