#!/usr/bin/env python

import logging
import sys

import semver
from external_resources_io.input import parse_model, read_input_from_file
from external_resources_io.terraform import (
    Action,
    Plan,
    ResourceChange,
    TerraformJsonPlanParser,
)

from er_aws_rds.input import AppInterfaceInput
from hooks.utils.aws_api import AWSApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("botocore")
logger.setLevel(logging.ERROR)


class RDSPlanValidator:
    """The plan validator class"""

    def __init__(self, plan: Plan, app_interface_input: AppInterfaceInput) -> None:
        self.plan = plan
        self.input = app_interface_input
        self.aws_api = AWSApi(
            config_options={"region_name": app_interface_input.data.region}
        )
        self.errors: list[str] = []

    @property
    def aws_db_instance_updates(self) -> list[ResourceChange]:
        "Gets the plan updates"
        return [
            c
            for c in self.plan.resource_changes
            if c.type == "aws_db_instance"
            and c.change
            and Action.ActionUpdate in c.change.actions
        ]

    @property
    def aws_db_instance_deletions(self) -> list[ResourceChange]:
        "Gets the plan updates"
        return [
            c
            for c in self.plan.resource_changes
            if c.type == "aws_db_instance"
            and c.change
            and Action.ActionDelete in c.change.actions
        ]

    def _validate_major_version_upgrade(self) -> None:
        for u in self.aws_db_instance_updates:
            if not u.change or not u.change.before or not u.change.after:
                continue
            current_version = u.change.before["engine_version"]
            desired_version = u.change.after["engine_version"]
            if current_version != desired_version:
                valid_update_versions = self.aws_api.get_rds_valid_update_versions(
                    u.change.before["engine"], current_version
                )
                if desired_version not in valid_update_versions:
                    self.errors.append(
                        "Engine version cannot be updated. "
                        f"Current_version: {current_version}, "
                        f"Desired_version: {desired_version}, "
                        f"Valid update versions: %{valid_update_versions}"
                    )

                # Major version upgrade validation
                semver_current_version = semver.Version.parse(
                    u.change.before["engine_version"], optional_minor_and_patch=True
                )
                semver_desired_version = semver.Version.parse(
                    u.change.after["engine_version"], optional_minor_and_patch=True
                )
                if (
                    semver_current_version.major != semver_desired_version.major
                    and not self.input.data.allow_major_version_upgrade
                ):
                    self.errors.append(
                        "To enable major version ugprades, allow_major_version_upgrade attribute must be set to True"
                    )

    def _validate_deletion_protection_not_enabled_on_destroy(self) -> None:
        for u in self.aws_db_instance_deletions:
            if not u.change or not u.change.before:
                continue
            if u.change.before.get("deletion_protection", False):
                self.errors.append(
                    "Deletion protection cannot be enabled on destroy. Disable deletion_protection first to remove the instance"
                )

    def validate(self) -> bool:
        """Validate method"""
        self._validate_major_version_upgrade()
        self._validate_deletion_protection_not_enabled_on_destroy()
        return not self.errors


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    app_interface_input: AppInterfaceInput = parse_model(
        AppInterfaceInput,
        read_input_from_file(),
    )

    logger.info("Running RDS terraform plan validation")
    parser = TerraformJsonPlanParser(plan_path=sys.argv[1])
    validator = RDSPlanValidator(parser.plan, app_interface_input)
    if not validator.validate():
        logger.error(validator.errors)
        sys.exit(1)
    else:
        logger.info("Validation ended succesfully")
        sys.exit(0)
