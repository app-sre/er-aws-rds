from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

from hooks.post_run import main


@pytest.fixture
def mock_should_rerun() -> Iterator[Mock]:
    """Patch mark_rerun"""
    with patch("hooks.post_run.should_rerun") as m:
        yield m


@pytest.fixture
def mock_logging() -> Iterator[Mock]:
    """Patch logging"""
    with patch("hooks.post_run.logging") as m:
        yield m


@pytest.mark.parametrize(
    ("should_rerun", "expected_exit_code", "log_message"),
    [
        (True, 1, "rerun marker exists, exiting with error"),
        (False, 0, "run completed successfully"),
    ],
)
def test_post_run_hook_when_no_rerun_marker(
    mock_should_rerun: Mock,
    mock_logging: Mock,
    *,
    should_rerun: bool,
    expected_exit_code: int,
    log_message: str,
) -> None:
    """Test post_run_hook when no rerun marker"""
    mock_should_rerun.return_value = should_rerun

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == expected_exit_code
    mock_should_rerun.assert_called_once_with()
    mock_logging.getLogger.return_value.info.assert_called_once_with(log_message)
