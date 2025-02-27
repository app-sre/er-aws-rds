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

        rds_identifier = self.app_interface_input.provision.identifier
        instance = self.aws_api.get_db_instance(rds_identifier)
        if instance is None:
            raise ValueError(
                f"DB instance not found: {self.app_interface_input.provision.identifier}"
            )

        bg_name = rds_identifier
        bg = self.aws_api.get_blue_green_deployment(bg_name)
        if bg:
            bg_identifier = bg["BlueGreenDeploymentIdentifier"]
            if config.switchover:
                match bg["Status"]:
                    case "AVAILABLE":
                        self.logger.info(
                            f"Action: SwitchoverBlueGreenDeployment, name: {bg_name}, identifier: {bg_identifier}"
                        )
                        if not self.dry_run:
                            self.aws_api.switchover_blue_green_deployment(bg_identifier)
                        return
                    case "SWITCHOVER_COMPLETED":
                        if config.delete:
                            to_delete_instances = [
                                instance
                                for details in bg["SwitchoverDetails"]
                                if (instance := self.aws_api.get_db_instance(details["SourceMember"]))
                                and instance["DBInstanceStatus"] == "available"
                            ]
                            if to_delete_instances:
                                for instance in to_delete_instances:
                                    identifier = instance["DBInstanceIdentifier"]
                                    self.logger.info(f"Action: DeleteSourceDBInstance, identifier: {identifier}")
                                    if not self.dry_run:
                                        self.aws_api.delete_db_instance(identifier)
                            self.logger.info(f"Action: DeleteBlueGreenDeployment, name: {bg_name}, identifier: {bg_identifier}")
                            if not to_delete_instances and not self.dry_run:
                                self.aws_api.delete_blue_green_deployment(bg_identifier)
                            return
                    case _:
                        pass
            elif config.delete and bg["Status"] == "AVAILABLE":
                self.logger.info(f"Action: DeleteBlueGreenDeployment, name: {bg_name}, identifier: {bg_identifier}")
                if not self.dry_run:
                    self.aws_api.delete_blue_green_deployment(bg_identifier, delete_target=True)
                return
            self.logger.info(
                f"Blue/Green Deployment {bg_name} Status: {bg['Status']}"
            )
            return

        target = config.target or BlueGreenDeploymentTarget()
        parameter_group_name = (
            target.parameter_group.name if target.parameter_group else None
        )
        if (
            config.delete
            and (parameter_group_name is None or parameter_group_name == instance["DBParameterGroups"][0]["DBParameterGroupName"])
            and (target.iops is None or target.iops == instance["Iops"])
            and (target.engine_version is None or target.engine_version == instance["EngineVersion"])
            and (target.instance_class is None or target.instance_class == instance["DBInstanceClass"])
            and (target.storage_throughput is None or target.storage_throughput == instance["StorageThroughput"])
            and (target.storage_type is None or target.storage_type == instance["StorageType"])
            and (target.allocated_storage is None or target.allocated_storage == instance["AllocatedStorage"])
        ):
            self.logger.info("No changes for Blue/Green Deployment, continue to normal flow.")
            return
        if (
            parameter_group_name
            and self.aws_api.get_db_parameter_group(parameter_group_name) is None
        ):
            raise ValueError(
                f"Target Parameter Group not found: {parameter_group_name}"
            )

        params = CreateBlueGreenDeploymentParams(
            name=rds_identifier,
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
