"""
Retry management with exponential backoff for Agent Eval.

Provides utilities for retrying operations that may fail transiently,
with configurable retry counts and backoff strategies.
"""

import asyncio
import time
import functools
from typing import Callable, TypeVar, Optional, Tuple, Type, Union
import logging

from ..config import AgentConfig
from ..exceptions import ExecutionError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryManager:
    """Manages retries with exponential backoff.

    Provides both synchronous and asynchronous retry utilities.

    Usage:
        retry = RetryManager(config)
        result = retry.execute_with_retry(
            lambda: risky_operation(),
            operation_name="database query"
        )

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (doubles each time)
    """

    def __init__(self, config: AgentConfig):
        """Initialize retry manager.

        Args:
            config: Agent configuration containing retry settings
        """
        self.max_retries = config.max_retries
        self.base_delay = config.retry_delay_seconds

    def execute_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str = "operation",
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> T:
        """Execute function with retry logic (synchronous).

        Args:
            func: Function to execute (no arguments)
            operation_name: Name for logging
            retryable_exceptions: Exception types to retry on

        Returns:
            Result of the function

        Raises:
            ExecutionError: If all retries exhausted

        Example:
            result = retry.execute_with_retry(
                lambda: api.call(),
                "API call",
                (ConnectionError, TimeoutError)
            )
        """
        last_error: Optional[Exception] = None
        attempts = self.max_retries + 1  # +1 for initial attempt

        for attempt in range(attempts):
            try:
                return func()

            except retryable_exceptions as e:
                last_error = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{attempts}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"{operation_name} failed after {attempts} attempts: {e}"
                    )

        raise ExecutionError(
            f"{operation_name} failed after {attempts} attempts"
        ) from last_error

    async def execute_with_retry_async(
        self,
        func: Callable[[], T],
        operation_name: str = "operation",
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> T:
        """Execute function with retry logic (asynchronous).

        Args:
            func: Async function to execute (no arguments)
            operation_name: Name for logging
            retryable_exceptions: Exception types to retry on

        Returns:
            Result of the function

        Raises:
            ExecutionError: If all retries exhausted

        Example:
            result = await retry.execute_with_retry_async(
                lambda: api.call_async(),
                "API call"
            )
        """
        last_error: Optional[Exception] = None
        attempts = self.max_retries + 1

        for attempt in range(attempts):
            try:
                return await func()

            except retryable_exceptions as e:
                last_error = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{attempts}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"{operation_name} failed after {attempts} attempts: {e}"
                    )

        raise ExecutionError(
            f"{operation_name} failed after {attempts} attempts"
        ) from last_error

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Uses exponential backoff: delay = base_delay * 2^attempt

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        return self.base_delay * (2 ** attempt)

    @staticmethod
    def retry_decorator(
        max_retries: int = 3,
        base_delay: float = 1.0,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> Callable:
        """Decorator for adding retry logic to a function.

        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries
            retryable_exceptions: Exception types to retry on

        Returns:
            Decorated function

        Example:
            @RetryManager.retry_decorator(max_retries=5)
            def flaky_function():
                # ...
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                last_error: Optional[Exception] = None
                attempts = max_retries + 1

                for attempt in range(attempts):
                    try:
                        return func(*args, **kwargs)
                    except retryable_exceptions as e:
                        last_error = e
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                f"{func.__name__} failed (attempt {attempt + 1}/{attempts}), "
                                f"retrying in {delay:.1f}s: {e}"
                            )
                            time.sleep(delay)

                raise ExecutionError(
                    f"{func.__name__} failed after {attempts} attempts"
                ) from last_error

            return wrapper

        return decorator


class RetryContext:
    """Context for tracking retry state across operations.

    Useful when you want to track retries across multiple related operations
    and implement circuit breaker patterns.
    """

    def __init__(self, max_total_retries: int = 10):
        """Initialize retry context.

        Args:
            max_total_retries: Maximum total retries across all operations
        """
        self.max_total_retries = max_total_retries
        self.total_retries = 0
        self.operations: list = []

    def record_retry(self, operation_name: str, error: Exception) -> None:
        """Record a retry attempt.

        Args:
            operation_name: Name of the operation
            error: The exception that triggered the retry
        """
        self.total_retries += 1
        self.operations.append({
            "operation": operation_name,
            "error": str(error),
            "retry_number": self.total_retries,
        })

    def can_retry(self) -> bool:
        """Check if more retries are allowed.

        Returns:
            True if under the total retry limit
        """
        return self.total_retries < self.max_total_retries

    @property
    def retry_summary(self) -> str:
        """Get a summary of retries.

        Returns:
            Human-readable summary
        """
        if not self.operations:
            return "No retries"

        return f"{self.total_retries} retries: " + ", ".join(
            f"{op['operation']} ({op['retry_number']})"
            for op in self.operations
        )
