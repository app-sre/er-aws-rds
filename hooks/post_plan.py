#!/usr/bin/env python
import logging
import sys

import semver
from external_resources_io.input import parse_model, read_input_from_file
from external_resources_io.terraform import (
    Action,
    Change,
    Plan,
    ResourceChange,
    TerraformJsonPlanParser,
)

from er_aws_rds.input import AppInterfaceInput
from hooks.utils.aws_api import AWSApi
from hooks.utils.envvars import RuntimeEnvVars
from hooks.utils.logger import setup_logging


class RDSPlanValidator:
    """The plan validator class"""

    def __init__(self, plan: Plan, app_interface_input: AppInterfaceInput) -> None:
        self.plan = plan
        self.input = app_interface_input
        self.aws_api = AWSApi(region_name=app_interface_input.data.region)
        self.errors: list[str] = []

    @property
    def output_deletions(self) -> list[Change]:
        return [
            c
            for c in self.plan.output_changes.values()
            if Action.ActionDelete in c.actions
        ]

    @property
    def output_creations(self) -> list[Change]:
        return [
            c
            for c in self.plan.output_changes.values()
            if Action.ActionCreate in c.actions
        ]

    @property
    def resource_updates(self) -> list[ResourceChange]:
        return [
            c
            for c in self.plan.resource_changes
            if c.change and Action.ActionUpdate in c.change.actions
        ]

    @property
    def resource_deletions(self) -> list[ResourceChange]:
        return [
            c
            for c in self.plan.resource_changes
            if c.change and Action.ActionDelete in c.change.actions
        ]

    @property
    def resource_creations(self) -> list[ResourceChange]:
        return [
            c
            for c in self.plan.resource_changes
            if c.change and Action.ActionCreate in c.change.actions
        ]

    @property
    def aws_db_instance_creations(self) -> list[ResourceChange]:
        "Gets the RDS isntance creations"
        return [c for c in self.resource_creations if c.type == "aws_db_instance"]

    @property
    def aws_db_instance_updates(self) -> list[ResourceChange]:
        "Gets the RDS isntance updates"
        return [c for c in self.resource_updates if c.type == "aws_db_instance"]

    @property
    def aws_db_instance_deletions(self) -> list[ResourceChange]:
        "Gets the RDS instance deletions"
        return [c for c in self.resource_deletions if c.type == "aws_db_instance"]

    def _validate_version_on_create(self) -> None:
        """Validates the RDS instance desired version (new instance)"""
        for u in self.aws_db_instance_creations:
            if not u.change or not u.change.after:
                continue
            engine = self.input.data.engine
            version = u.change.after["engine_version"]
            if not self.aws_api.is_rds_engine_version_available(
                engine=engine, version=version
            ):
                self.errors.append(f"{engine} version {version} is not available.")

    def _validate_version_upgrade(self) -> None:
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
                        f"Valid update versions: {valid_update_versions}"
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

    def _validate_resource_renaming(self) -> None:
        # This validation was used to migrate resources from CDKTF to HCL
        if (
            len(self.resource_deletions) != 0
            and len(self.resource_creations) != 0
            and any([
                (len(self.resource_creations) != len(self.resource_deletions)),
                (len(self.output_creations) != len(self.output_deletions)),
            ])
        ):
            self.errors.append("Deletions and Creations mismatch")

    def validate(self) -> bool:
        """Validate method"""
        self._validate_version_on_create()
        self._validate_version_upgrade()
        self._validate_deletion_protection_not_enabled_on_destroy()
        return not self.errors


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)

    RuntimeEnvVars.check([RuntimeEnvVars.PLAN_FILE_JSON])
    terraform_plan_json = RuntimeEnvVars.PLAN_FILE_JSON.get() or ""

    app_interface_input: AppInterfaceInput = parse_model(
        AppInterfaceInput,
        read_input_from_file(),
    )

    logger.info("Running RDS terraform plan validation")
    parser = TerraformJsonPlanParser(plan_path=terraform_plan_json)
    validator = RDSPlanValidator(parser.plan, app_interface_input)
    if not validator.validate():
        logger.error(validator.errors)
        sys.exit(1)
    else:
        logger.info("Validation ended succesfully")
        sys.exit(0)
