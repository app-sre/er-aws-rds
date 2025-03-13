from typing import TYPE_CHECKING

from boto3 import Session

if TYPE_CHECKING:
    from mypy_boto3_rds import RDSClient
    from mypy_boto3_rds.type_defs import (
        DeleteBlueGreenDeploymentRequestRequestTypeDef,
        FilterTypeDef,
    )
from mypy_boto3_rds.type_defs import (
    BlueGreenDeploymentTypeDef,
    DBInstanceTypeDef,
    DBParameterGroupTypeDef,
    ParameterOutputTypeDef,
    UpgradeTargetTypeDef,
)

from hooks.utils.models import CreateBlueGreenDeploymentParams


class AWSApi:
    """AWS Api Class"""

    def __init__(self, region_name: str | None = None) -> None:
        self.session = Session(region_name=region_name)
        self.rds_client: RDSClient = self.session.client("rds")

    def is_rds_engine_version_available(self, engine: str, version: str) -> bool:
        """Checks if the engine version is available"""
        data = self.rds_client.describe_db_engine_versions(
            Engine=engine,
            EngineVersion=version,
        ).get("DBEngineVersions", [])

        return len(data) == 1 and data[0].get("EngineVersion") == version

    def get_rds_valid_upgrade_targets(
        self,
        engine: str,
        version: str,
    ) -> dict[str, UpgradeTargetTypeDef]:
        """Get RDS valid upgrade targets"""
        data = self.rds_client.describe_db_engine_versions(
            Engine=engine,
            EngineVersion=version,
            IncludeAll=True,
        )
        if not data.get("DBEngineVersions"):
            return {}

        return {
            item["EngineVersion"]: item
            for item in data["DBEngineVersions"][0].get("ValidUpgradeTarget", [])
        }

    def get_blue_green_deployment_valid_upgrade_targets(
        self,
        engine: str,
        version: str,
    ) -> dict[str, UpgradeTargetTypeDef]:
        """Get Blue/Green Deployment valid upgrade targets"""
        current_version_as_target: UpgradeTargetTypeDef = {
            "Engine": engine,
            "EngineVersion": version,
            "IsMajorVersionUpgrade": False,
        }
        candidate_upgrade_targets = {
            version: current_version_as_target
        } | self.get_rds_valid_upgrade_targets(engine, version)
        filters: list[FilterTypeDef] = [
            {
                "Name": "engine-version",
                "Values": list(candidate_upgrade_targets.keys()),
            },
        ]
        data = self.rds_client.describe_db_engine_versions(
            Engine=engine,
            Filters=filters,
        )
        if not data["DBEngineVersions"]:
            return {}
        available_versions = {
            item["EngineVersion"] for item in data["DBEngineVersions"]
        }
        return {
            version: item
            for version, item in candidate_upgrade_targets.items()
            if version in available_versions
        }

    def get_db_parameter_group(self, name: str) -> DBParameterGroupTypeDef | None:
        """Get DB parameter group info"""
        data = self.rds_client.describe_db_parameter_groups(DBParameterGroupName=name)
        return data["DBParameterGroups"][0] if data["DBParameterGroups"] else None

    def get_db_parameters(
        self,
        parameter_group_name: str,
        parameter_names: list[str],
    ) -> dict[str, ParameterOutputTypeDef]:
        """Get DB parameters"""
        data = self.rds_client.describe_db_parameters(
            DBParameterGroupName=parameter_group_name,
            Filters=[
                {
                    "Name": "parameter-name",
                    "Values": parameter_names,
                }
            ],
        )
        return {item["ParameterName"]: item for item in data["Parameters"] or []}

    def get_db_instance(self, identifier: str) -> DBInstanceTypeDef | None:
        """Get DB instance info"""
        try:
            data = self.rds_client.describe_db_instances(
                DBInstanceIdentifier=identifier
            )
        except self.rds_client.exceptions.DBInstanceNotFoundFault:
            return None
        return data["DBInstances"][0] if data["DBInstances"] else None

    def delete_db_instance(self, identifier: str) -> None:
        self.rds_client.delete_db_instance(
            DBInstanceIdentifier=identifier,
            SkipFinalSnapshot=True,
        )

    def create_blue_green_deployment(
        self, params: CreateBlueGreenDeploymentParams
    ) -> None:
        """Create Blue/Green Deployment"""
        kwargs = params.model_dump(by_alias=True, exclude_none=True)
        self.rds_client.create_blue_green_deployment(**kwargs)

    def get_blue_green_deployment(self, name: str) -> BlueGreenDeploymentTypeDef | None:
        """Get Blue/Green Deployment"""
        data = self.rds_client.describe_blue_green_deployments(
            Filters=[
                {
                    "Name": "blue-green-deployment-name",
                    "Values": [name],
                }
            ]
        )
        return data["BlueGreenDeployments"][0] if data["BlueGreenDeployments"] else None

    def switchover_blue_green_deployment(self, identifier: str) -> None:
        """Switchover Blue/Green Deployment"""
        self.rds_client.switchover_blue_green_deployment(
            BlueGreenDeploymentIdentifier=identifier
        )

    def delete_blue_green_deployment(
        self,
        identifier: str,
        *,
        delete_target: bool | None = None,
    ) -> None:
        """
        Delete Blue/Green Deployment

        :param identifier: Blue/Green Deployment Identifier
        :param delete_target: Specifies whether to delete the resources in the green environment.
                              You can not specify this option if the blue/green deployment
                              status is SWITCHOVER_COMPLETED.
        """
        kwargs: DeleteBlueGreenDeploymentRequestRequestTypeDef = {
            "BlueGreenDeploymentIdentifier": identifier
        }
        if delete_target is not None:
            kwargs["DeleteTarget"] = delete_target
        self.rds_client.delete_blue_green_deployment(**kwargs)
