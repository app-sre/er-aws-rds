from collections.abc import Iterator
from logging import Logger
from unittest.mock import Mock, create_autospec, patch

import pytest
from hooks.utils.aws_api import AWSApi
from hooks.utils.blue_green_deployment_manager import BlueGreenDeploymentManager

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
    dry_run: bool,  # noqa: FBT001
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
