from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock, patch

import pytest
from external_resources_io.terraform import Action, Plan

from hooks.post_plan import RDSPlanValidator

from .conftest import input_object


@pytest.fixture
def new_instance_plan() -> dict[str, Any]:
    "Return a plan for an rds instance creation"
    return {
        "resource_changes": [
            {
                "type": "aws_db_instance",
                "change": {
                    "actions": [Action.ActionCreate],
                    "before": None,
                    "after": {
                        "engine": "postgres",
                        "engine_version": "16.1",
                        "deletion_protection": False,
                    },
                    "after_unknown": None,
                },
            }
        ]
    }


@pytest.fixture
def mock_aws_api() -> Iterator[Mock]:
    """Patch AWSApi"""
    with patch("hooks.post_plan.AWSApi", autospec=True) as m:
        yield m


@pytest.mark.parametrize(
    ("is_rds_engine_version_available", "expected_errors"),
    [
        (True, []),
        (False, ["postgres version 16.1 is not available."]),
    ],
)
def test_validate_desired_version(
    new_instance_plan: dict[str, Any],
    mock_aws_api: Mock,
    *,
    is_rds_engine_version_available: bool,
    expected_errors: list[str],
) -> None:
    """Test engine version available in AWS"""
    mock_aws_api.return_value.is_rds_engine_version_available.return_value = (
        is_rds_engine_version_available
    )

    plan = Plan.model_validate(new_instance_plan)
    validator = RDSPlanValidator(plan, input_object())
    errors = validator.validate()
    assert errors == expected_errors


def test_validate_deletion_protection_not_enabled_on_destroy() -> None:
    """Test instance deletion protection is not set when destroying the instance"""
    plan = Plan.model_validate({
        "resource_changes": [
            {
                "type": "aws_db_instance",
                "change": {
                    "actions": [Action.ActionDelete],
                    "before": {
                        "engine": "postgres",
                        "engine_version": "16.1",
                        "deletion_protection": True,
                    },
                    "after": None,
                    "after_unknown": None,
                },
            }
        ]
    })

    validator = RDSPlanValidator(plan, input_object())
    errors = validator.validate()
    assert (
        "Deletion protection cannot be enabled on destroy. Disable deletion_protection first to remove the instance"
        in errors
    )


def test_validate_version_upgrade(mock_aws_api: Mock) -> None:
    """Test version upgrade validation"""
    mock_aws_api.return_value.get_rds_valid_upgrade_targets.return_value = {
        "16.1": {
            "EngineVersion": "16.1",
            "IsMajorVersionUpgrade": True,
        }
    }
    plan = Plan.model_validate({
        "resource_changes": [
            {
                "type": "aws_db_instance",
                "change": {
                    "actions": [Action.ActionUpdate],
                    "before": {
                        "engine": "postgres",
                        "engine_version": "15.7",
                    },
                    "after": {
                        "engine": "postgres",
                        "engine_version": "16.1",
                    },
                    "after_unknown": None,
                },
            }
        ]
    })

    validator = RDSPlanValidator(
        plan,
        input_object({
            "data": {
                "allow_major_version_upgrade": False,
            }
        }),
    )
    errors = validator.validate()
    assert errors == [
        "To enable major version upgrade, allow_major_version_upgrade attribute must be set to True"
    ]


@pytest.mark.parametrize(
    "change",
    [
        {
            "type": "aws_db_parameter_group",
            "change": {
                "actions": ["update"],
                "before": {
                    "id": "test-rds-pg15",
                    "name": "test-rds-pg15",
                    "family": "postgres15",
                    "parameter": [
                        {
                            "apply_method": "pending-reboot",
                            "name": "rds.force_ssl",
                            "value": "0",
                        },
                    ],
                },
                "after": {
                    "id": "test-rds-pg15",
                    "name": "test-rds-pg15",
                    "family": "postgres15",
                    "parameter": [
                        {
                            "apply_method": "pending-reboot",
                            "name": "rds.force_ssl",
                            "value": "1",
                        },
                    ],
                },
                "after_unknown": None,
            },
        },
        {
            "type": "aws_db_instance",
            "change": {
                "actions": ["update"],
                "before": {
                    "id": "some-id",
                    "name": "test-rds",
                    "engine": "postgres",
                    "engine_version": "15.7",
                    "allocated_storage": 30,
                },
                "after": {
                    "id": "test-rds-pg15",
                    "name": "test-rds-pg15",
                    "engine": "postgres",
                    "engine_version": "15.7",
                    "allocated_storage": 20,
                },
                "after_unknown": {},
            },
        },
    ],
)
def test_validate_no_changes_when_blue_green_deployment_enabled(change: dict) -> None:
    """Test no changes when Blue/Green Deployment is enabled"""
    plan = Plan.model_validate({
        "resource_changes": [
            change,
        ]
    })
    validator = RDSPlanValidator(
        plan,
        input_object({
            "data": {
                "blue_green_deployment": {
                    "enabled": True,
                    "switchover": True,
                    "delete": True,
                }
            }
        }),
    )

    errors = validator.validate()

    assert errors == [
        f"No changes allowed when Blue/Green Deployment enabled, detected changes: {plan.resource_changes}"
    ]


