import pytest
from pydantic_core import ValidationError

from er_aws_rds.errors import RDSLogicalReplicationError
from er_aws_rds.input import (
    ENHANCED_MONITORING_ROLE_NAME_MAX_LENGTH,
    AppInterfaceInput,
    BlueGreenDeploymentTarget,
    Parameter,
    ParameterGroup,
)

from .conftest import DEFAULT_PARAMETER_GROUP, input_data


def test_validate_parameter_rds_replication() -> None:
    """Test that rds.logical_replication parameter must be set to 'pending-reboot'"""
    # mod_input = input_data()
    mod_input = input_data({
        "data": {
            "parameter_group": {
                "parameters": [
                    {
                        "name": "rds.logical_replication",
                        "value": "1",
                        "apply_method": "immediate",
                    }
                ],
            }
        }
    })
    with pytest.raises(RDSLogicalReplicationError):
        AppInterfaceInput.model_validate(mod_input)


def test_parameter_value_as_string() -> None:
    """Test that parameters are serialized as strings"""
    assert Parameter(name="test", value=60).model_dump(exclude_none=True) == {
        "name": "test",
        "value": "60",
    }


def test_parameter_group_name() -> None:
    """Test correct parameter group names are set"""
    model = AppInterfaceInput.model_validate(input_data())
    assert model.data.parameter_group is not None
    expected_parameter_group_name = f"{model.data.identifier}-test-pg"
    assert model.data.parameter_group.name == expected_parameter_group_name
    assert model.data.parameter_group_name == expected_parameter_group_name


def test_parameter_group_name_without_pg_name() -> None:
    """Test correct parameter group names are set"""
    mod_input = input_data({"data": {"parameter_group": {"name": None}}})
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.parameter_group is not None
    assert model.data.parameter_group.name == f"{model.data.identifier}-pg"


def test_parameter_group_name_along_old_parameter_group_1() -> None:
    """Test correct parameter group names are set"""
    mod_input = input_data({
        "data": {
            "old_parameter_group": {
                "name": "postgres-16",
                "family": "postgres16",
                "description": "Parameter Group for PostgreSQL 16",
                "parameters": [],
            }
        }
    })
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.parameter_group is not None
    assert model.data.old_parameter_group is not None
    assert model.data.parameter_group.name == f"{model.data.identifier}-test-pg"
    assert model.data.old_parameter_group.name == f"{model.data.identifier}-postgres-16"


def test_parameter_group_along_old_parameter_group_without_names() -> None:
    """Test correct parameter group names are set"""
    mod_input = input_data({
        "data": {
            "parameter_group": {"name": None},
            "old_parameter_group": {
                "family": "postgres16",
                "description": "Parameter Group for PostgreSQL 16",
                "parameters": [],
            },
        }
    })
    with pytest.raises(
        ValidationError,
        match=r".*Parameter group and old parameter group have the same name.*",
    ):
        AppInterfaceInput.model_validate(mod_input)


def test_blue_green_deployment_parameter_group_default_name() -> None:
    """Test Blue/Green Deployment parameter group default name"""
    mod_input = input_data({
        "data": {
            "blue_green_deployment": {
                "enabled": True,
                "switchover": True,
                "delete": True,
                "target": {
                    "parameter_group": {
                        "family": "postgres16",
                    }
                },
            }
        }
    })
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.blue_green_deployment is not None
    assert model.data.blue_green_deployment.target == BlueGreenDeploymentTarget(
        parameter_group=ParameterGroup(
            name=f"{model.data.identifier}-pg",
            family="postgres16",
        )
    )


def test_blue_green_deployment_parameter_group_name() -> None:
    """Test Blue/Green Deployment parameter group name"""
    mod_input = input_data({
        "data": {
            "blue_green_deployment": {
                "enabled": True,
                "switchover": True,
                "delete": True,
                "target": {
                    "parameter_group": {
                        "name": "new-pg",
                        "family": "postgres16",
                    }
                },
            }
        }
    })
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.blue_green_deployment is not None
    assert model.data.blue_green_deployment.target == BlueGreenDeploymentTarget(
        parameter_group=ParameterGroup(
            name=f"{model.data.identifier}-new-pg",
            family="postgres16",
        )
    )


@pytest.mark.parametrize("enabled", [True, False])
def test_blue_green_deployment_parameter_group_same_name_different_values(
    *,
    enabled: bool,
) -> None:
    """Test Blue/Green Deployment parameter group name"""
    target_parameter_group = DEFAULT_PARAMETER_GROUP | {"family": "postgres15"}
    mod_input = input_data({
        "data": {
            "parameter_group": DEFAULT_PARAMETER_GROUP,
            "blue_green_deployment": {
                "enabled": enabled,
                "switchover": False,
                "delete": False,
                "target": {"parameter_group": target_parameter_group},
            },
        }
    })
    with pytest.raises(
        ValidationError,
        match="Blue/Green Deployment Parameter Group name already exist",
    ):
        AppInterfaceInput.model_validate(mod_input)


