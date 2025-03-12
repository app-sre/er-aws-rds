from collections.abc import Callable
from functools import cached_property
from typing import Self

from mypy_boto3_rds.type_defs import (
    BlueGreenDeploymentTypeDef,
    DBInstanceTypeDef,
    DBParameterGroupTypeDef,
    UpgradeTargetTypeDef,
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
    target_db_instances: list[DBInstanceTypeDef] = []
    tags: dict[str, str] | None = None
    valid_upgrade_targets: dict[str, UpgradeTargetTypeDef] = {}

    @model_validator(mode="after")
    def _init_state(self) -> Self:
        if self.blue_green_deployment is None:
            self.state = State.INIT
            return self
        match self.blue_green_deployment["Status"]:
            case "PROVISIONING":
                self.state = State.PROVISIONING
            case "AVAILABLE":
                self.state = (
                    State.AVAILABLE
                    if self.is_blue_green_deployment_available()
                    else State.PROVISIONING
                )
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

    @model_validator(mode="after")
    def _validate_deletion_protection(self) -> Self:
        if self.db_instance and self.db_instance["DeletionProtection"]:
            raise ValueError("deletion_protection must be disabled")
        return self

    @model_validator(mode="after")
    def _validate_backup_retention_period(self) -> Self:
        if self.db_instance and self.db_instance["BackupRetentionPeriod"] <= 0:
            raise ValueError("backup_retention_period must be greater than 0")
        return self

    @model_validator(mode="after")
    def _validate_version_upgrade(self) -> Self:
        assert self.db_instance
        target_engine_version = (
            self.config.target.engine_version
            if self.config.target and self.config.target.engine_version
            else self.db_instance["EngineVersion"]
        )
        if target_engine_version not in self.valid_upgrade_targets:
            valid_versions = ", ".join(self.valid_upgrade_targets)
            raise ValueError(
                f"target engine_version {target_engine_version} is not valid, valid versions: {valid_versions}"
            )
        return self

    def plan_actions(self) -> list[BaseAction]:
        """Plan Actions"""
        state = self.state
        actions = []
        while state != State.NO_OP:
            routing_func, allowed_next_states = self._state_graph[state]
            action = routing_func()
            if action is None:
                break
            next_state = action.next_state
            if next_state not in allowed_next_states:
                raise ValueError(f"Invalid next state: {next_state} for state: {state}")
            if action.type != ActionType.NO_OP:
                actions.append(action)
            state = next_state
        return actions

    def is_blue_green_deployment_available(self) -> bool:
        """Check if Blue/Green Deployment is available"""
        return (
            self.blue_green_deployment is not None
            and self.blue_green_deployment["Status"] == "AVAILABLE"
            and all(
                db["DBInstanceStatus"] == "available" for db in self.target_db_instances
            )
        )

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
    def _state_graph(
        self,
    ) -> dict[State, tuple[Callable[[], BaseAction | None], list[State]]]:
        """
        State graph

        mermaid graph is:

        flowchart TD
            START --> INIT
            INIT --> NO_OP
            INIT --> PROVISIONING
            PROVISIONING --> AVAILABLE
            AVAILABLE --> SWITCHOVER_IN_PROGRESS
            AVAILABLE --> DELETING
            SWITCHOVER_IN_PROGRESS --> SWITCHOVER_COMPLETED
            SWITCHOVER_COMPLETED --> DELETING_SOURCE_DB_INSTANCES
            DELETING_SOURCE_DB_INSTANCES --> SOURCE_DB_INSTANCES_DELETED
            SOURCE_DB_INSTANCES_DELETED --> DELETING
            DELETING --> NO_OP
            NO_OP --> END
            AVAILABLE --> END
            SWITCHOVER_COMPLETED --> END
        """
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
                [State.SWITCHOVER_IN_PROGRESS, State.DELETING],
            ),
            State.SWITCHOVER_IN_PROGRESS: (
                self._route_switchover_in_progress,
                [State.SWITCHOVER_COMPLETED],
            ),
            State.SWITCHOVER_COMPLETED: (
                self._route_switchover_completed,
                [State.DELETING_SOURCE_DB_INSTANCES],
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

    def _route_init(self) -> BaseAction | None:
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
    def _route_provisioning() -> BaseAction | None:
        return WaitForAvailableAction(
            type=ActionType.WAIT_FOR_AVAILABLE,
            next_state=State.AVAILABLE,
        )

    def _route_available(self) -> BaseAction | None:
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
        return None

    @staticmethod
    def _route_switchover_in_progress() -> BaseAction | None:
        return WaitForSwitchoverCompletedAction(
            type=ActionType.WAIT_FOR_SWITCHOVER_COMPLETED,
            next_state=State.SWITCHOVER_COMPLETED,
        )

    def _route_switchover_completed(self) -> BaseAction | None:
        if self.config.delete:
            return DeleteSourceDBInstanceAction(
                type=ActionType.DELETE_SOURCE_DB_INSTANCE,
                next_state=State.DELETING_SOURCE_DB_INSTANCES,
            )
        return None

    @staticmethod
    def _route_deleting_source_db_instances() -> BaseAction | None:
        return WaitForSourceDBInstancesDeletedAction(
            type=ActionType.WAIT_FOR_SOURCE_DB_INSTANCES_DELETED,
            next_state=State.SOURCE_DB_INSTANCES_DELETED,
        )

    @staticmethod
    def _route_source_db_instances_deleted() -> BaseAction | None:
        return DeleteAction(
            type=ActionType.DELETE,
            next_state=State.DELETING,
        )

    @staticmethod
    def _route_deleting() -> BaseAction | None:
        return WaitForDeletedAction(
            type=ActionType.WAIT_FOR_DELETED,
            next_state=State.NO_OP,
        )
