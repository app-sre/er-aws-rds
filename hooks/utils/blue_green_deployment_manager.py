import logging

from er_aws_rds.input import AppInterfaceInput
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

        instance = self.aws_api.get_db_instance(
            self.app_interface_input.provision.identifier
        )
        if instance is None:
            raise ValueError(
                f"DB instance not found: {self.app_interface_input.provision.identifier}"
            )

        params = CreateBlueGreenDeploymentParams(
            name=self.app_interface_input.provision.identifier,
            source_arn=instance["DBInstanceArn"],
            allocated_storage=config.target.allocated_storage,
            engine_version=config.target.engine_version,
            instance_class=config.target.instance_class,
            iops=config.target.iops,
            parameter_group_name=config.target.parameter_group.computed_pg_name,
            storage_throughput=config.target.storage_throughput,
            storage_type=config.target.storage_type,
            tags=self.app_interface_input.data.tags,
        )

        self.logger.info(
            f"Action: CreateBlueGreenDeployment, {params.model_dump_json()}"
        )
        if not self.dry_run:
            self.aws_api.create_blue_green_deployment(params)
