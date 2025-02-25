from collections.abc import Iterator
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec, patch

import pytest

from hooks.utils.aws_api import AWSApi
from hooks.utils.models import CreateBlueGreenDeploymentParams

if TYPE_CHECKING:
    from mypy_boto3_rds.type_defs import DBInstanceTypeDef
from mypy_boto3_rds import RDSClient


@pytest.fixture
def mock_session() -> Iterator[Mock]:
    """Patch Session"""
    with patch("hooks.utils.aws_api.Session", autospec=True) as m:
        yield m


@pytest.mark.parametrize(
    "region_name",
    [
        None,
        "us-east-1",
    ],
)
def test_init(mock_session: Mock, region_name: str | None) -> None:
    """Test init"""
    aws_api = AWSApi(region_name=region_name)

    assert aws_api.session == mock_session.return_value
    assert aws_api.rds_client == mock_session.return_value.client.return_value
    mock_session.assert_called_once_with(region_name=region_name)
    mock_session.return_value.client.assert_called_once_with("rds")


@pytest.fixture
def mock_rds_client() -> Iterator[Mock]:
    """Patch Session"""
    with patch("hooks.utils.aws_api.Session", autospec=True) as m:
        client = create_autospec(RDSClient)
        m.return_value.client.return_value = client
        yield client


def test_get_db_instance(mock_rds_client: Mock) -> None:
    """Test get_db_instance"""
    expected_result: DBInstanceTypeDef = {
        "DBInstanceArn": "arn:aws:rds:us-east-1:xxx",
        "DBInstanceIdentifier": "identifier",
    }
    mock_rds_client.describe_db_instances.return_value = {
        "DBInstances": [expected_result]
    }
    aws_api = AWSApi()

    result = aws_api.get_db_instance("identifier")

    assert result == expected_result
    mock_rds_client.describe_db_instances.assert_called_once_with(
        DBInstanceIdentifier="identifier"
    )


def test_get_db_instance_not_found(mock_rds_client: Mock) -> None:
    """Test get_db_instance"""
    mock_rds_client.describe_db_instances.return_value = {"DBInstances": []}
    aws_api = AWSApi()

    result = aws_api.get_db_instance("identifier")

    assert result is None


def test_create_blue_green_deployment(mock_rds_client: Mock) -> None:
    """Test create_blue_green_deployment"""
    aws_api = AWSApi()

    params = CreateBlueGreenDeploymentParams(
        name="name",
        source_arn="arn:aws:rds:us-east-1:xxx",
    )

    aws_api.create_blue_green_deployment(params)

    mock_rds_client.create_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentName="name",
        Source="arn:aws:rds:us-east-1:xxx",
    )


def test_create_blue_green_deployment_with_all_params(mock_rds_client: Mock) -> None:
    """Test create_blue_green_deployment"""
    aws_api = AWSApi()

    params = CreateBlueGreenDeploymentParams(
        name="name",
        source_arn="arn:aws:rds:us-east-1:xxx",
        allocated_storage=20,
        engine_version="15.7",
        instance_class="db.t4g.micro",
        iops=3000,
        parameter_group_name="parameter-group",
        storage_throughput=125,
        storage_type="gp3",
        tags={"k": "v"},
    )

    aws_api.create_blue_green_deployment(params)

    mock_rds_client.create_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentName="name",
        Source="arn:aws:rds:us-east-1:xxx",
        TargetAllocatedStorage=20,
        TargetDBInstanceClass="db.t4g.micro",
        TargetDBParameterGroupName="parameter-group",
        TargetEngineVersion="15.7",
        TargetIops=3000,
        TargetStorageThroughput=125,
        TargetStorageType="gp3",
        Tags=[{"Key": "k", "Value": "v"}],
    )


def test_get_blue_green_deployment(mock_rds_client: Mock) -> None:
    """Test get_blue_green_deployment"""
    expected_result = {"BlueGreenDeploymentName": "name"}
    mock_rds_client.describe_blue_green_deployments.return_value = {
        "BlueGreenDeployments": [expected_result]
    }
    aws_api = AWSApi()

    result = aws_api.get_blue_green_deployment("name")

    assert result == expected_result
    mock_rds_client.describe_blue_green_deployments.assert_called_once_with(
        Filters=[
            {
                "Name": "blue-green-deployment-name",
                "Values": ["name"],
            }
        ]
    )


def test_get_blue_green_deployment_when_not_found(mock_rds_client: Mock) -> None:
    """Test get_blue_green_deployment"""
    mock_rds_client.describe_blue_green_deployments.return_value = {
        "BlueGreenDeployments": []
    }
    aws_api = AWSApi()

    result = aws_api.get_blue_green_deployment("name")

    assert result is None


def test_get_db_parameter_group(mock_rds_client: Mock) -> None:
    """Test get_db_parameter_group"""
    aws_api = AWSApi()
    expected_result = {"DBParameterGroupName": "name"}
    mock_rds_client.describe_db_parameter_groups.return_value = {
        "DBParameterGroups": [expected_result]
    }

    result = aws_api.get_db_parameter_group("name")

    assert result == expected_result
    mock_rds_client.describe_db_parameter_groups.assert_called_once_with(
        DBParameterGroupName="name"
    )


def test_get_db_parameter_group_when_not_found(mock_rds_client: Mock) -> None:
    """Test get_db_parameter_group"""
    aws_api = AWSApi()
    mock_rds_client.describe_db_parameter_groups.return_value = {
        "DBParameterGroups": []
    }

    result = aws_api.get_db_parameter_group("name")

    assert result is None
    mock_rds_client.describe_db_parameter_groups.assert_called_once_with(
        DBParameterGroupName="name"
    )


def test_switchover_switchover_blue_green_deployment(mock_rds_client: Mock) -> None:
    """Test switchover_blue_green_deployment"""
    aws_api = AWSApi()
    mock_rds_client.switchover_blue_green_deployment.return_value = None

    aws_api.switchover_blue_green_deployment("identifier")

    mock_rds_client.switchover_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentIdentifier="identifier"
    )
