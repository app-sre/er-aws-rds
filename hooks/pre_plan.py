#!/usr/bin/env python

import logging
import subprocess
from collections.abc import Iterable
from subprocess import CompletedProcess

from hooks.utils.envvars import RuntimeEnvVars
from hooks.utils.logger import setup_logging
from hooks.utils.runtime import is_dry_run


def run_process(cmd: Iterable[str], *, dry_run: bool = True) -> CompletedProcess | None:
    """Runs a subprocess"""
    if dry_run:
        logger.debug(f"cmd: {' '.join(cmd)}")
        return None

    try:
        return subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.exception(e.stderr)  # Prints error output
    return None


def rename_resource(src: str, dest: str) -> None:
    """Renames a resource in the state"""
    logger.info(f"Renaming state resource: {src} --> {dest}")
    run_process([*terraform_cmd, "state", "mv", src, dest], dry_run=is_dry_run())


def refresh_state() -> None:
    """Refreshes the terraform state"""
    logger.info("Refreshing the state")
    run_process(
        [
            *terraform_cmd,
            "apply",
            f"--var-file={terraform_vars_file}",
            "--refresh-only",
            "-auto-approve",
        ],
        dry_run=is_dry_run(),
    )


def mv_state_items(state_items: Iterable[str]) -> int:
    """Renames the state items to the new approach."""
    count = 0
    for item in state_items:
        parts = item.split(".")
        type_, *_, name = parts
        if type_ == "data" or name.startswith("this"):
            continue
        new_item = (
            f'{type_}.this["{name}"]'
            if type_ == "aws_db_parameter_group"
            else f"{type_}.this"
        )
        rename_resource(item, new_item)
        count += 1
    return count


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)

    RuntimeEnvVars.check([RuntimeEnvVars.TERRAFORM_CMD, RuntimeEnvVars.TF_VARS_FILE])

    terraform_cmd = (RuntimeEnvVars.TERRAFORM_CMD.get() or "").split()
    terraform_vars_file = RuntimeEnvVars.TF_VARS_FILE.get()

    logger.info("Running Migration Process CDKTF -> Terraform")
    result = run_process([*terraform_cmd, "state", "list"], dry_run=False)
    if result:
        state_items = result.stdout.split()
        count = mv_state_items(state_items)
        if count > 0:
            refresh_state()
