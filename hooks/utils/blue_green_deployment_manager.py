import logging

from er_aws_rds.input import AppInterfaceInput, BlueGreenDeploymentTarget
from hooks.utils.aws_api import AWSApi
from hooks.utils.models import CreateBlueGreenDeploymentParams


class BlueGreenDeploymentManager:
    """Blue/Green Deployment Manager"""

    def __init__(
        self,
        aws_api: AWSApi,
        app_interface_input: AppInterfaceInput,
        *,
        dry_run: bool,
    ) -> None:
        """Init"""
        self.aws_api = aws_api
        self.app_interface_input = app_interface_input
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)

    def run(self) -> None:
        """Manage Blue/Green Deployment"""
        config = self.app_interface_input.data.blue_green_deployment
        if config is None or not config.enabled:
            self.logger.info(
                "Blue/Green Deployment not enabled, continue to normal flow."
            )
            return

        identifier = self.app_interface_input.provision.identifier
        instance = self.aws_api.get_db_instance(identifier)
        if instance is None:
            raise ValueError(
                f"DB instance not found: {self.app_interface_input.provision.identifier}"
            )

        bg = self.aws_api.get_blue_green_deployment(identifier)
        if bg:
            self.logger.info(
                f"Blue/Green Deployment {identifier} Status: {bg['Status']}"
            )
            return

        target = config.target or BlueGreenDeploymentTarget()
        parameter_group_name = (
            target.parameter_group.name if target.parameter_group else None
        )
        if (
            parameter_group_name
            and self.aws_api.get_db_parameter_group(parameter_group_name) is None
        ):
            raise ValueError(
                f"Target Parameter Group not found: {parameter_group_name}"
            )

        params = CreateBlueGreenDeploymentParams(
            name=identifier,
            source_arn=instance["DBInstanceArn"],
            allocated_storage=target.allocated_storage,
            engine_version=target.engine_version,
            instance_class=target.instance_class,
            iops=target.iops,
            parameter_group_name=parameter_group_name,
            storage_throughput=target.storage_throughput,
            storage_type=target.storage_type,
            tags=self.app_interface_input.data.tags,
        )

        self.logger.info(
            f"Action: CreateBlueGreenDeployment, {params.model_dump(by_alias=True, exclude_none=True)}"
        )
        if not self.dry_run:
            self.aws_api.create_blue_green_deployment(params)
