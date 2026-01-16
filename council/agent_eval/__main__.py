"""
Entry point for running Agent Eval as a module.

Usage:
    python -m council.agent_eval run scenarios/
    python -m council.agent_eval list scenarios/
    python -m council.agent_eval validate scenarios/
"""

from .api.cli import main

if __name__ == "__main__":
    main()
