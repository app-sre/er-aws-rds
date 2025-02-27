from typing import Any
from unittest.mock import Mock, patch

import boto3
import pytest
from external_resources_io.terraform import Action, Plan

from hooks.post_plan import RDSPlanValidator
from hooks.utils.aws_api import AWSApi

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
def rds_client_mock() -> Mock:
    """Return a mock of the boto3 rds client"""
    return Mock(boto3.client("rds", region_name="us-east-1"))


def test_validate_desired_version_ok(
    new_instance_plan: dict[str, Any], rds_client_mock: Mock
) -> None:
    """Test engine version available in AWS"""
    rds_client_mock.describe_db_engine_versions.return_value = {
        "DBEngineVersions": [
            {"EngineVersion": "16.1"},
        ]
    }

    with patch.object(AWSApi, "get_rds_client", return_value=rds_client_mock):
        plan = Plan.model_validate(new_instance_plan)
        validator = RDSPlanValidator(plan, input_object())
        validator.validate()
        assert validator.errors == []


def test_validate_desired_version_nok(
    new_instance_plan: dict[str, Any], rds_client_mock: Mock
) -> None:
    """Test engine version not available in AWS"""
    rds_client_mock.describe_db_engine_versions.return_value = {
        "DBEngineVersions": [
            {"EngineVersion": "16.2"},
        ]
    }
    with patch.object(AWSApi, "get_rds_client", return_value=rds_client_mock):
        plan = Plan.model_validate(new_instance_plan)
        validator = RDSPlanValidator(plan, input_object())
        validator.validate()
        assert validator.errors == ["postgres version 16.1 is not available."]


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
    validator.validate()
    assert (
        "Deletion protection cannot be enabled on destroy. Disable deletion_protection first to remove the instance"
        in validator.errors
    )
