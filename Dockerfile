FROM quay.io/redhat-services-prod/app-sre-tenant/er-base-terraform-main/er-base-terraform-main:0.3.8-1@sha256:2a70bb36c8da671a792359a77162800a8d3f807864d9e75cd04f4f87d55871b6 AS base
# keep in sync with pyproject.toml
LABEL konflux.additional-tags="0.6.10"

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.7.6@sha256:c467e9b5da1e763ee5841f9ae51020d11569ca08991a05367ceca6eda0be9b16 /uv /bin/uv

# Python and UV related variables
ENV \
    # compile bytecode for faster startup
    UV_COMPILE_BYTECODE="true" \
    # disable uv cache. it doesn't make sense in a container
    UV_NO_CACHE=true \
    UV_NO_PROGRESS=true \
    VIRTUAL_ENV="${APP}/.venv" \
    PATH="${APP}/.venv/bin:${PATH}" \
    TERRAFORM_MODULE_SRC_DIR="${APP}/module"

COPY pyproject.toml uv.lock ./
# Test lock file is up to date
RUN uv lock --locked
# Install dependencies
RUN uv sync --frozen --no-group dev --no-install-project --python /usr/bin/python3

# the source code
COPY README.md  ./
COPY hooks ./hooks
COPY er_aws_rds ./er_aws_rds
# Sync the project
RUN uv sync --frozen --no-group dev

COPY module ./module

# Get the terraform providers
RUN terraform-provider-sync

FROM builder AS test
# install test dependencies
RUN uv sync --frozen

COPY Makefile ./
COPY tests ./tests

RUN make test

FROM base AS prod
# get terraform providers
COPY --from=builder ${TF_PLUGIN_CACHE_DIR} ${TF_PLUGIN_CACHE_DIR}
# get our app with the dependencies
COPY --from=builder ${APP} ${APP}

ENV \
    VIRTUAL_ENV="${APP}/.venv" \
    PATH="${APP}/.venv/bin:${PATH}"
