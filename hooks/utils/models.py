from pydantic import BaseModel, Field, field_serializer


class CreateBlueGreenDeploymentParams(BaseModel):
    """CreateBlueGreenDeploymentParams"""

    name: str = Field(serialization_alias="BlueGreenDeploymentName")
    source_arn: str = Field(serialization_alias="Source")
    allocated_storage: int | None = Field(
        serialization_alias="TargetAllocatedStorage", default=None
    )
    engine_version: str | None = Field(
        serialization_alias="TargetEngineVersion", default=None
    )
    instance_class: str | None = Field(
        serialization_alias="TargetDBInstanceClass", default=None
    )
    iops: int | None = Field(serialization_alias="TargetIops", default=None)
    parameter_group_name: str | None = Field(
        serialization_alias="TargetDBParameterGroupName", default=None
    )
    storage_throughput: int | None = Field(
        serialization_alias="TargetStorageThroughput", default=None
    )
    storage_type: str | None = Field(
        serialization_alias="TargetStorageType", default=None
    )
    tags: dict[str, str] | None = Field(serialization_alias="Tags", default=None)

    @field_serializer("tags")
    def serialize_tags(  # noqa: PLR6301
        self,
        tags: dict[str, str] | None,
    ) -> list[dict[str, str]] | None:
        """Serialize tags as AWS API format"""
        if tags is None:
            return None
        return [{"Key": k, "Value": v} for k, v in tags.items()]
