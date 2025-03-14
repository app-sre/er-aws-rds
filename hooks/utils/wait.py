import time
from collections.abc import Callable
from logging import Logger


def wait_for(
    condition: Callable[[], bool],
    *,
    logger: Logger,
    timeout: int | None = None,
    interval: int = 60,
) -> None:
    """
    Wait for a condition to be met.

    Args:
        condition (Callable[[], bool]): A callable that returns True when the condition is met.
        logger (Logger): A logger instance for logging messages.
        timeout (int | None): The maximum time to wait in seconds. If None, wait indefinitely.
        interval (int): The time to wait between checks in seconds. Default is 60 seconds.
    """
    start_time = time.time()
    logger.info("Waiting for condition to be met...")
    while not condition():
        elapsed = int(time.time() - start_time)
        if timeout is not None and elapsed >= timeout:
            raise TimeoutError(
                f"Condition not met within the timeout period: {timeout} seconds."
            )
        logger.info(f"Still waiting... [{elapsed}s elapsed]")
        time.sleep(interval)
