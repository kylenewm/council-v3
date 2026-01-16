"""
Configuration management for Agent Eval system.

Supports:
- Programmatic configuration via dataclasses
- YAML file loading
- Environment variable overrides
- Sensible defaults for all settings
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Dict
import os

import yaml

from .exceptions import ConfigurationError


@dataclass
class AgentConfig:
    """Configuration for the agent being tested."""

    type: str = "claude"  # claude, openai, custom
    model: str = "claude-sonnet-4-20250514"
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    def __post_init__(self):
        if self.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ConfigurationError("max_retries cannot be negative")
        if self.retry_delay_seconds <= 0:
            raise ConfigurationError("retry_delay_seconds must be positive")


@dataclass
class WatchdogConfig:
    """Configuration for the watchdog evaluator (LLM that evaluates agent output)."""

    enabled: bool = True
    model: str = "claude-sonnet-4-20250514"
    timeout_seconds: int = 60
    temperature: float = 0.0  # Deterministic for reproducibility

    def __post_init__(self):
        if self.timeout_seconds <= 0:
            raise ConfigurationError("watchdog timeout_seconds must be positive")
        if not 0.0 <= self.temperature <= 1.0:
            raise ConfigurationError("temperature must be between 0.0 and 1.0")


@dataclass
class PersistenceConfig:
    """Configuration for result persistence."""

    enabled: bool = True
    database_path: Path = field(
        default_factory=lambda: Path.home() / ".council" / "agent_eval.db"
    )
    keep_history_days: int = 90

    def __post_init__(self):
        # Convert string to Path if needed
        if isinstance(self.database_path, str):
            self.database_path = Path(self.database_path)

        if self.keep_history_days <= 0:
            raise ConfigurationError("keep_history_days must be positive")


@dataclass
class ExecutionConfig:
    """Configuration for execution environment."""

    parallel_scenarios: int = 1  # Start sequential, increase later
    cleanup_on_success: bool = True
    cleanup_on_failure: bool = False  # Keep for debugging
    working_dir: Optional[Path] = None  # None = use temp dir

    def __post_init__(self):
        # Convert string to Path if needed
        if isinstance(self.working_dir, str):
            self.working_dir = Path(self.working_dir)

        if self.parallel_scenarios <= 0:
            raise ConfigurationError("parallel_scenarios must be positive")


@dataclass
class Config:
    """Master configuration for Agent Eval system.

    Example usage:
        # Defaults
        config = Config.default()

        # From file
        config = Config.from_yaml(Path("config.yaml"))

        # Programmatic
        config = Config(
            agent=AgentConfig(timeout_seconds=600),
            watchdog=WatchdogConfig(enabled=False),
        )
    """

    agent: AgentConfig = field(default_factory=AgentConfig)
    watchdog: WatchdogConfig = field(default_factory=WatchdogConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If file not found or invalid
        """
        if not path.exists():
            raise ConfigurationError(f"Config file not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {path}: {e}")

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary."""
        return cls(
            agent=AgentConfig(**data.get("agent", {})),
            watchdog=WatchdogConfig(**data.get("watchdog", {})),
            persistence=PersistenceConfig(**data.get("persistence", {})),
            execution=ExecutionConfig(**data.get("execution", {})),
        )

    @classmethod
    def default(cls) -> "Config":
        """Create configuration with all defaults."""
        return cls()

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration with environment variable overrides.

        Supported environment variables:
        - AGENT_EVAL_TIMEOUT: Agent timeout in seconds
        - AGENT_EVAL_MODEL: Agent model to use
        - AGENT_EVAL_WATCHDOG_ENABLED: Enable/disable watchdog (true/false)
        - AGENT_EVAL_DB_PATH: Path to SQLite database
        - AGENT_EVAL_PARALLEL: Number of parallel scenarios
        """
        config = cls.default()

        # Agent overrides
        if timeout := os.environ.get("AGENT_EVAL_TIMEOUT"):
            config.agent.timeout_seconds = int(timeout)
        if model := os.environ.get("AGENT_EVAL_MODEL"):
            config.agent.model = model

        # Watchdog overrides
        if watchdog_enabled := os.environ.get("AGENT_EVAL_WATCHDOG_ENABLED"):
            config.watchdog.enabled = watchdog_enabled.lower() == "true"

        # Persistence overrides
        if db_path := os.environ.get("AGENT_EVAL_DB_PATH"):
            config.persistence.database_path = Path(db_path)

        # Execution overrides
        if parallel := os.environ.get("AGENT_EVAL_PARALLEL"):
            config.execution.parallel_scenarios = int(parallel)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary (for serialization)."""
        return {
            "agent": {
                "type": self.agent.type,
                "model": self.agent.model,
                "timeout_seconds": self.agent.timeout_seconds,
                "max_retries": self.agent.max_retries,
                "retry_delay_seconds": self.agent.retry_delay_seconds,
            },
            "watchdog": {
                "enabled": self.watchdog.enabled,
                "model": self.watchdog.model,
                "timeout_seconds": self.watchdog.timeout_seconds,
                "temperature": self.watchdog.temperature,
            },
            "persistence": {
                "enabled": self.persistence.enabled,
                "database_path": str(self.persistence.database_path),
                "keep_history_days": self.persistence.keep_history_days,
            },
            "execution": {
                "parallel_scenarios": self.execution.parallel_scenarios,
                "cleanup_on_success": self.execution.cleanup_on_success,
                "cleanup_on_failure": self.execution.cleanup_on_failure,
                "working_dir": str(self.execution.working_dir)
                if self.execution.working_dir
                else None,
            },
        }

    def to_yaml(self) -> str:
        """Serialize config to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False)
