"""
Timeout management for Agent Eval.

Provides utilities for enforcing timeouts on operations,
both synchronous (via signals) and asynchronous (via asyncio).
"""

import asyncio
import signal
import functools
from contextlib import contextmanager
from typing import Any, Callable, TypeVar, Optional
import logging

from ..exceptions import TimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutManager:
    """Manages timeouts for operations.

    Provides both synchronous and asynchronous timeout utilities.

    Usage (sync):
        with TimeoutManager.timeout(30, "Operation timed out"):
            slow_operation()

    Usage (async):
        result = await TimeoutManager.with_timeout(
            async_operation(),
            30,
            "Operation timed out"
        )
    """

    @staticmethod
    @contextmanager
    def timeout(seconds: int, message: str = "Operation timed out"):
        """Context manager for synchronous timeout using signals.

        Note: Only works on Unix-like systems and in the main thread.
        For cross-platform or thread-safe timeouts, use subprocess
        with timeout parameter.

        Args:
            seconds: Timeout in seconds
            message: Error message if timeout occurs

        Yields:
            None

        Raises:
            TimeoutError: If the operation times out

        Example:
            with TimeoutManager.timeout(30, "Database query timed out"):
                result = database.query(sql)
        """
        def handler(signum, frame):
            raise TimeoutError(message)

        # Store the old handler
        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            # Cancel alarm and restore handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    @staticmethod
    async def with_timeout(
        coro,
        seconds: int,
        message: str = "Operation timed out",
    ) -> Any:
        """Execute a coroutine with timeout.

        Args:
            coro: Coroutine to execute
            seconds: Timeout in seconds
            message: Error message if timeout occurs

        Returns:
            The result of the coroutine

        Raises:
            TimeoutError: If the operation times out

        Example:
            result = await TimeoutManager.with_timeout(
                fetch_data(),
                60,
                "API request timed out"
            )
        """
        try:
            return await asyncio.wait_for(coro, timeout=seconds)
        except asyncio.TimeoutError:
            raise TimeoutError(message)

    @staticmethod
    def timeout_decorator(
        seconds: int,
        message: Optional[str] = None,
    ) -> Callable:
        """Decorator for adding timeout to a function.

        Args:
            seconds: Timeout in seconds
            message: Optional error message (defaults to function name)

        Returns:
            Decorated function

        Example:
            @TimeoutManager.timeout_decorator(30)
            def slow_function():
                # ...
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            msg = message or f"{func.__name__} timed out after {seconds}s"

            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                with TimeoutManager.timeout(seconds, msg):
                    return func(*args, **kwargs)

            return wrapper

        return decorator
