from cdktf import Testing
from cdktf_cdktf_provider_aws.db_instance import DbInstance
from cdktf_cdktf_provider_aws.db_parameter_group import DbParameterGroup

from er_aws_rds.rds import Stack

from .conftest import input_object


class TestMain:
    """Main test class"""

    input = input_object()
    stack = Stack(Testing.app(), "CDKTF", input)
    synthesized = Testing.synth(stack)

    def test_should_contain_rds_instance(self) -> None:
        """Test should_contain_rds_instance"""
        assert Testing.to_have_resource_with_properties(
            self.synthesized,
            DbInstance.TF_RESOURCE_TYPE,
            {
                "identifier": "test-rds",
                "engine": "postgres",
                "db_name": "postgres",
                "allocated_storage": 20,
                "parameter_group_name": "test-rds-postgres-14",
                "tags": {
                    "app": "external-resources-poc",
                    "cluster": "appint-ex-01",
                    "environment": "stage",
                    "managed_by_integration": "external_resources",
                    "namespace": "external-resources-poc",
                },
            },
        )

    def test_should_contain_parameter_group(self) -> None:
        """Test should_contain_parameter_group"""
        assert Testing.to_have_resource_with_properties(
            self.synthesized,
            DbParameterGroup.TF_RESOURCE_TYPE,
            {
                "name": "test-rds-postgres-14",
                "family": "postgres14",
            },
            # Test fails if I add the parameters. It works for 1 parameter
            # but fails if I set the full list
        )
