from external_resources_io.input import (
    create_backend_tf_file,
    create_tf_vars_json,
    parse_model,
    read_input_from_file,
)

from er_aws_rds.input import AppInterfaceInput, TerraformModuleData


def get_ai_input() -> AppInterfaceInput:
    """Get the AppInterfaceInput from the input file."""
    return parse_model(
        AppInterfaceInput,
        read_input_from_file(),
    )


def generate_tf_files() -> None:
    """Main method"""
    ai_input = get_ai_input()
    create_backend_tf_file(ai_input.provision)
    tf = TerraformModuleData(ai_input=ai_input)
    create_tf_vars_json(tf)
