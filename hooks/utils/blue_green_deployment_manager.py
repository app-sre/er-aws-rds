from er_aws_rds.input import AppInterfaceInput
from hooks.utils.aws_api import AWSApi


class BlueGreenDeploymentManager:
    """Blue/Green Deployment Manager"""

    def __init__(
        self,
        aws_api: AWSApi,
        app_interface_input: AppInterfaceInput,
        dry_run: bool,  # noqa: FBT001
    ) -> None:
        """Init"""
        self.aws_api = aws_api
        self.app_interface_input = app_interface_input
        self.dry_run = dry_run

    def run(self) -> None:
        """Manage Blue/Green Deployment"""
        pass
