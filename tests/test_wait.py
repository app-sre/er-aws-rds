from collections.abc import Iterator
from logging import Logger
from unittest.mock import MagicMock, Mock, call, create_autospec, patch

import pytest

from hooks.utils.wait import wait_for


@pytest.fixture
def mock_time() -> Iterator[Mock]:
    """Patch time"""
    with patch("hooks.utils.wait.time") as m:
        yield m


@pytest.fixture
def mock_logging() -> Mock:
    """Mock logging"""
    return create_autospec(Logger)


def test_wait_for_condition_met(
    mock_time: Mock,
    mock_logging: Mock,
) -> None:
    """Test wait_for with condition met"""
    condition = MagicMock(return_value=True)

    wait_for(
        condition=condition,
        logger=mock_logging,
        timeout=None,
        interval=1,
    )

    mock_logging.info.assert_called_with("Waiting for condition to be met...")
    condition.assert_called_once_with()
    mock_time.sleep.assert_not_called()


def test_wait_for_condition_met_later(
    mock_time: Mock,
    mock_logging: Mock,
) -> None:
    """Test wait_for with condition met later"""
    mock_time.time.side_effect = [0, 1]
    condition = MagicMock()
    condition.side_effect = [False, True]

    wait_for(
        condition=condition,
        logger=mock_logging,
        timeout=None,
        interval=1,
    )

    mock_logging.info.assert_has_calls([
        call("Waiting for condition to be met..."),
        call("Still waiting... [1s elapsed]"),
    ])
    assert condition.call_count == 2
    mock_time.sleep.assert_called_once_with(1)


def test_wait_for_condition_met_timeout(
    mock_time: Mock,
    mock_logging: Mock,
) -> None:
    """Test wait_for with condition timeout"""
    mock_time.time.side_effect = [0, 1, 2]
    condition = MagicMock()
    condition.side_effect = [False, False]

    with pytest.raises(
        TimeoutError, match=r"Condition not met within the timeout period: 2 seconds."
    ):
        wait_for(
            condition=condition,
            logger=mock_logging,
            timeout=2,
            interval=1,
        )

    mock_logging.info.assert_has_calls([
        call("Waiting for condition to be met..."),
        call("Still waiting... [1s elapsed]"),
    ])
    assert condition.call_count == 2
    mock_time.sleep.assert_called_once_with(1)
