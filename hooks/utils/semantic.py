from semver import Version


def parse_semver(version: str) -> Version:
    """
    Parse a version string into a semver.Version object.

    Args:
        version (str): The version string to parse.

    Returns:
        Version: A semver.Version object representing the parsed version.
    """
    return Version.parse(version, optional_minor_and_patch=True)
