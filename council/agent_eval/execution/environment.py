"""
Isolated execution environment for Agent Eval.

The Environment class creates and manages temporary directories
where scenarios run. This provides isolation between tests and
clean starting states.
"""

import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

from ..models.scenario import Scenario, SetupSpec
from ..exceptions import EnvironmentError
from ..config import ExecutionConfig

logger = logging.getLogger(__name__)


class Environment:
    """Isolated execution environment for a scenario.

    Creates a temporary directory, sets up files and dependencies,
    and cleans up afterward.

    Usage:
        # As context manager (recommended)
        with Environment(scenario, config) as env:
            workdir = env.workdir
            # Run agent in workdir...

        # Manual management
        env = Environment(scenario, config)
        env.setup()
        try:
            # Do work...
        finally:
            env.cleanup()

    Attributes:
        scenario: The scenario to set up
        config: Execution configuration
        workdir: Path to the working directory (available after setup)
    """

    def __init__(
        self,
        scenario: Scenario,
        config: ExecutionConfig,
        workdir: Optional[Path] = None,
    ):
        """Initialize environment.

        Args:
            scenario: The scenario to set up
            config: Execution configuration
            workdir: Optional explicit working directory (creates temp dir if None)
        """
        self.scenario = scenario
        self.config = config
        self._workdir = workdir
        self._created = False  # Whether we created the directory
        self._setup_complete = False

    @property
    def workdir(self) -> Path:
        """Get the working directory.

        Raises:
            EnvironmentError: If environment not initialized
        """
        if self._workdir is None:
            raise EnvironmentError("Environment not initialized. Call setup() first.")
        return self._workdir

    def setup(self) -> Path:
        """Create and set up the environment.

        Creates files, initializes git, installs dependencies as specified
        in the scenario's setup spec.

        Returns:
            Path to the working directory

        Raises:
            EnvironmentError: If setup fails
        """
        try:
            # Create working directory if not provided
            if self._workdir is None:
                prefix = f"agent_eval_{self.scenario.id}_"
                self._workdir = Path(tempfile.mkdtemp(prefix=prefix))
                self._created = True

            logger.info(f"Setting up environment in {self._workdir}")

            # Create files
            self._create_files()

            # Initialize git if requested
            if self.scenario.setup.git_init:
                self._init_git()

            # Install npm dependencies if requested
            if self.scenario.setup.npm_install:
                self._npm_install()

            # Install pip packages if requested
            for package in self.scenario.setup.pip_install:
                self._pip_install(package)

            # Run custom setup commands
            for cmd in self.scenario.setup.commands:
                self._run_setup_command(cmd, shell=True)

            self._setup_complete = True
            logger.info(f"Environment setup complete: {self._workdir}")
            return self._workdir

        except EnvironmentError:
            # Re-raise environment errors
            self.cleanup()
            raise
        except Exception as e:
            logger.error(f"Environment setup failed: {e}")
            self.cleanup()
            raise EnvironmentError(f"Failed to setup environment: {e}") from e

    def _create_files(self) -> None:
        """Create files specified in the setup."""
        for file_spec in self.scenario.setup.files:
            file_path = self._workdir / file_spec.path

            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            file_path.write_text(file_spec.content, encoding=file_spec.encoding)
            logger.debug(f"Created file: {file_path}")

    def _init_git(self) -> None:
        """Initialize a git repository."""
        logger.debug("Initializing git repository")

        # git init
        self._run_setup_command(["git", "init"])

        # Configure git user (required for commits)
        self._run_setup_command(
            ["git", "config", "user.email", "agent-eval@test.local"]
        )
        self._run_setup_command(["git", "config", "user.name", "Agent Eval"])

        # Initial commit if there are files
        if list(self._workdir.iterdir()):
            self._run_setup_command(["git", "add", "."])
            self._run_setup_command(["git", "commit", "-m", "Initial commit"])

    def _npm_install(self) -> None:
        """Run npm install."""
        logger.debug("Running npm install")

        # Check if package.json exists
        if not (self._workdir / "package.json").exists():
            logger.warning("npm_install requested but no package.json found")
            return

        self._run_setup_command(["npm", "install"], timeout=120)

    def _pip_install(self, package: str) -> None:
        """Install a pip package."""
        logger.debug(f"Installing pip package: {package}")
        self._run_setup_command(["pip", "install", package], timeout=60)

    def _run_setup_command(
        self,
        cmd,
        shell: bool = False,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess:
        """Run a setup command with error handling.

        Args:
            cmd: Command to run (list or string if shell=True)
            shell: Whether to run through shell
            timeout: Timeout in seconds

        Returns:
            CompletedProcess result

        Raises:
            EnvironmentError: If command fails critically
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=self._workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
            )

            if result.returncode != 0:
                # Log warning but don't necessarily fail
                # Some setup commands are best-effort
                cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
                logger.warning(
                    f"Setup command exited with {result.returncode}: {cmd_str}\n"
                    f"stderr: {result.stderr}"
                )

            return result

        except subprocess.TimeoutExpired:
            cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
            raise EnvironmentError(f"Setup command timed out after {timeout}s: {cmd_str}")

        except FileNotFoundError as e:
            cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
            raise EnvironmentError(f"Command not found: {cmd_str}: {e}")

        except Exception as e:
            cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
            raise EnvironmentError(f"Setup command failed: {cmd_str}: {e}")

    def cleanup(self) -> None:
        """Clean up the environment.

        Runs teardown commands then removes the working directory
        (if we created it).
        """
        if not self._workdir or not self._workdir.exists():
            return

        # Run teardown commands
        for cmd in self.scenario.teardown_commands:
            try:
                subprocess.run(
                    cmd,
                    cwd=self._workdir,
                    shell=True,
                    timeout=30,
                    capture_output=True,
                )
            except Exception as e:
                logger.warning(f"Teardown command failed: {cmd}: {e}")

        # Remove directory if we created it
        if self._created:
            try:
                shutil.rmtree(self._workdir)
                logger.debug(f"Cleaned up environment: {self._workdir}")
            except Exception as e:
                logger.error(f"Failed to cleanup environment: {e}")

    def __enter__(self) -> "Environment":
        """Context manager entry - sets up environment."""
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - conditionally cleans up.

        Cleanup behavior depends on config:
        - cleanup_on_success: Remove on successful exit
        - cleanup_on_failure: Remove on exception
        """
        should_cleanup = (
            (exc_type is None and self.config.cleanup_on_success)
            or (exc_type is not None and self.config.cleanup_on_failure)
        )

        if should_cleanup:
            self.cleanup()
        elif self._workdir:
            logger.info(f"Keeping environment for debugging: {self._workdir}")


class EnvironmentFactory:
    """Factory for creating environments with shared configuration.

    Useful when running multiple scenarios with the same config.
    """

    def __init__(self, config: ExecutionConfig):
        """Initialize factory with config."""
        self.config = config

    def create(
        self,
        scenario: Scenario,
        workdir: Optional[Path] = None,
    ) -> Environment:
        """Create an environment for a scenario.

        Args:
            scenario: The scenario to set up
            workdir: Optional explicit working directory

        Returns:
            Environment instance (not yet set up)
        """
        return Environment(scenario, self.config, workdir)
