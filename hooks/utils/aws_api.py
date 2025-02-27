from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from boto3 import Session
from botocore.config import Config
from mypy_boto3_rds import RDSClient

if TYPE_CHECKING:
    from mypy_boto3_rds.type_defs import FilterTypeDef


class AWSApi:
    """AWS Api Class"""

    def __init__(self, config_options: Mapping[str, Any]) -> None:
        self.session = Session()
        self.config = Config(**config_options)

    def get_rds_client(self) -> RDSClient:
        """Gets a boto RDS client"""
        return self.session.client("rds", config=self.config)

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
        data = self.get_rds_client().describe_db_engine_versions(
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
        resp = self.get_rds_client().describe_db_parameter_groups(Filters=filters)
        return {group["DBParameterGroupName"] for group in resp["DBParameterGroups"]}
