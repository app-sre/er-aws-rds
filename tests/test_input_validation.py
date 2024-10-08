import pytest
from cdktf import Testing

from er_aws_rds.errors import RDSLogicalReplicationError
from er_aws_rds.input import AppInterfaceInput, Parameter

from .conftest import input_data

Testing.__test__ = False


def test_validate_parameter_rds_replication() -> None:
    """Test that rds.logical_replication parameter must be set to 'pending-reboot'"""
    with pytest.raises(RDSLogicalReplicationError):
        AppInterfaceInput.model_validate(
            input_data(
                parameters=[
                    Parameter(
                        name="rds.logical_replication",
                        value="1",
                        apply_method="immediate",
                    ),
                ]
            )
        )


def test_parameter_value_as_string() -> None:
    """Test that parameters are serialized as strings"""
    assert Parameter(name="test", value=60).model_dump(exclude_none=True) == {
        "name": "test",
        "value": "60",
    }
