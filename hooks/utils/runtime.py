import os


def is_dry_run() -> bool:
    """Checks if the run is a DRY_RUN"""
    return os.getenv("DRY_RUN", "True") == "True"
