import os

from cdktf import App
from external_resources_io.input import parse_model, read_input_from_file

from er_aws_rds.input import AppInterfaceInput
from er_aws_rds.rds import Stack


def get_ai_input() -> AppInterfaceInput:
    """Get the AppInterfaceInput from the input file."""
    return parse_model(
        AppInterfaceInput,
        read_input_from_file(),
    )


def init_cdktf_app(ai_input: AppInterfaceInput, id_: str = "CDKTF") -> App:
    """Initialize the CDKTF app and all the stacks."""
    app = App(outdir=os.environ.get("ER_OUTDIR", None))
    Stack(app, id_, ai_input)
    return app


def main() -> None:
    """Proper entry point for the CDKTF app."""
    app = init_cdktf_app(get_ai_input())
    app.synth()


if __name__ == "__main__":
    main()
