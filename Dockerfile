FROM quay.io/redhat-services-prod/app-sre-tenant/er-base-terraform-main/er-base-terraform-main:0.6.0-6@sha256:d8b77d6253a9938040f5d7c7172f2d1b58773db2a1a9c618a1fb88d5e32ac850 AS base
# keep in sync with pyproject.toml
LABEL konflux.additional-tags="0.13.0"
COPY LICENSE /licenses/
ENV TERRAFORM_MODULE_SRC_DIR="./module"

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.22@sha256:16b63af0e7342dd372da9ca989ea9fa542fc68f4640972d59a8450a5240fe42e /uv /bin/uv

COPY pyproject.toml uv.lock ./
# Test lock file is up to date
RUN uv lock --locked
# Install dependencies
RUN uv sync --frozen --no-group dev --no-install-project

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
COPY --from=builder ${APP_ROOT} ${APP_ROOT}
