from collections.abc import Iterator
from logging import Logger
from unittest.mock import Mock, create_autospec, patch

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


BLUE_GREEN_DEPLOYMENT_NOT_ENABLED = {
    "data": {
        "blue_green_deployment": {
            "enabled": False,
            "switchover": False,
            "delete": False,
        }
    }
}


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        ({}, True),
        ({}, False),
        (BLUE_GREEN_DEPLOYMENT_NOT_ENABLED, True),
        (BLUE_GREEN_DEPLOYMENT_NOT_ENABLED, False),
    ],
)
def test_run_when_not_enabled(
    mock_aws_api: Mock,
    mock_logging: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test not enabled"""
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    manager.run()

    mock_logging.info.assert_called_once_with(
        "Blue/Green Deployment not enabled, continue to normal flow."
    )


BLUE_GREEN_DEPLOYMENT_ENABLED = {
    "data": {
        "blue_green_deployment": {
            "enabled": True,
            "switchover": False,
            "delete": False,
            "target": {
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
            },
        }
    }
}


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        (BLUE_GREEN_DEPLOYMENT_ENABLED, True),
        (BLUE_GREEN_DEPLOYMENT_ENABLED, False),
    ],
)
def test_run_create_blue_green_deployment_with_default_target(
    mock_aws_api: Mock,
    mock_logging: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test create default"""
    mock_aws_api.get_db_instance.return_value = {"DBInstanceArn": "some-arn"}
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


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        (BLUE_GREEN_DEPLOYMENT_ENABLED, True),
        (BLUE_GREEN_DEPLOYMENT_ENABLED, False),
    ],
)
def test_run_create_blue_green_deployment_when_rds_not_found(
    mock_aws_api: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test create when not found"""
    mock_aws_api.get_db_instance.return_value = None
    manager = BlueGreenDeploymentManager(
        aws_api=mock_aws_api,
        app_interface_input=input_object(additional_data),
        dry_run=dry_run,
    )

    with pytest.raises(ValueError, match="DB instance not found: test-rds"):
        manager.run()

    mock_aws_api.get_db_instance.assert_called_once_with("test-rds")


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        (BLUE_GREEN_DEPLOYMENT_ENABLED, True),
        (BLUE_GREEN_DEPLOYMENT_ENABLED, False),
    ],
)
def test_run_when_create_blue_green_deployment_when_already_created(
    mock_aws_api: Mock,
    mock_logging: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test create when already created"""
    mock_aws_api.get_db_instance.return_value = {"DBInstanceArn": "some-arn"}
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "Status": "PROVISIONING",
    }
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


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        (BLUE_GREEN_DEPLOYMENT_ENABLED, True),
        (BLUE_GREEN_DEPLOYMENT_ENABLED, False),
    ],
)
def test_run_when_create_blue_green_deployment_with_parameter_group_not_found(
    mock_aws_api: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test create when parameter group not found"""
    mock_aws_api.get_db_instance.return_value = {"DBInstanceArn": "some-arn"}
    mock_aws_api.get_blue_green_deployment.return_value = None
    mock_aws_api.get_db_parameter_group.return_value = None

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


BLUE_GREEN_DEPLOYMENT_SWITCHOVER = {
    "data": {
        "blue_green_deployment": {
            "enabled": True,
            "switchover": True,
            "delete": False,
        }
    }
}


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        (BLUE_GREEN_DEPLOYMENT_SWITCHOVER, True),
        (BLUE_GREEN_DEPLOYMENT_SWITCHOVER, False),
    ],
)
def test_run_when_switchover(
    mock_aws_api: Mock,
    mock_logging: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test switchover"""
    mock_aws_api.get_db_instance.return_value = {"DBInstanceArn": "some-arn"}
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "AVAILABLE",
    }
    mock_aws_api.switchover_blue_green_deployment.return_value = {
        "BlueGreenDeployment": {
            "BlueGreenDeploymentIdentifier": "some-bg-id",
            "Status": "SWITCHING",
        }
    }
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


@pytest.mark.parametrize(
    ("additional_data", "dry_run"),
    [
        (BLUE_GREEN_DEPLOYMENT_SWITCHOVER, True),
        (BLUE_GREEN_DEPLOYMENT_SWITCHOVER, False),
    ],
)
def test_run_when_switchover_in_progress(
    mock_aws_api: Mock,
    mock_logging: Mock,
    additional_data: dict,
    *,
    dry_run: bool,
) -> None:
    """Test switchover in progress"""
    mock_aws_api.get_db_instance.return_value = {"DBInstanceArn": "some-arn"}
    mock_aws_api.get_blue_green_deployment.return_value = {
        "BlueGreenDeploymentName": "test-rds",
        "BlueGreenDeploymentIdentifier": "some-bg-id",
        "Status": "SWITCHOVER_IN_PROGRESS",
    }
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
