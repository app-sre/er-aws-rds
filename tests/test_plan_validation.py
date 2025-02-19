from external_resources_io.terraform import Action, Plan
from hooks.post_plan import RDSPlanValidator

from .conftest import input_object


def test_validate_deletion_protection_not_enabled_on_destroy() -> None:
    """Test deletion protection is not enabled on destroy"""
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
    assert validator.errors == [
        "Deletion protection cannot be enabled on destroy. Disable deletion_protection first to remove the instance"
    ]
