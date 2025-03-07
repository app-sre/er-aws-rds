#!/usr/bin/env python

from external_resources_io.input import parse_model, read_input_from_file

from er_aws_rds.input import AppInterfaceInput
from hooks.utils.aws_api import AWSApi
from hooks.utils.blue_green_deployment_manager import BlueGreenDeploymentManager
from hooks.utils.logger import setup_logging
from hooks.utils.runtime import is_dry_run


def main() -> None:
    """Manage Blue/Green Deployment"""
    setup_logging()
    app_interface_input = parse_model(AppInterfaceInput, read_input_from_file())
    aws_api = AWSApi(region_name=app_interface_input.data.region)
    manager = BlueGreenDeploymentManager(
        aws_api=aws_api,
        app_interface_input=app_interface_input,
        dry_run=is_dry_run(),
    )
    manager.run()


if __name__ == "__main__":
    main()
