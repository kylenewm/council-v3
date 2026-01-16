"""
API layer for Agent Eval.

External interfaces:
- CLI (command line interface)
- SDK (Python programmatic interface)
- HTTP API (future)
"""

from .cli import main as cli_main

__all__ = [
    "cli_main",
]
