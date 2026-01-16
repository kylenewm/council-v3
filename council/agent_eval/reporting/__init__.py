"""
Reporting layer for Agent Eval.

Handles:
- Report generation
- Multiple output formats (JSON, Markdown, HTML)
- Run comparison
"""

from .reporter import Report, Reporter, ComparisonReporter

__all__ = [
    "Report",
    "Reporter",
    "ComparisonReporter",
]
