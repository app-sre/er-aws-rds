import pytest

from er_aws_rds.input import TerraformModuleData

from .conftest import DEFAULT_PARAMETER_GROUP, input_object

EXPECTED_DEFAULT_PARAMETER_GROUP = DEFAULT_PARAMETER_GROUP | {
    "name": "test-rds-test-pg",
}
OLD_PARAMETER_GROUP = {
    "name": "postgres-15",
    "family": "postgres15",
    "description": "Parameter Group for PostgreSQL 15",
    "parameters": [],
}
EXPECTED_OLD_PARAMETER_GROUP = OLD_PARAMETER_GROUP | {
    "name": "test-rds-postgres-15",
}
BLUE_GREEN_DEPLOYMENT_PARAMETER_GROUP = {
    "name": "postgres-16",
    "family": "postgres16",
    "description": "Parameter Group for PostgreSQL 16",
    "parameters": [],
}
EXPECTED_BLUE_GREEN_DEPLOYMENT_PARAMETER_GROUP = (
    BLUE_GREEN_DEPLOYMENT_PARAMETER_GROUP
    | {
        "name": "test-rds-postgres-16",
    }
)


def test_parameter_group_names() -> None:
    """Ensure terraform model gets the right parameter group names"""
    model = input_object({
        "data": {
            "old_parameter_group": OLD_PARAMETER_GROUP,
        }
    })
    tf_model = TerraformModuleData(ai_input=model).model_dump()

    assert tf_model["parameter_groups"] == [
        EXPECTED_DEFAULT_PARAMETER_GROUP,
        EXPECTED_OLD_PARAMETER_GROUP,
    ]


@pytest.mark.parametrize("enabled", [True, False])
def test_parameter_groups_with_blue_green_deployment(*, enabled: bool) -> None:
    """Test parameter groups with blue-green deployment"""
    model = input_object({
        "data": {
            "old_parameter_group": OLD_PARAMETER_GROUP,
            "blue_green_deployment": {
                "enabled": enabled,
                "switchover": False,
                "delete": False,
                "target": {
                    "parameter_group": BLUE_GREEN_DEPLOYMENT_PARAMETER_GROUP,
                },
            },
        }
    })
    tf_model = TerraformModuleData(ai_input=model).model_dump()

    assert tf_model["parameter_groups"] == [
        EXPECTED_DEFAULT_PARAMETER_GROUP,
        EXPECTED_OLD_PARAMETER_GROUP,
        EXPECTED_BLUE_GREEN_DEPLOYMENT_PARAMETER_GROUP,
    ]


def test_parameter_groups_when_blue_green_deployment_has_duplicate() -> None:
    """Test parameter groups when blue-green deployment has duplicate"""
    model = input_object({
        "data": {
            "old_parameter_group": OLD_PARAMETER_GROUP,
            "parameter_group": DEFAULT_PARAMETER_GROUP,
            "blue_green_deployment": {
                "enabled": False,
                "switchover": False,
                "delete": False,
                "target": {
                    "parameter_group": DEFAULT_PARAMETER_GROUP,
                },
            },
        }
    })
    tf_model = TerraformModuleData(ai_input=model).model_dump()

    assert tf_model["parameter_groups"] == [
        EXPECTED_DEFAULT_PARAMETER_GROUP,
        EXPECTED_OLD_PARAMETER_GROUP,
    ]
