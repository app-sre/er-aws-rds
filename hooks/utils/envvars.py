import logging
import os
import sys
from collections.abc import Iterable
from enum import Enum

logger = logging.getLogger(__name__)


class RuntimeEnvVars(Enum):
    TF_VARS_FILE = "TF_VARS_FILE"
    TERRAFORM_CMD = "TERRAFORM_CMD"
    PLAN_FILE_JSON = "PLAN_FILE_JSON"

    def get(self, default: str | None = None) -> str | None:
        return os.getenv(self.value, default)

    def is_set(self) -> bool:
        return self.value in os.environ

    @classmethod
    def missing(cls, vars_: Iterable["RuntimeEnvVars"]) -> list[str]:
        return [var.value for var in vars_ if not var.is_set()]

    @classmethod
    def check(cls, required_vars: Iterable["RuntimeEnvVars"]) -> None:
        """Checks if required environment variables are set, logs an error, and exits if any are missing."""
        missing_vars = cls.missing(required_vars)
        if missing_vars:
            logger.error(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
            sys.exit(1)
