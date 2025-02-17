from collections.abc import Sequence
from typing import Any, Literal

from external_resources_io.input import AppInterfaceProvision
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from er_aws_rds.errors import RDSLogicalReplicationError

ENHANCED_MONITORING_ROLE_NAME_MAX_LENGTH = 64


class EventNotification(BaseModel):
    "db_event_subscription for SNS"

    destination: str = Field(..., alias="destination")
    source_type: str | None = Field(default="all", alias="source_type")
    event_categories: list[str] | None = Field(..., alias="event_categories")


class DataClassification(BaseModel):
    """DataClassification check. NOT Implemented"""

    loss_impact: str | None = Field(..., alias="loss_impact")


class VaultSecret(BaseModel):
    """VaultSecret spec"""

    path: str
    field: str
    version: int | None = 1
    q_format: str | None = Field(default=None)

    def to_vault_ref(self) -> str:
        """Generates a JSON vault ref"""
        json = self.model_dump_json()
        return "__vault__:" + json


class Parameter(BaseModel):
    """db_parameter_group_parameter"""

    name: str
    value: Any
    apply_method: Literal["immediate", "pending-reboot"] | None = Field(default=None)

    @field_validator("value", mode="before")
    @classmethod
    def transform(cls, v: Any) -> str:  # noqa: ANN401
        """values come as int|str|float|bool from App-Interface, but terraform only allows str"""
        return str(v)


class ParameterGroup(BaseModel):
    "db_parameter_group"

    family: str
    name: str | None = None
    description: str | None = None
    parameters: list[Parameter] | None = Field(default=None)


class ReplicaSource(BaseModel):
    "AppInterface ReplicaSource"

    region: str
    identifier: str


class BlueGreenDeploymentTarget(BaseModel):
    "AppInterface BlueGreenDeployment.Target"

    allocated_storage: int | None = None
    engine_version: str | None = None
    instance_class: str | None = None
    iops: int | None = None
    parameter_group: ParameterGroup | None = None
    storage_throughput: int | None = None
    storage_type: str | None = None


class BlueGreenDeployment(BaseModel):
    "AppInterface BlueGreenDeployment"

    enabled: bool
    switchover: bool
    delete: bool
    target: BlueGreenDeploymentTarget | None = None


class DBInstanceTimeouts(BaseModel):
    "DBInstance timeouts"

    create: str | None = None
    delete: str | None = None
    update: str | None = None


class BlueGreenUpdate(BaseModel):
    enabled: bool = False


class RdsAppInterface(BaseModel):
    """AppInterface Input parameters

    Class with Input parameters from App-Interface that are not part of the
    Terraform aws_db_instance object.
    """

    # Name is deprecated. db_name is included as a computed_field
    name: str | None = Field(
        max_length=63, pattern=r"^[a-zA-Z][a-zA-Z0-9_]+$", exclude=True, default=None
    )
    aws_partition: str | None = Field(default="aws", exclude=True)
    region: str = Field(exclude=True)
    parameter_group: ParameterGroup | None = Field(default=None, exclude=True)
    old_parameter_group: ParameterGroup | None = Field(default=None, exclude=True)
    blue_green_deployment: BlueGreenDeployment | None = Field(
        default=None, exclude=True
    )
    replica_source: ReplicaSource | None = Field(default=None, exclude=True)
    enhanced_monitoring: bool | None = Field(default=None, exclude=True)
    reset_password: str | None = Field(default="", exclude=True)
    ca_cert: VaultSecret | None = Field(default=None, exclude=True)
    annotations: str | None = Field(default=None, exclude=True)
    event_notifications: list[EventNotification] | None = Field(
        default=None, exclude=True
    )
    data_classification: DataClassification | None = Field(default=None, exclude=True)
    # This value is use to override the db_name set in the outputs
    output_resource_db_name: str | None = Field(default=None, exclude=True)
    # Output_resource_name is redundant
    output_resource_name: str | None = Field(default=None, exclude=True)
    # output_prefix is not necessary since now each resources has it own state.
    output_prefix: str = Field(exclude=True)
    tags: dict[str, Any] | None = Field(default=None, exclude=True)
    default_tags: Sequence[dict[str, Any]] | None = Field(default=None, exclude=True)


