import logging
from collections.abc import Callable
from functools import cached_property
from typing import Any, Literal

from mypy_boto3_rds.type_defs import BlueGreenDeploymentTypeDef, DBInstanceTypeDef

from er_aws_rds.input import (
    AppInterfaceInput,
    BlueGreenDeployment,
)
from hooks.utils.aws_api import AWSApi
from hooks.utils.blue_green_deployment_model import BlueGreenDeploymentModel
from hooks.utils.models import (
    ActionType,
    CreateAction,
    DeleteAction,
    DeleteSourceDBInstanceAction,
    State,
    SwitchoverAction,
    WaitForAvailableAction,
    WaitForDeletedAction,
    WaitForSourceDBInstancesDeletedAction,
    WaitForSwitchoverCompletedAction,
)
from hooks.utils.wait import wait_for


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
        self.model: BlueGreenDeploymentModel | None = None

    def run(self) -> State:
        """Run Blue/Green Deployment Manager"""
        config = self.app_interface_input.data.blue_green_deployment
        if config is None or not config.enabled:
            self.logger.info("blue_green_deployment not enabled.")
            return State.NOT_ENABLED
        self.model = self._build_model(config)
        actions = self.model.plan_actions()
        if not actions:
            self.logger.info("No changes for Blue/Green Deployment.")
        for action in actions:
            self.logger.info(f"Action {action.type}: {action.model_dump_json()}")
            if not self.dry_run:
                handler = self._action_handlers[action.type]
                handler(action)
                self.model.state = action.next_state
        return self.model.state

    def _build_model(self, config: BlueGreenDeployment) -> BlueGreenDeploymentModel:
        db_instance_identifier = self.app_interface_input.provision.identifier
        db_instance = self.aws_api.get_db_instance(db_instance_identifier)
        valid_upgrade_targets = (
            self.aws_api.get_blue_green_deployment_valid_upgrade_targets(
                engine=db_instance["Engine"],
                version=db_instance["EngineVersion"],
            )
            if db_instance
            else {}
        )
        target_parameter_group_name = (
            config.target.parameter_group.name
            if config.target and config.target.parameter_group
            else None
        )
        target_db_parameter_group = (
            self.aws_api.get_db_parameter_group(target_parameter_group_name)
            if target_parameter_group_name
            else None
        )
        blue_green_deployment = self.aws_api.get_blue_green_deployment(
            db_instance_identifier
        )
        source_db_instances = self._fetch_source_db_instances(blue_green_deployment)
        target_db_instances = self._fetch_target_db_instances(blue_green_deployment)
        return BlueGreenDeploymentModel(
            db_instance_identifier=db_instance_identifier,
            state=State.INIT,
            config=config,
            db_instance=db_instance,
            valid_upgrade_targets=valid_upgrade_targets,
            target_db_parameter_group=target_db_parameter_group,
            blue_green_deployment=blue_green_deployment,
            source_db_instances=source_db_instances,
            target_db_instances=target_db_instances,
            tags=self.app_interface_input.data.tags,
        )

    def _fetch_blue_green_deployment_member_instances(
        self,
        blue_green_deployment: BlueGreenDeploymentTypeDef | None,
        key: Literal["SourceMember", "TargetMember"],
    ) -> list[DBInstanceTypeDef]:
        if blue_green_deployment is None:
            return []
        return list(
            filter(
                None,
                (
                    self.aws_api.get_db_instance(identifier)
                    for details in blue_green_deployment.get("SwitchoverDetails", [])
                    if (identifier := details.get(key))
                ),
            )
        )

    def _fetch_source_db_instances(
        self,
        blue_green_deployment: BlueGreenDeploymentTypeDef | None,
    ) -> list[DBInstanceTypeDef]:
        return self._fetch_blue_green_deployment_member_instances(
            blue_green_deployment, "SourceMember"
        )

    def _fetch_target_db_instances(
        self,
        blue_green_deployment: BlueGreenDeploymentTypeDef | None,
    ) -> list[DBInstanceTypeDef]:
        return self._fetch_blue_green_deployment_member_instances(
            blue_green_deployment, "TargetMember"
        )

    @cached_property
    def _action_handlers(self) -> dict[ActionType, Callable[[Any], None]]:
        return {
            ActionType.CREATE: self._handle_create,
            ActionType.WAIT_FOR_AVAILABLE: self._handle_wait_for_available,
            ActionType.SWITCHOVER: self._handle_switchover,
            ActionType.WAIT_FOR_SWITCHOVER_COMPLETED: self._handle_wait_for_switchover_completed,
            ActionType.DELETE_SOURCE_DB_INSTANCE: self._handle_delete_source_db_instance,
            ActionType.WAIT_FOR_SOURCE_DB_INSTANCES_DELETED: self._handle_wait_for_source_db_instances_deleted,
            ActionType.DELETE: self._handle_delete,
            ActionType.DELETE_WITHOUT_SWITCHOVER: self._handle_delete_without_switchover,
            ActionType.WAIT_FOR_DELETED: self._handle_wait_for_delete,
        }

    def _handle_create(self, action: CreateAction) -> None:
        self.aws_api.create_blue_green_deployment(action.payload)

    def _wait_for_available_condition(self) -> bool:
        assert self.model
        self.model.blue_green_deployment = self.aws_api.get_blue_green_deployment(
            self.model.db_instance_identifier
        )
        self.model.target_db_instances = self._fetch_target_db_instances(
            self.model.blue_green_deployment
        )
        return self.model.is_blue_green_deployment_available()

    def _handle_wait_for_available(self, _: WaitForAvailableAction) -> None:
        wait_for(self._wait_for_available_condition, logger=self.logger)

    def _handle_switchover(self, _: SwitchoverAction) -> None:
        assert self.model
        assert self.model.blue_green_deployment
        identifier = self.model.blue_green_deployment["BlueGreenDeploymentIdentifier"]
        self.aws_api.switchover_blue_green_deployment(identifier)

    def _wait_for_switchover_completed_condition(self) -> bool:
        assert self.model
        assert self.model.db_instance_identifier
        self.model.blue_green_deployment = self.aws_api.get_blue_green_deployment(
            self.model.db_instance_identifier
        )
        return (
            self.model.blue_green_deployment is not None
            and self.model.blue_green_deployment["Status"] == "SWITCHOVER_COMPLETED"
        )

    def _handle_wait_for_switchover_completed(
        self, _: WaitForSwitchoverCompletedAction
    ) -> None:
        wait_for(self._wait_for_switchover_completed_condition, logger=self.logger)

    def _handle_delete_source_db_instance(
        self, _: DeleteSourceDBInstanceAction
    ) -> None:
        assert self.model
        self.model.source_db_instances = self._fetch_source_db_instances(
            self.model.blue_green_deployment
        )
        for instance in self.model.source_db_instances:
            self.aws_api.delete_db_instance(instance["DBInstanceIdentifier"])

    def _wait_for_source_db_instances_deleted_condition(self) -> bool:
        assert self.model
        self.model.source_db_instances = self._fetch_source_db_instances(
            self.model.blue_green_deployment
        )
        return len(self.model.source_db_instances) == 0

    def _handle_wait_for_source_db_instances_deleted(
        self, _: WaitForSourceDBInstancesDeletedAction
    ) -> None:
        wait_for(
            self._wait_for_source_db_instances_deleted_condition, logger=self.logger
        )

    def _handle_delete(self, _: DeleteAction) -> None:
        assert self.model
        assert self.model.blue_green_deployment
        identifier = self.model.blue_green_deployment["BlueGreenDeploymentIdentifier"]
        self.aws_api.delete_blue_green_deployment(identifier)

    def _handle_delete_without_switchover(self, _: DeleteAction) -> None:
        assert self.model
        assert self.model.blue_green_deployment
        identifier = self.model.blue_green_deployment["BlueGreenDeploymentIdentifier"]
        self.aws_api.delete_blue_green_deployment(identifier, delete_target=True)

    def _wait_for_delete_condition_condition(self) -> bool:
        assert self.model
        self.model.blue_green_deployment = self.aws_api.get_blue_green_deployment(
            self.model.db_instance_identifier
        )
        return self.model.blue_green_deployment is None

    def _handle_wait_for_delete(self, _: WaitForDeletedAction) -> None:
        wait_for(self._wait_for_delete_condition_condition, logger=self.logger)
