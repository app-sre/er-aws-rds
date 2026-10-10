FROM quay.io/redhat-services-prod/app-sre-tenant/er-base-terraform-main/er-base-terraform-main:0.6.0-21@sha256:bd4b2818cc9333901b56a67d1fbf552b98e54e7c46d08bc5f91d13728f2eaaaf AS base
# keep in sync with pyproject.toml
LABEL konflux.additional-tags="0.13.4"
COPY LICENSE /licenses/
ENV TERRAFORM_MODULE_SRC_DIR="./module"

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /bin/uv

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
