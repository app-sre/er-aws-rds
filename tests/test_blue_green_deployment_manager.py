from collections.abc import Iterator
from logging import Logger
from unittest.mock import Mock, call, create_autospec, patch

import pytest

from hooks.utils.aws_api import AWSApi
from hooks.utils.blue_green_deployment_manager import BlueGreenDeploymentManager
from hooks.utils.models import CreateBlueGreenDeploymentParams
from tests.conftest import input_object


@pytest.fixture
def mock_aws_api() -> Mock:
    """Mock AWSApi"""
    return create_autospec(AWSApi)


@pytest.fixture
def mock_logging() -> Iterator[Mock]:
    """Patch logging"""
    with patch("hooks.utils.blue_green_deployment_manager.logging.getLogger") as m:
        logger = create_autospec(Logger)
        m.return_value = logger
        yield logger


DEFAULT_TARGET = {
    "engine_version": "15.7",
    "instance_class": "db.t4g.micro",
    "iops": 3000,
    "parameter_group": {
        "name": "pg15",
        "family": "postgres15",
    },
    "allocated_storage": 20,
    "storage_type": "gp3",
    "storage_throughput": 125,
}

DEFAULT_RDS_INSTANCE = {
    "DBInstanceArn": "some-arn",
    "DBInstanceIdentifier": "test-rds",
    "DBParameterGroups": [
        {
            "DBParameterGroupName": "test-rds-pg15",
            "ParameterApplyStatus": "in-sync",
        }
    ],
    "Iops": 3000,
    "EngineVersion": "15.7",
    "DBInstanceClass": "db.t4g.micro",
    "StorageType": "gp3",
    "AllocatedStorage": 20,
    "StorageThroughput": 125,
}


