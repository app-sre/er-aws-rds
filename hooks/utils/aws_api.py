from typing import TYPE_CHECKING

from boto3 import Session

if TYPE_CHECKING:
    from mypy_boto3_rds import RDSClient
    from mypy_boto3_rds.type_defs import FilterTypeDef
from mypy_boto3_rds.type_defs import (
    BlueGreenDeploymentTypeDef,
    DBInstanceTypeDef,
    DBParameterGroupTypeDef,
)

from hooks.utils.models import CreateBlueGreenDeploymentParams


class AWSApi:
    """AWS Api Class"""

    def __init__(self, region_name: str | None = None) -> None:
        self.session = Session(region_name=region_name)
        self.rds_client: RDSClient = self.session.client("rds")

    def is_rds_engine_version_available(self, engine: str, version: str) -> bool:
        """Gets the available versions for an Rds engine"""
        data = (
            self.get_rds_client()
            .describe_db_engine_versions(Engine=engine, EngineVersion=version)
            .get("DBEngineVersions", [])
        )

        return len(data) == 1 and data[0].get("EngineVersion") == version

    def get_rds_valid_update_versions(self, engine: str, version: str) -> set[str]:
        """Gets the valid update versions"""
        data = self.rds_client.describe_db_engine_versions(
            Engine=engine, EngineVersion=version, IncludeAll=True
        )

        if data["DBEngineVersions"] and len(data["DBEngineVersions"]) == 1:
            return {
                item.get("EngineVersion", "-1")
                for item in data["DBEngineVersions"][0].get("ValidUpgradeTarget", [])
            }
        return set[str]()

    def get_rds_parameter_groups(self, engine: str) -> set[str]:
        """Gets the existing parameter groups by engine"""
        filters: list[FilterTypeDef] = [
            {"Name": "db-parameter-group-family", "Values": [engine]},
        ]
        resp = self.rds_client.describe_db_parameter_groups(Filters=filters)
        return {group["DBParameterGroupName"] for group in resp["DBParameterGroups"]}

    def get_db_parameter_group(self, name: str) -> DBParameterGroupTypeDef | None:
        """Get DB parameter group info"""
        data = self.rds_client.describe_db_parameter_groups(DBParameterGroupName=name)
        return data["DBParameterGroups"][0] if data["DBParameterGroups"] else None

    def get_db_instance(self, identifier: str) -> DBInstanceTypeDef | None:
        """Get DB instance info"""
        data = self.rds_client.describe_db_instances(DBInstanceIdentifier=identifier)
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
        kwargs = {"BlueGreenDeploymentIdentifier": identifier}
        if delete_target is not None:
            kwargs["DeleteTarget"] = delete_target
        self.rds_client.delete_blue_green_deployment(**kwargs)
