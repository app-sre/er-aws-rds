from typing import Any

from mypy_boto3_rds.type_defs import DBInstanceTypeDef, DBParameterGroupTypeDef

from er_aws_rds.input import AppInterfaceInput


def deep_merge(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries recursively"""
    return dict1.copy() | {
        key: (
            deep_merge(dict1[key], value)
            if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict)
            else value
        )
        for key, value in dict2.items()
    }


DEFAULT_PARAMETER_GROUP = {
    "name": "test-pg",
    "family": "postgres14",
    "description": "Parameter Group for PostgreSQL 14",
    "parameters": [
        {
            "name": "log_statement",
            "value": "none",
            "apply_method": "pending-reboot",
        },
        {
            "name": "log_min_duration_statement",
            "value": "-1",
            "apply_method": "pending-reboot",
        },
        {
            "name": "log_min_duration_statement",
            "value": "60000",
            "apply_method": "pending-reboot",
        },
    ],
}

DEFAULT_DATA = {
    "data": {
        "engine": "postgres",
        "engine_version": "14.6",
        "name": "postgres",
        "username": "postgres",
        "instance_class": "db.t3.micro",
        "allocated_storage": 20,
        "auto_minor_version_upgrade": False,
        "skip_final_snapshot": True,
        "backup_retention_period": 7,
        "storage_type": "gp2",
        "multi_az": False,
        "ca_cert_identifier": "rds-ca-rsa2048-g1",
        "publicly_accessible": True,
        "apply_immediately": True,
        "identifier": "test-rds",
        "parameter_group": DEFAULT_PARAMETER_GROUP,
        "output_resource_name": "test-rds-credentials",
        "ca_cert": {
            "path": "app-interface/global/rds-ca-cert",
            "field": "us-east-1",
            "version": 2,
            "q_format": None,
        },
        "output_prefix": "prefixed-test-rds",
        "region": "us-east-1",
        "tags": {
            "app": "external-resources-poc",
            "cluster": "appint-ex-01",
            "environment": "stage",
            "managed_by_integration": "external_resources",
            "namespace": "external-resources-poc",
        },
        "default_tags": [{"tags": {"app": "app-sre-infra"}}],
    },
    "provision": {
        "provision_provider": "aws",
        "provisioner": "app-int-example-01",
        "provider": "rds",
        "identifier": "test-rds",
        "target_cluster": "appint-ex-01",
        "target_namespace": "external-resources-poc",
        "target_secret_name": "test-rds-credentials",
        "module_provision_data": {
            "tf_state_bucket": "external-resources-terraform-state-dev",
            "tf_state_region": "us-east-1",
            "tf_state_dynamodb_table": "external-resources-terraform-lock",
            "tf_state_key": "aws/app-int-example-01/rds/test-rds/terraform.tfstate",
        },
    },
}

DEFAULT_TARGET = {
    "engine_version": "15.7",
    "instance_class": "db.t4g.micro",
    "iops": 3000,
    "parameter_group": {
        "name": "pg15",
        "family": "postgres15",
    },
    "allocated_storage": 20,
    "storage_type": "gp3",
    "storage_throughput": 125,
}

DEFAULT_RDS_INSTANCE: DBInstanceTypeDef = {
    "DBInstanceArn": "some-arn",
    "DBInstanceIdentifier": "test-rds",
    "DBParameterGroups": [
        {
            "DBParameterGroupName": "test-rds-pg15",
            "ParameterApplyStatus": "in-sync",
        }
    ],
    "Iops": 3000,
    "EngineVersion": "15.7",
    "DBInstanceClass": "db.t4g.micro",
    "StorageType": "gp3",
    "AllocatedStorage": 20,
    "StorageThroughput": 125,
    "DBInstanceStatus": "available",
}

DEFAULT_TARGET_RDS_INSTANCE: DBInstanceTypeDef = {
    "DBInstanceArn": "some-arn-new",
    "DBInstanceStatus": "available",
    "DBInstanceIdentifier": "test-rds-new",
}


DEFAULT_TARGET_PARAMETER_GROUP: DBParameterGroupTypeDef = {
    "DBParameterGroupName": "test-rds-pg15",
    "DBParameterGroupFamily": "postgres15",
}


def input_data(additional_data: dict[str, Any] | None = None) -> dict:
    """Returns a parsed JSON input as dict"""
    return deep_merge(DEFAULT_DATA, additional_data or {})


def input_object(additional_data: dict[str, Any] | None = None) -> AppInterfaceInput:
    """Returns an AppInterfaceInput object"""
    return AppInterfaceInput.model_validate(input_data(additional_data))
