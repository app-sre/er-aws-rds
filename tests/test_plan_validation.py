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


def test_validate_no_changes_when_blue_green_deployment_enabled() -> None:
    """Test no changes when Blue/Green Deployment is enabled"""
    plan = Plan.model_validate({
        "resource_changes": [
            {
                "type": "aws_db_parameter_group",
                "change": {
                    "actions": [Action.ActionDelete],
                    "before": {
                        "id": "test-rds-pg15",
                        "name": "test-rds-pg15",
                        "engine": "postgres",
                    },
                    "after": None,
                    "after_unknown": None,
                },
            }
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

    assert errors == ["No changes allowed when Blue/Green Deployment enabled."]
