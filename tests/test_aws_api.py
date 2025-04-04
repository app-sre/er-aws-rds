from collections.abc import Iterator
from typing import TYPE_CHECKING
from unittest.mock import Mock, call, create_autospec, patch

import pytest
from botocore.exceptions import ClientError

from hooks.utils.aws_api import AWSApi
from hooks.utils.models import CreateBlueGreenDeploymentParams

if TYPE_CHECKING:
    from mypy_boto3_rds.type_defs import (
        DBInstanceTypeDef,
    )
from mypy_boto3_rds import (
    DescribeDBParametersPaginator,
    DescribeEngineDefaultParametersPaginator,
    RDSClient,
)
from mypy_boto3_rds.type_defs import (
    DescribeDBParametersMessagePaginateTypeDef,
    DescribeEngineDefaultParametersMessagePaginateTypeDef,
    ParameterOutputTypeDef,
)


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


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        ([{"EngineVersion": "16.1"}], True),
        ([], False),
    ],
)
def test_is_rds_engine_version_available(
    mock_rds_client: Mock,
    versions: list[dict[str, str]],
    *,
    expected: bool,
) -> None:
    """Test is_rds_engine_version_available"""
    mock_rds_client.describe_db_engine_versions.return_value = {
        "DBEngineVersions": versions,
    }
    aws_api = AWSApi()

    result = aws_api.is_rds_engine_version_available("postgres", "16.1")

    assert result == expected


def test_get_rds_valid_upgrade_targets(
    mock_rds_client: Mock,
) -> None:
    """Test get_rds_valid_upgrade_targets"""
    mock_rds_client.describe_db_engine_versions.return_value = {
        "DBEngineVersions": [
            {
                "ValidUpgradeTarget": [
                    {"EngineVersion": "16.1"},
                ]
            }
        ]
    }
    aws_api = AWSApi()

    result = aws_api.get_rds_valid_upgrade_targets("postgres", "15.7")

    assert result == {
        "16.1": {
            "EngineVersion": "16.1",
        }
    }
    mock_rds_client.describe_db_engine_versions.assert_called_once_with(
        Engine="postgres",
        EngineVersion="15.7",
        IncludeAll=True,
    )


def test_get_blue_green_deployment_valid_upgrade_targets(
    mock_rds_client: Mock,
) -> None:
    """Test get_blue_green_deployment_valid_upgrade_targets"""
    expected_result = {
        "15.7": {
            "Engine": "postgres",
            "EngineVersion": "15.7",
            "IsMajorVersionUpgrade": False,
        },
        "15.8": {
            "Engine": "postgres",
            "EngineVersion": "15.8",
            "IsMajorVersionUpgrade": False,
        },
        "16.3": {
            "Engine": "postgres",
            "EngineVersion": "16.3",
            "IsMajorVersionUpgrade": True,
        },
    }
    mock_rds_client.describe_db_engine_versions.side_effect = [
        {
            "DBEngineVersions": [
                {
                    "EngineVersion": "15.7",
                    "ValidUpgradeTarget": [
                        {
                            "Engine": "postgres",
                            "EngineVersion": "15.8",
                            "IsMajorVersionUpgrade": False,
                        },
                        {
                            "Engine": "postgres",
                            "EngineVersion": "16.1",
                            "IsMajorVersionUpgrade": True,
                        },
                        {
                            "Engine": "postgres",
                            "EngineVersion": "16.3",
                            "IsMajorVersionUpgrade": True,
                        },
                    ],
                }
            ]
        },
        {
            "DBEngineVersions": [
                {
                    "EngineVersion": "15.7",
                },
                {
                    "EngineVersion": "15.8",
                },
                {
                    "EngineVersion": "16.3",
                },
            ]
        },
    ]
    aws_api = AWSApi()

    result = aws_api.get_blue_green_deployment_valid_upgrade_targets("postgres", "15.7")

    assert result == expected_result
    mock_rds_client.describe_db_engine_versions.assert_has_calls([
        call(
            Engine="postgres",
            EngineVersion="15.7",
            IncludeAll=True,
        ),
        call(
            Engine="postgres",
            Filters=[
                {"Name": "engine-version", "Values": ["15.7", "15.8", "16.1", "16.3"]}
            ],
        ),
    ])


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
    mock_rds_client.exceptions.DBInstanceNotFoundFault = ClientError
    mock_rds_client.describe_db_instances.side_effect = ClientError(
        error_response={
            "Error": {
                "Code": "DBInstanceNotFound",
            },
        },
        operation_name="DescribeDBInstances",
    )
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


