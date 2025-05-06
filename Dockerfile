FROM quay.io/redhat-services-prod/app-sre-tenant/er-base-terraform-main/er-base-terraform-main:0.3.7-2@sha256:29fedfe932acd8be7b8abc1e6dea35f5e2f867fcb6c00e7bd25af5cc50836c09 AS base
# keep in sync with pyproject.toml
LABEL konflux.additional-tags="0.6.10"

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.7.2@sha256:3b898ca84fbe7628c5adcd836c1de78a0f1ded68344d019af8478d4358417399 /uv /bin/uv

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
