"""
shared/retry.py — Exponential backoff decorator using tenacity.

Usage:
    from shared.retry import with_retry

    @with_retry()
    def call_api():
        ...

    @with_retry(attempts=5, min_wait=1, max_wait=30)
    def call_flaky_service():
        ...
"""

import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def with_retry(
    exceptions: tuple = (Exception,),
    attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 8,
):
    """
    Returns a tenacity retry decorator with exponential backoff.

    Args:
        exceptions: Tuple of exception types to retry on. Default: all exceptions.
        attempts:   Maximum number of attempts before raising. Default: 3.
        min_wait:   Minimum wait time in seconds between retries. Default: 2.
        max_wait:   Maximum wait time in seconds between retries. Default: 8.
    """
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
