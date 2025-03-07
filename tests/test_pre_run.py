import os
from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from hooks.pre_run import main
from tests.conftest import input_data, input_object


@pytest.fixture
def mock_read_input_from_file() -> Iterator[Mock]:
    """Patch read_input_from_file"""
    with patch("hooks.pre_run.read_input_from_file") as m:
        yield m


@pytest.fixture
def mock_aws_api() -> Iterator[Mock]:
    """Patch AWSApi"""
    with patch("hooks.pre_run.AWSApi", autospec=True) as m:
        yield m


@pytest.fixture
def mock_blue_green_deployment_manager() -> Iterator[Mock]:
    """Patch BlueGreenDeploymentManager"""
    with patch("hooks.pre_run.BlueGreenDeploymentManager", autospec=True) as m:
        yield m


@pytest.fixture
def mock_is_dry_run() -> Iterator[Mock]:
    """Patch is_dry_run"""
    with patch("hooks.pre_run.is_dry_run") as m:
        yield m


def test_pre_hook_dry_run(
    mock_read_input_from_file: Mock,
    mock_aws_api: Mock,
    mock_blue_green_deployment_manager: Mock,
    mock_is_dry_run: Mock,
) -> None:
    """Test Dry Run"""
    mock_read_input_from_file.return_value = input_data()
    mock_is_dry_run.return_value = True
    expected_model = input_object()

    main()

    mock_aws_api.assert_called_once_with(region_name=expected_model.data.region)
    mock_blue_green_deployment_manager.assert_called_once_with(
        aws_api=mock_aws_api.return_value,
        app_interface_input=expected_model,
        dry_run=True,
    )
    mock_blue_green_deployment_manager.return_value.run.assert_called_once_with()


def test_pre_hook_non_dry_run(
    mock_read_input_from_file: Mock,
    mock_aws_api: Mock,
    mock_blue_green_deployment_manager: Mock,
    mock_is_dry_run: Mock,
) -> None:
    """Test Non Dry Run"""
    mock_read_input_from_file.return_value = input_data()
    mock_is_dry_run.return_value = False
    expected_model = input_object()

    with patch.dict(os.environ, {"DRY_RUN": "False"}):
        main()

    mock_aws_api.assert_called_once_with(region_name=expected_model.data.region)
    mock_blue_green_deployment_manager.assert_called_once_with(
        aws_api=mock_aws_api.return_value,
        app_interface_input=expected_model,
        dry_run=False,
    )
    mock_blue_green_deployment_manager.return_value.run.assert_called_once_with()