def build_blue_green_deployment_data(
    *,
    enabled: bool = False,
    switchover: bool = False,
    delete: bool = False,
    target: dict | None = None,
) -> dict:
    """Build blue/green deployment config data"""
    return {
        "data": {
            "blue_green_deployment": {
                "enabled": enabled,
                "switchover": switchover,
                "delete": delete,
                "target": DEFAULT_TARGET if target is None else target,
            }
        }
    }


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_no_blue_green_deployment_config(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test not enabled"""
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(),
        dry_run=dry_run,
    )

    manager.run()

    mock_logging.info.assert_called_once_with(
        "Blue/Green Deployment not enabled, continue to normal flow."
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_not_enabled(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test not enabled"""
    additional_data = build_blue_green_deployment_data(enabled=False)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_logging.info.assert_called_once_with(
        "Blue/Green Deployment not enabled, continue to normal flow."
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_create_blue_green_deployment_with_no_target(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test create with no target"""
    additional_data = build_blue_green_deployment_data(enabled=True, target={})
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = None
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )
    expected_params = CreateBlueGreenDeploymentParams(
        name="test-rds",
        source_arn="some-arn",
        tags={
            "app": "external-resources-poc",
            "cluster": "appint-ex-01",
            "environment": "stage",
            "managed_by_integration": "external_resources",
            "namespace": "external-resources-poc",
        },
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        f"Action: CreateBlueGreenDeployment, {expected_params.model_dump(by_alias=True, exclude_none=True)}"
    )
    if dry_run:
        mock_aws_api.create_blue_green_deployment.assert_not_called()
    else:
        mock_aws_api.create_blue_green_deployment.assert_called_once_with(
            expected_params
        )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_create_blue_green_deployment_with_default_target(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test create default"""
    additional_data = build_blue_green_deployment_data(enabled=True)
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = None
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )
    expected_params = CreateBlueGreenDeploymentParams(
        name="test-rds",
        source_arn="some-arn",
        allocated_storage=20,
        engine_version="15.7",
        instance_class="db.t4g.micro",
        iops=3000,
        parameter_group_name="test-rds-pg15",
        storage_throughput=125,
        storage_type="gp3",
        tags={
            "app": "external-resources-poc",
            "cluster": "appint-ex-01",
            "environment": "stage",
            "managed_by_integration": "external_resources",
            "namespace": "external-resources-poc",
        },
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        f"Action: CreateBlueGreenDeployment, {expected_params.model_dump(by_alias=True, exclude_none=True)}"
    )
    if dry_run:
        mock_aws_api.create_blue_green_deployment.assert_not_called()
    else:
        mock_aws_api.create_blue_green_deployment.assert_called_once_with(
            expected_params
        )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_create_blue_green_deployment_when_rds_not_found(
    mock_aws_api: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test create when not found"""
    mock_aws_api.get_db_instance.return_value = None
    additional_data = build_blue_green_deployment_data(enabled=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    with pytest.raises(ValueError, match="DB instance not found: test-rds"):
        manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_create_blue_green_deployment_when_already_created(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test create when already created"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "PROVISIONING",
    }
    additional_data = build_blue_green_deployment_data(enabled=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_aws_api.create_blue_green_deployment.assert_not_called()
    mock_logging.info.assert_called_once_with(
        "Blue/Green Deployment test-rds Status: PROVISIONING"
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_create_blue_green_deployment_with_parameter_group_not_found(
    mock_aws_api: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test create when parameter group not found"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = None
    mock_aws_api.get_db_parameter_group.return_value = None
    additional_data = build_blue_green_deployment_data(enabled=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    with pytest.raises(
        ValueError, match="Target Parameter Group not found: test-rds-pg15"
    ):
        manager.run()

    mock_aws_api.get_db_parameter_group.assert_called_once_with("test-rds-pg15")
    mock_aws_api.create_blue_green_deployment.assert_not_called()


@pytest.mark.parametrize("dry_run", [True, False, ])
def test_run_when_switchover(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test switchover"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "AVAILABLE",
    }
    additional_data = build_blue_green_deployment_data(enabled=True, switchover=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        "Action: SwitchoverBlueGreenDeployment, name: test-rds, identifier: some-bg-id"
    )
    if dry_run:
        mock_aws_api.switchover_blue_green_deployment.assert_not_called()
    else:
        mock_aws_api.switchover_blue_green_deployment.assert_called_once_with(
            "some-bg-id"
        )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_switchover_in_progress(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test switchover in progress"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "SWITCHOVER_IN_PROGRESS",
    }
    additional_data = build_blue_green_deployment_data(enabled=True, switchover=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_aws_api.switchover_blue_green_deployment.assert_not_called()
    mock_logging.info.assert_called_once_with(
        "Blue/Green Deployment test-rds Status: SWITCHOVER_IN_PROGRESS"
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_delete_after_switchover(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test delete after switchover"""
    mock_aws_api.get_db_instance.side_effect = [
        {"DBInstanceArn": "some-arn-new", "DBInstanceStatus": "available", "DBInstanceIdentifier": "test-rds"},
        {"DBInstanceArn": "some-arn-old", "DBInstanceStatus": "available", "DBInstanceIdentifier": "test-rds-old"},
    ]
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "SWITCHOVER_COMPLETED",
        "SwitchoverDetails": [
            {
                "SourceMember": "some-arn-old",
                "TargetMember": "some-arn-new",
                "Status": "SWITCHOVER_COMPLETED",
            }
        ],
    }
    additional_data = build_blue_green_deployment_data(enabled=True, switchover=True, delete=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_has_calls(
        [
            call("test-rds"),
            call("some-arn-old"),
        ]
    )
    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_logging.info.assert_has_calls(
        [
            call("Action: DeleteSourceDBInstance, identifier: test-rds-old"),
            call("Action: DeleteBlueGreenDeployment, name: test-rds, identifier: some-bg-id"),
        ]
    )
    mock_aws_api.delete_blue_green_deployment.assert_not_called()
    if dry_run:
        mock_aws_api.delete_db_instance.assert_not_called()
    else:
        mock_aws_api.delete_db_instance.assert_called_once_with(
            "test-rds-old"
        )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_delete_after_switchover_and_source_deleted(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test delete after switchover and source deleted"""
    mock_aws_api.get_db_instance.side_effect = [
        {"DBInstanceArn": "some-arn-new", "DBInstanceStatus": "available", "DBInstanceIdentifier": "test-rds"},
        None,
    ]
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "SWITCHOVER_COMPLETED",
        "SwitchoverDetails": [
            {
                "SourceMember": "some-arn-old",
                "TargetMember": "some-arn-new",
                "Status": "SWITCHOVER_COMPLETED",
            }
        ],
    }
    additional_data = build_blue_green_deployment_data(enabled=True, switchover=True, delete=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_has_calls(
        [
            call("test-rds"),
            call("some-arn-old"),
        ]
    )
    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        "Action: DeleteBlueGreenDeployment, name: test-rds, identifier: some-bg-id"
    )
    mock_aws_api.delete_db_instance.assert_not_called()
    if dry_run:
        mock_aws_api.delete_blue_green_deployment.assert_not_called()
    else:
        mock_aws_api.delete_blue_green_deployment.assert_called_once_with(
            "some-bg-id"
        )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_delete_without_switchover(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test delete without switchover"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "AVAILABLE",
    }
    additional_data = build_blue_green_deployment_data(enabled=True, switchover=False, delete=True)
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        "Action: DeleteBlueGreenDeployment, name: test-rds, identifier: some-bg-id"
    )
    mock_aws_api.delete_db_instance.assert_not_called()
    if dry_run:
        mock_aws_api.delete_blue_green_deployment.assert_not_called()
    else:
        mock_aws_api.delete_blue_green_deployment.assert_called_once_with(
            "some-bg-id",
            delete_target=True,
        )


@pytest.mark.parametrize(
    ("switchover", "target", "dry_run"),
    [
        (True, {}, True),
        (True, {}, False),
        (True, DEFAULT_TARGET, True),
        (True, DEFAULT_TARGET, False),
        (False, {}, True),
        (False, {}, False),
        (False, DEFAULT_TARGET, True),
        (False, DEFAULT_TARGET, False),
    ],
)
def test_run_when_no_changes_and_no_blue_green_deployment(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    switchover: bool,
    target: dict | None,
    dry_run: bool,
) -> None:
    """Test no changes and no blue/green deployment"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = None
    additional_data = build_blue_green_deployment_data(
        enabled=True,
        switchover=switchover,
        delete=True,
        target=target,
    )
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_aws_api.get_blue_green_deployment.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        "No changes for Blue/Green Deployment, continue to normal flow."
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_when_all_in_one_config(
    mock_aws_api: Mock,
    mock_logging: Mock,
    *,
    dry_run: bool,
) -> None:
    """Test no changes and no blue/green deployment"""
    mock_aws_api.get_db_instance.return_value = DEFAULT_RDS_INSTANCE
    mock_aws_api.get_blue_green_deployment.return_value = None
    additional_data = build_blue_green_deployment_data(
        enabled=True,
        switchover=True,
        delete=True,
        target={"engine_version": "16.3"},
    )
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    expected_params = CreateBlueGreenDeploymentParams(
        name="test-rds",
        source_arn="some-arn",
        engine_version="16.3",
        tags={
            "app": "external-resources-poc",
            "cluster": "appint-ex-01",
            "environment": "stage",
            "managed_by_integration": "external_resources",
            "namespace": "external-resources-poc",
        },
    )

    manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")
    mock_logging.info.assert_called_once_with(
        f"Action: CreateBlueGreenDeployment, {expected_params.model_dump(by_alias=True, exclude_none=True)}"
    )
    if dry_run:
        mock_aws_api.create_blue_green_deployment.assert_not_called()
    else:
        mock_aws_api.create_blue_green_deployment.assert_called_once_with(
            expected_params
        )
