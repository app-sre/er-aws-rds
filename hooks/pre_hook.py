#!/usr/bin/env python

import logging
import os

from external_resources_io.input import parse_model, read_input_from_file

from er_aws_rds.input import AppInterfaceInput
from hooks.utils.aws_api import AWSApi
from hooks.utils.blue_green_deployment_manager import BlueGreenDeploymentManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("botocore")
logger.setLevel(logging.ERROR)


def main() -> None:
    """Manage Blue/Green Deployment"""
    app_interface_input = parse_model(AppInterfaceInput, read_input_from_file())
    aws_api = AWSApi(config_options={"region_name": app_interface_input.data.region})
    dry_run = os.environ.get("DRY_RUN") == "True"
    manager = BlueGreenDeploymentManager(
        aws_api=aws_api, app_interface_input=app_interface_input, dry_run=dry_run
    )
    manager.run()


if __name__ == "__main__":
    main()