@pytest.mark.parametrize(
    ("parameter_names", "expected_parameters", "expected_kwargs"),
    [
        (
            None,
            {
                "rds.logical_replication": {
                    "ParameterName": "rds.logical_replication",
                    "ParameterValue": "1",
                    "ApplyMethod": "pending-reboot",
                },
            },
            {"DBParameterGroupName": "pg15"},
        ),
        (
            ["rds.logical_replication", "rds.force_ssl"],
            {
                "rds.logical_replication": {
                    "ParameterName": "rds.logical_replication",
                    "ParameterValue": "1",
                    "ApplyMethod": "pending-reboot",
                },
                "rds.force_ssl": {
                    "ParameterName": "rds.force_ssl",
                    "ParameterValue": "1",
                    "ApplyMethod": "immediate",
                },
            },
            {
                "DBParameterGroupName": "pg15",
                "Filters": [
                    {
                        "Name": "parameter-name",
                        "Values": ["rds.logical_replication", "rds.force_ssl"],
                    }
                ],
            },
        ),
    ],
)
def test_get_db_parameters(
    parameter_names: list[str] | None,
    expected_parameters: dict[str, ParameterOutputTypeDef],
    expected_kwargs: DescribeDBParametersMessagePaginateTypeDef,
    mock_rds_client: Mock,
) -> None:
    """Test get_db_parameters"""
    aws_api = AWSApi()
    mock_paginator = create_autospec(DescribeDBParametersPaginator)
    mock_paginator.paginate.return_value = [
        {
            "Parameters": [parameter],
        }
        for parameter in expected_parameters.values()
    ]
    mock_rds_client.get_paginator.return_value = mock_paginator

    result = aws_api.get_db_parameters(
        parameter_group_name="pg15",
        parameter_names=parameter_names,
    )

    assert result == expected_parameters
    mock_rds_client.get_paginator.assert_called_once_with("describe_db_parameters")
    mock_paginator.paginate.assert_called_once_with(**expected_kwargs)


@pytest.mark.parametrize(
    ("parameter_names", "expected_parameters", "expected_kwargs"),
    [
        (
            None,
            {
                "rds.force_ssl": {
                    "ParameterName": "rds.force_ssl",
                    "ParameterValue": "1",
                    "ApplyMethod": "pending-reboot",
                },
            },
            {"DBParameterGroupFamily": "postgres15"},
        ),
        (
            ["rds.force_ssl", "rds.logical_replication"],
            {
                "rds.force_ssl": {
                    "ParameterName": "rds.force_ssl",
                    "ParameterValue": "1",
                    "ApplyMethod": "pending-reboot",
                },
                "rds.logical_replication": {
                    "ParameterName": "rds.logical_replication",
                    "ParameterValue": "1",
                    "ApplyMethod": "pending-reboot",
                },
            },
            {
                "DBParameterGroupFamily": "postgres15",
                "Filters": [
                    {
                        "Name": "parameter-name",
                        "Values": ["rds.force_ssl", "rds.logical_replication"],
                    }
                ],
            },
        ),
    ],
)
def test_get_engine_default_parameters(
    parameter_names: list[str] | None,
    expected_parameters: dict[str, ParameterOutputTypeDef],
    expected_kwargs: DescribeEngineDefaultParametersMessagePaginateTypeDef,
    mock_rds_client: Mock,
) -> None:
    """Test get_engine_default_parameters"""
    aws_api = AWSApi()
    mock_paginator = create_autospec(DescribeEngineDefaultParametersPaginator)
    mock_paginator.paginate.return_value = [
        {
            "EngineDefaults": {
                "DBParameterGroupFamily": "postgres15",
                "Parameters": [parameter],
            }
        }
        for parameter in expected_parameters.values()
    ]
    mock_rds_client.get_paginator.return_value = mock_paginator

    result = aws_api.get_engine_default_parameters(
        parameter_group_family="postgres15",
        parameter_names=parameter_names,
    )

    assert result == expected_parameters
    mock_rds_client.get_paginator.assert_called_once_with(
        "describe_engine_default_parameters"
    )
    mock_paginator.paginate.assert_called_once_with(**expected_kwargs)


def test_switchover_blue_green_deployment(mock_rds_client: Mock) -> None:
    """Test switchover_blue_green_deployment"""
    aws_api = AWSApi()
    mock_rds_client.switchover_blue_green_deployment.return_value = None

    aws_api.switchover_blue_green_deployment("identifier")

    mock_rds_client.switchover_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentIdentifier="identifier"
    )


def test_switchover_blue_green_deployment_with_timeout(mock_rds_client: Mock) -> None:
    """Test switchover_blue_green_deployment"""
    aws_api = AWSApi()
    mock_rds_client.switchover_blue_green_deployment.return_value = None

    aws_api.switchover_blue_green_deployment("identifier", timeout=600)

    mock_rds_client.switchover_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentIdentifier="identifier",
        SwitchoverTimeout=600,
    )


def test_delete_db_instance(mock_rds_client: Mock) -> None:
    """Test delete_db_instance"""
    aws_api = AWSApi()

    aws_api.delete_db_instance("identifier")

    mock_rds_client.delete_db_instance.assert_called_once_with(
        DBInstanceIdentifier="identifier", SkipFinalSnapshot=True
    )


def test_delete_blue_green_deployment(mock_rds_client: Mock) -> None:
    """Test delete_blue_green_deployment"""
    aws_api = AWSApi()

    aws_api.delete_blue_green_deployment("identifier")

    mock_rds_client.delete_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentIdentifier="identifier"
    )


@pytest.mark.parametrize(
    "delete_target",
    [
        True,
        False,
    ],
)
def test_delete_blue_green_deployment_with_delete_target(
    mock_rds_client: Mock,
    *,
    delete_target: bool,
) -> None:
    """Test delete_blue_green_deployment"""
    aws_api = AWSApi()

    aws_api.delete_blue_green_deployment("identifier", delete_target=delete_target)

    mock_rds_client.delete_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentIdentifier="identifier",
        DeleteTarget=delete_target,
    )


def test_delete_blue_green_deployment_with_delete_target_none(
    mock_rds_client: Mock,
) -> None:
    """Test delete_blue_green_deployment"""
    aws_api = AWSApi()

    aws_api.delete_blue_green_deployment("identifier", delete_target=None)

    mock_rds_client.delete_blue_green_deployment.assert_called_once_with(
        BlueGreenDeploymentIdentifier="identifier",
    )