@pytest.mark.parametrize(
    "change",
    [
        {
            "type": "aws_db_instance",
            "change": {
                "actions": ["delete"],
                "before": {
                    "id": "some-id",
                    "name": "test-rds",
                    "engine": "postgres",
                    "engine_version": "16.3",
                },
                "after": {},
                "after_unknown": {},
            },
        },
        {
            "type": "aws_db_parameter_group",
            "change": {
                "actions": ["delete"],
                "before": {
                    "id": "test-rds-pg15",
                    "name": "test-rds-pg15",
                    "family": "postgres15",
                },
                "after": {},
                "after_unknown": {},
            },
        },
    ],
)
def test_validate_no_changes_allow_delete_when_blue_green_deployment_enabled(
    change: dict,
) -> None:
    """Test delete is allowed when Blue/Green Deployment is enabled"""
    plan = Plan.model_validate({"resource_changes": [change]})
    validator = RDSPlanValidator(
        plan,
        input_object({
            "data": {
                "blue_green_deployment": {
                    "enabled": True,
                    "switchover": True,
                    "delete": True,
                }
            }
        }),
    )

    errors = validator.validate()

    assert errors == []


def test_validate_parameter_group_on_update() -> None:
    """Test parameter group update validation"""
    plan = Plan.model_validate({
        "resource_changes": [
            {
                "type": "aws_db_parameter_group",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "id": "test-rds-pg15",
                        "name": "test-rds-pg15",
                        "family": "postgres15",
                        "parameter": [
                            {
                                "apply_method": "pending-reboot",
                                "name": "rds.force_ssl",
                                "value": "1",
                            },
                        ],
                    },
                    "after": {
                        "id": "test-rds-pg15",
                        "name": "test-rds-pg15",
                        "family": "postgres15",
                        "parameter": [
                            {
                                "apply_method": "immediate",
                                "name": "rds.force_ssl",
                                "value": "1",
                            },
                        ],
                    },
                    "after_unknown": {},
                },
            },
        ]
    })
    validator = RDSPlanValidator(plan, input_object())

    errors = validator.validate()

    assert errors == [
        "Problematic plan changes for parameter group detected, "
        "apply_method only changes are not allowed, parameters: rds.force_ssl, "
        "checkout https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_parameter_group#problematic-plan-changes"
    ]


def test_validate_parameter_group_on_create(
    mock_aws_api: Mock,
) -> None:
    """Test parameter group creation validation"""
    # ApplyMethod is pending-reboot in default parameter group
    # but the field is not returend in actual DescribeEngineDefaultParameters response
    mock_aws_api.return_value.get_engine_default_parameters.return_value = {
        "rds.force_ssl": {
            "ParameterName": "rds.force_ssl",
            "ParameterValue": "1",
        }
    }
    plan = Plan.model_validate({
        "resource_changes": [
            {
                "type": "aws_db_parameter_group",
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {
                        "id": "test-rds-pg15",
                        "name": "test-rds-pg15",
                        "family": "postgres15",
                        "parameter": [
                            {
                                "apply_method": "immediate",
                                "name": "rds.force_ssl",
                                "value": "1",
                            },
                        ],
                    },
                    "after_unknown": {},
                },
            },
        ]
    })
    validator = RDSPlanValidator(plan, input_object())

    errors = validator.validate()

    assert errors == [
        "Problematic plan changes for parameter group detected, "
        "apply_method only changes are not allowed, parameters: rds.force_ssl, "
        "checkout https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_parameter_group#problematic-plan-changes"
    ]