def test_name() -> None:
    """Test name not set validates ok"""
    mod_input = input_data()
    mod_input["data"].pop("name")
    AppInterfaceInput.model_validate(mod_input)


def test_enhanced_monitoring_sets_default_monitoring_interval() -> None:
    """monitoring_interval != 0 enables enhanced_monitoring"""
    model = AppInterfaceInput.model_validate(
        input_data({
            "data": {
                "enhanced_monitoring": True,
            }
        })
    )
    assert model.data.monitoring_interval == 60


def test_enhanced_monitoring_custom_monitoring_interval() -> None:
    """Test for enhanced monitoring tests"""
    model = AppInterfaceInput.model_validate(
        input_data({"data": {"enhanced_monitoring": True, "monitoring_interval": 90}})
    )
    assert model.data.monitoring_interval == 90


def test_no_enhanced_monitoring_disables_enhanced_monitoring() -> None:
    """enhanced_monitoring_configuration requires enhanced_monitoring"""
    model = AppInterfaceInput.model_validate(
        input_data({
            "data": {
                "enhanced_monitoring": False,
                "monitoring_interval": 90,
                "monitoring_role_arn": "arn:bla:bla",
            }
        })
    )
    assert model.data.monitoring_interval is None
    assert model.data.monitoring_role_arn is None


def test_enhanced_monitoring_with_monitoring_interval_0() -> None:
    """enhanced_monitoring_configuration requires enhanced_monitoring"""
    with pytest.raises(
        ValidationError,
        match=r".*Monitoring interval can not be 0 when enhanced monitoring is enabled.*",
    ):
        AppInterfaceInput.model_validate(
            input_data({
                "data": {
                    "enhanced_monitoring": True,
                    "monitoring_interval": 0,
                }
            })
        )


def test_monitoring_role_arn_requires_monitoring_interval() -> None:
    """monitoring_role_arn requires monitoring_interval != 0"""
    mod_input = input_data({
        "data": {
            "enhanced_monitoring": True,
            "monitoring_role_arn": "A-Role-ARN",
        }
    })
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.monitoring_interval == 60
    assert model.data.monitoring_role_arn == "A-Role-ARN"


def test_very_long_enhanced_monitoring_role_name() -> None:
    """Enhanced monitoring role name must be less than 64 characters"""
    mod_input = input_data({
        "data": {
            "identifier": "a-very-long-identifier-that-will-generate-a-very-long-role-name",
        }
    })
    model = AppInterfaceInput.model_validate(mod_input)
    assert (
        len(model.data.enhanced_monitoring_role_name)
        == ENHANCED_MONITORING_ROLE_NAME_MAX_LENGTH
    )
    assert (
        model.data.enhanced_monitoring_role_name
        == "a-very-long-identifier-that-will-generate-a-very-long-role-na-em"
    )


def test_kms_key_id_alias_removed() -> None:
    """Test that kms_key_id_alias is removed from the input data"""
    mod_input = input_data({
        "data": {
            "kms_key_id": "alias/test",
        }
    })
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.kms_key_id == "test"


def test_timeouts() -> None:
    """Test timeouts data"""
    mod_input = input_data({"data": {"timeouts": {"create": "60m"}}})
    model = AppInterfaceInput.model_validate(mod_input)
    assert model.data.timeouts is not None
    assert model.data.timeouts.create == "60m"


def test_validate_blue_green_update() -> None:
    """Test blue_green_update"""
    mod_input = input_data({"data": {"blue_green_update": {"enabled": True}}})
    with pytest.raises(
        ValidationError,
        match=r"blue_green_update is not supported, use blue_green_deployment instead",
    ):
        AppInterfaceInput.model_validate(mod_input)


def test_validate_replica_source_with_parameter_group() -> None:
    """Test that replica_source with parameter_group is not allowed"""
    mod_input = input_data({
        "data": {
            "replica_source": {
                "identifier": "test-rds-source",
                "region": "us-east-1",
                "blue_green_deployment_enabled": True,
            },
            "parameter_group": DEFAULT_PARAMETER_GROUP,
        }
    })
    with pytest.raises(
        ValidationError,
        match=r".*parameter_group is not supported when replica_source has blue_green_deployment enabled.*",
    ):
        AppInterfaceInput.model_validate(mod_input)
