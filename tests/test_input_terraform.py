from er_aws_rds.input import AppInterfaceInput, TerraformModuleData

from .conftest import input_data


def test_parameter_group_names() -> None:
    """Ensure terraform model gets the right parameter group names"""
    model = AppInterfaceInput.model_validate(
        input_data({
            "data": {
                "old_parameter_group": {
                    "name": "postgres-16",
                    "family": "postgres16",
                    "description": "Parameter Group for PostgreSQL 16",
                    "parameters": [],
                }
            }
        })
    )
    tf_model = TerraformModuleData(ai_input=model).model_dump()

    assert model.data.parameter_group is not None
    assert model.data.old_parameter_group is not None

    assert len(tf_model["parameter_groups"]) == 2  # noqa: PLR2004
    assert (
        tf_model["parameter_groups"][0]["name"]
        == model.data.parameter_group.computed_pg_name
    )
    assert (
        tf_model["parameter_groups"][1]["name"]
        == model.data.old_parameter_group.computed_pg_name
    )