class Rds(RdsAppInterface):
    """RDS Input parameters

    Input parameters from App-Interface that are part
    of the Terraform aws_db_instance object. Generally speaking, these
    parameters come from the rds defaults attributes.

    The class only defines the parameters that are changed or tweaked in the module, other
    attributes are included as extra_attributes.
    """

    model_config = ConfigDict(extra="allow")
    identifier: str
    engine: str = "postgres"
    allow_major_version_upgrade: bool | None = False
    availability_zone: str | None = None
    monitoring_interval: int | None = None
    monitoring_role_arn: str | None = None
    apply_immediately: bool | None = False
    multi_az: bool | None = False
    replicate_source_db: str | None = None
    snapshot_identifier: str | None = None
    backup_retention_period: int | None = None
    db_subnet_group_name: str | None = None
    storage_encrypted: bool | None = None
    kms_key_id: str | None = None
    username: str | None = None
    # _password is not in the input, the field is used to populate the random password
    password: str | None = None
    parameter_group_name: str | None = None
    timeouts: DBInstanceTimeouts | None = None
    blue_green_update: BlueGreenUpdate | None = None

    @property
    def enhanced_monitoring_role_name(self) -> str:
        """Id/Name for enhanced monitoring role"""
        base_name = self.identifier + "-enhanced-monitoring"
        return (
            base_name
            if len(base_name) <= ENHANCED_MONITORING_ROLE_NAME_MAX_LENGTH
            else self.identifier[:61].rstrip("-") + "-em"
        )

    @computed_field
    def db_name(self) -> str | None:
        """db_name"""
        return self.name

    @model_validator(mode="after")
    def az_belongs_to_region(self) -> "Rds":
        """Check if a the AZ belongs to a region"""
        if self.availability_zone:
            az_region = self.availability_zone[:-1]
            if self.region != az_region:
                msg = "Availability_zone does not belong to the region"
                raise ValueError(
                    msg,
                    self.availability_zone,
                    self.region,
                )
        return self

    @model_validator(mode="after")
    def unset_az_if_multi_region(self) -> "Rds":
        """Remove az for multi_region instances"""
        if self.multi_az:
            self.availability_zone = None
        return self

    @model_validator(mode="after")
    def unset_replica_or_snapshot_not_allowed_attrs(self) -> "Rds":
        """
        Some attributes are not allowed if the instance is a read replica or is created from a snapshot.

        engine is not removed because it's needed in the plan validation.
        """
        if self.replica_source or self.replicate_source_db or self.snapshot_identifier:
            self.username = None
            self.password = None
            self.name = None
            self.allocated_storage = None
        return self

    @model_validator(mode="after")
    def replication(self) -> "Rds":
        """replica_source and replicate_source_db are mutually excluive"""
        if not self.replica_source:
            return self

        if self.replicate_source_db:
            msg = "Only one of replicate_source_db or replica_source can be defined"
            raise ValueError(msg)
        if self.replica_source.region != self.region:
            # Cross-region replication or different db_subnet_group_name.
            # The ARN must be set in the replicate_source_db attribute for these cases.
            # The ARN is resolved in the module using a Datasource.
            # The Datasource required attributes are fed with the replica_source variable.
            if not self.db_subnet_group_name:
                msg = "db_subnet_group_name must be defined for cross-region replicas"
                raise ValueError(msg)
            if self.storage_encrypted and not self.kms_key_id:
                msg = "storage_encrypted ignored for cross-region read replica. Set kms_key_id"
                raise ValueError(msg)
        else:
            # Same-region replication. The instance identifier must be supplied int the replicate_source_db attr.
            self.replicate_source_db = self.replica_source.identifier
            self.db_subnet_group_name = None

        # No backup for replicas
        self.backup_retention_period = 0
        return self

    @model_validator(mode="after")
    def validate_parameter_group_parameters(self) -> "Rds":
        """Validate that every parameter complies with our requirements"""
        if not self.parameter_group:
            return self
        for parameter in self.parameter_group.parameters or []:
            if (
                parameter.name == "rds.logical_replication"
                and parameter.apply_method != "pending-reboot"
            ):
                msg = "rds.logical_replication must be set to pending-reboot"
                raise RDSLogicalReplicationError(msg)
        return self

    @model_validator(mode="after")
    def parameter_groups(self) -> "Rds":
        """
        Sets the right parameter group names. The instance identifier is used as prefix on each pg.

        This way each instance will have its own parameter group, without re-using them on multiple instances.
        """
        if self.parameter_group:
            name = f"{self.identifier}-{self.parameter_group.name or 'pg'}"
            self.parameter_group.name = name
            self.parameter_group_name = name

        if self.old_parameter_group and not self.parameter_group:
            msg = "old_parameter_group must be used with parameter_group. old_parameter_group is only used for RDS major version upgrades"
            raise ValueError(msg)

        if self.old_parameter_group and self.parameter_group:
            self.old_parameter_group.name = (
                f"{self.identifier}-{self.old_parameter_group.name or 'pg'}"
            )

            if self.old_parameter_group.name == self.parameter_group.name:
                msg = "Parameter group and old parameter group have the same name. Assign a name to the new parameter group"
                raise ValueError(msg)

        if (
            self.blue_green_deployment
            and self.blue_green_deployment.target
            and (pg := self.blue_green_deployment.target.parameter_group)
        ):
            pg.computed_pg_name = f"{self.identifier}-{pg.name or 'pg'}"
            if not self.blue_green_deployment.enabled:
                parameter_group_names = {
                    group.computed_pg_name
                    for group in [self.parameter_group, self.old_parameter_group]
                    if group
                }
                if pg.computed_pg_name in parameter_group_names:
                    raise ValueError(
                        "Blue/Green Deployment Parameter Group name already exist"
                    )
        return self

    @property
    def is_read_replica(self) -> bool:
        """Returns true if the instance is a read replica"""
        return self.replica_source is not None or self.replicate_source_db is not None

    @model_validator(mode="after")
    def enhanced_monitoring_attributes(self) -> "Rds":
        """
        Enhanced monitoring validation:

        * If em is disabled, related parameters are removed.
        * If em is enabled and no monitoring_inverval specificied, set the default value (60)
        * If em is enabled and monitoring_interval is set to 0. Raise Validation Error
        """
        if self.enhanced_monitoring and self.monitoring_interval == 0:
            raise ValueError(
                "Monitoring interval can not be 0 when enhanced monitoring is enabled."
                "Set enhanced_monitoring=0 to disable Enhanced monitoring."
            )
        if self.enhanced_monitoring and self.monitoring_interval is None:
            self.monitoring_interval = 60

        if not self.enhanced_monitoring:
            self.monitoring_interval = None
            self.monitoring_role_arn = None

        return self

    @model_validator(mode="after")
    def kms_key_id_remove_alias_prefix(self) -> "Rds":
        """Remove alias prefix from kms_key_id"""
        if self.kms_key_id:
            self.kms_key_id = self.kms_key_id.removeprefix("alias/")
        return self

    @model_validator(mode="after")
    def blue_green_update_requirements(self) -> "Rds":
        if (
            self.blue_green_update
            and self.blue_green_update.enabled
            and self.snapshot_identifier
        ):
            raise ValueError(
                "Blue/Green updates can not be enabled when snapshot_identifier is set"
            )
        return self


