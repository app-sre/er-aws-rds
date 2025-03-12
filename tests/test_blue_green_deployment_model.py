import pytest
from pydantic import ValidationError

from er_aws_rds.input import (
    BlueGreenDeployment,
    BlueGreenDeploymentTarget,
    ParameterGroup,
)
from hooks.utils.blue_green_deployment_model import BlueGreenDeploymentModel
from hooks.utils.models import State
from tests.conftest import DEFAULT_RDS_INSTANCE


def build_blue_green_deployment(
    *,
    switchover: bool = False,
    delete: bool = False,
    target: BlueGreenDeploymentTarget | None = None,
) -> BlueGreenDeployment:
    """Build BlueGreenDeployment object"""
    return BlueGreenDeployment(
        enabled=True,
        switchover=switchover,
        delete=delete,
        target=target,
    )


def test_validate_db_instance_exist() -> None:
    """Test validate db instance exist"""
    with pytest.raises(ValidationError, match=r".*DB Instance not found: test-rds.*"):
        BlueGreenDeploymentModel(
            db_instance_identifier="test-rds",
            state=State.INIT,
            config=build_blue_green_deployment(),
            db_instance=None,
        )


def test_validate_target_parameter_group() -> None:
    """Test validate target parameter group"""
    with pytest.raises(
        ValidationError, match=r".*Target Parameter Group not found: pg15.*"
    ):
        BlueGreenDeploymentModel(
            db_instance_identifier="test-rds",
            state=State.INIT,
            config=build_blue_green_deployment(
                target=BlueGreenDeploymentTarget(
                    parameter_group=ParameterGroup(family="postgres15", name="pg15")
                )
            ),
            db_instance=DEFAULT_RDS_INSTANCE,
            target_db_parameter_group=None,
        )


def test_validate_deletion_protection() -> None:
    """Test validate deletion protection"""
    with pytest.raises(
        ValidationError, match=r".*deletion_protection must be disabled.*"
    ):
        BlueGreenDeploymentModel(
            db_instance_identifier="test-rds",
            state=State.INIT,
            config=build_blue_green_deployment(),
            db_instance=DEFAULT_RDS_INSTANCE | {"DeletionProtection": True},
        )


def test_validate_backup_retention_period() -> None:
    """Test validate backup retention period"""
    with pytest.raises(
        ValidationError, match=r".*backup_retention_period must be greater than 0.*"
    ):
        BlueGreenDeploymentModel(
            db_instance_identifier="test-rds",
            state=State.INIT,
            config=build_blue_green_deployment(),
            db_instance=DEFAULT_RDS_INSTANCE | {"BackupRetentionPeriod": 0},
        )
