from collections.abc import Callable
from functools import cached_property
from typing import Self

from mypy_boto3_rds.type_defs import (
    BlueGreenDeploymentTypeDef,
    DBInstanceTypeDef,
    DBParameterGroupTypeDef,
)
from pydantic import BaseModel, model_validator

from er_aws_rds.input import BlueGreenDeployment, BlueGreenDeploymentTarget
from hooks.utils.models import (
    ActionType,
    BaseAction,
    CreateAction,
    CreateBlueGreenDeploymentParams,
    DeleteAction,
    DeleteSourceDBInstanceAction,
    DeleteWithoutSwitchoverAction,
    NoOpAction,
    State,
    SwitchoverAction,
    WaitForAvailableAction,
    WaitForDeletedAction,
    WaitForSourceDBInstancesDeletedAction,
    WaitForSwitchoverCompletedAction,
)


class BlueGreenDeploymentModel(BaseModel):
    state: State
    db_instance_identifier: str
    config: BlueGreenDeployment
    db_instance: DBInstanceTypeDef | None = None
    target_db_parameter_group: DBParameterGroupTypeDef | None = None
    blue_green_deployment: BlueGreenDeploymentTypeDef | None = None
    source_db_instances: list[DBInstanceTypeDef] = []
    tags: dict[str, str] | None = None

    @model_validator(mode="after")
    def _init_state(self) -> Self:
        if self.blue_green_deployment is None:
            self.state = State.INIT
            return self
        match self.blue_green_deployment["Status"]:
            case "PROVISIONING":
                self.state = State.PROVISIONING
            case "AVAILABLE":
                self.state = State.AVAILABLE
            case "SWITCHOVER_IN_PROGRESS":
                self.state = State.SWITCHOVER_IN_PROGRESS
            case "SWITCHOVER_COMPLETED":
                if not self.source_db_instances:
                    self.state = State.SOURCE_DB_INSTANCES_DELETED
                elif any(
                    db["DBInstanceStatus"] == "deleting"
                    for db in self.source_db_instances
                ):
                    self.state = State.DELETING_SOURCE_DB_INSTANCES
                else:
                    self.state = State.SWITCHOVER_COMPLETED
            case "DELETING":
                self.state = State.DELETING
            case _ as status:
                raise ValueError(f"Unexpected Blue/Green Deployment status: {status}")
        return self

    @model_validator(mode="after")
    def _validate_db_instance_exist(self) -> Self:
        if self.db_instance is None:
            raise ValueError(f"DB Instance not found: {self.db_instance_identifier}")
        return self

    @model_validator(mode="after")
    def _validate_target_parameter_group(self) -> Self:
        if (
            self.config.target
            and self.config.target.parameter_group
            and (parameter_group_name := self.config.target.parameter_group.name)
            and self.target_db_parameter_group is None
        ):
            raise ValueError(
                f"Target Parameter Group not found: {parameter_group_name}"
            )
        return self

    def plan_actions(self) -> list[BaseAction]:
        """Plan Actions"""
        state = self.state
        actions = []
        while state != State.NO_OP:
            routing_func, allowed_next_states = self._state_graph[state]
            action = routing_func()
            next_state = action.next_state
            if next_state not in allowed_next_states:
                raise ValueError(f"Invalid next state: {next_state} for state: {state}")
            if action.type != ActionType.NO_OP:
                actions.append(action)
            state = next_state
        return actions

    def _no_changes(self) -> bool:
        target = self.config.target or BlueGreenDeploymentTarget()
        parameter_group_name = (
            target.parameter_group.name if target.parameter_group else None
        )
        desired_instance = {
            "parameter_group_name": parameter_group_name,
            "iops": target.iops,
            "engine_version": target.engine_version,
            "instance_class": target.instance_class,
            "storage_throughput": target.storage_throughput,
            "storage_type": target.storage_type,
            "allocated_storage": target.allocated_storage,
        }
        assert self.db_instance
        current_instance = {
            "parameter_group_name": self.db_instance["DBParameterGroups"][0][
                "DBParameterGroupName"
            ],
            "iops": self.db_instance["Iops"],
            "engine_version": self.db_instance["EngineVersion"],
            "instance_class": self.db_instance["DBInstanceClass"],
            "storage_throughput": self.db_instance["StorageThroughput"],
            "storage_type": self.db_instance["StorageType"],
            "allocated_storage": self.db_instance["AllocatedStorage"],
        }
        return all(
            value == current_instance[key]
            for key, value in desired_instance.items()
            if value is not None
        )

    @cached_property
    def _state_graph(self) -> dict[State, tuple[Callable[[], BaseAction], list[State]]]:
        return {
            State.INIT: (
                self._route_init,
                [State.NO_OP, State.PROVISIONING],
            ),
            State.PROVISIONING: (
                self._route_provisioning,
                [State.AVAILABLE],
            ),
            State.AVAILABLE: (
                self._route_available,
                [State.SWITCHOVER_IN_PROGRESS, State.DELETING, State.NO_OP],
            ),
            State.SWITCHOVER_IN_PROGRESS: (
                self._route_switchover_in_progress,
                [State.SWITCHOVER_COMPLETED],
            ),
            State.SWITCHOVER_COMPLETED: (
                self._route_switchover_completed,
                [State.DELETING_SOURCE_DB_INSTANCES, State.NO_OP],
            ),
            State.DELETING_SOURCE_DB_INSTANCES: (
                self._route_deleting_source_db_instances,
                [State.SOURCE_DB_INSTANCES_DELETED],
            ),
            State.SOURCE_DB_INSTANCES_DELETED: (
                self._route_source_db_instances_deleted,
                [State.DELETING],
            ),
            State.DELETING: (
                self._route_deleting,
                [State.NO_OP],
            ),
        }

    def _route_init(self) -> BaseAction:
        target = self.config.target or BlueGreenDeploymentTarget()
        parameter_group_name = (
            target.parameter_group.name if target.parameter_group else None
        )
        if self.config.delete and (not self.config.switchover or self._no_changes()):
            return NoOpAction(next_state=State.NO_OP)
        assert self.db_instance
        return CreateAction(
            type=ActionType.CREATE,
            payload=CreateBlueGreenDeploymentParams(
                name=self.db_instance_identifier,
                source_arn=self.db_instance["DBInstanceArn"],
                allocated_storage=target.allocated_storage,
                engine_version=target.engine_version,
                instance_class=target.instance_class,
                iops=target.iops,
                parameter_group_name=parameter_group_name,
                storage_throughput=target.storage_throughput,
                storage_type=target.storage_type,
                tags=self.tags,
            ),
            next_state=State.PROVISIONING,
        )

    @staticmethod
    def _route_provisioning() -> BaseAction:
        return WaitForAvailableAction(
            type=ActionType.WAIT_FOR_AVAILABLE,
            next_state=State.AVAILABLE,
        )

    def _route_available(self) -> BaseAction:
        if self.config.switchover:
            return SwitchoverAction(
                type=ActionType.SWITCHOVER,
                next_state=State.SWITCHOVER_IN_PROGRESS,
            )
        if self.config.delete:
            return DeleteWithoutSwitchoverAction(
                type=ActionType.DELETE_WITHOUT_SWITCHOVER,
                next_state=State.DELETING,
            )
        return NoOpAction(
            type=ActionType.NO_OP,
            next_state=State.NO_OP,
        )

    @staticmethod
    def _route_switchover_in_progress() -> BaseAction:
        return WaitForSwitchoverCompletedAction(
            type=ActionType.WAIT_FOR_SWITCHOVER_COMPLETED,
            next_state=State.SWITCHOVER_COMPLETED,
        )

    def _route_switchover_completed(self) -> BaseAction:
        if self.config.delete:
            return DeleteSourceDBInstanceAction(
                type=ActionType.DELETE_SOURCE_DB_INSTANCE,
                next_state=State.DELETING_SOURCE_DB_INSTANCES,
            )
        return NoOpAction(
            type=ActionType.NO_OP,
            next_state=State.NO_OP,
        )

    @staticmethod
    def _route_deleting_source_db_instances() -> BaseAction:
        return WaitForSourceDBInstancesDeletedAction(
            type=ActionType.WAIT_FOR_SOURCE_DB_INSTANCES_DELETED,
            next_state=State.SOURCE_DB_INSTANCES_DELETED,
        )

    @staticmethod
    def _route_source_db_instances_deleted() -> BaseAction:
        return DeleteAction(
            type=ActionType.DELETE,
            next_state=State.DELETING,
        )

    @staticmethod
    def _route_deleting() -> BaseAction:
        return WaitForDeletedAction(
            type=ActionType.WAIT_FOR_DELETED,
            next_state=State.NO_OP,
        )