class AppInterfaceInput(BaseModel):
    """The input model class"""

    data: Rds
    provision: AppInterfaceProvision


class TerraformModuleData(BaseModel):
    """Variables to feed the Terraform Module"""

    ai_input: AppInterfaceInput = Field(exclude=True)

    @computed_field
    def rds_instance(self) -> Rds | None:
        """The db_instance variable"""
        return self.ai_input.data

    @computed_field
    def parameter_groups(self) -> list[ParameterGroup] | None:
        """Parameter groups to create"""
        return [
            pg
            for pg in [
                self.ai_input.data.parameter_group,
                self.ai_input.data.old_parameter_group,
            ]
            if pg
        ]

    @computed_field
    def reset_password(self) -> str | None:
        """Terraform password variable"""
        return self.ai_input.data.reset_password

    @computed_field
    def enhanced_monitoring_role(self) -> str | None:
        """Sets the enhanced monitoring terraform variable if needed"""
        if (
            self.ai_input.data.enhanced_monitoring
            and self.ai_input.data.monitoring_role_arn is None
        ):
            return self.ai_input.data.enhanced_monitoring_role_name
        return None

    @computed_field
    def replica_source(self) -> ReplicaSource | None:
        """ReplicaSource terraform variable"""
        return self.ai_input.data.replica_source

    @computed_field
    def ca_cert(self) -> str | None:
        if self.ai_input.data.ca_cert:
            return self.ai_input.data.ca_cert.to_vault_ref()
        return None

    @computed_field
    def tags(self) -> dict[str, Any] | None:
        """Tags"""
        return self.ai_input.data.tags

    @computed_field
    def region(self) -> str:
        """Tags"""
        return self.ai_input.data.region

    @computed_field
    def provision(self) -> AppInterfaceProvision:
        """Provision"""
        return self.ai_input.provision
