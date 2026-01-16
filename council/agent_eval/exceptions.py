"""
Exception hierarchy for the Agent Eval system.

All exceptions inherit from AgentEvalError for easy catching.
"""


class AgentEvalError(Exception):
    """Base exception for agent eval system.

    All other exceptions in this module inherit from this,
    allowing callers to catch any agent eval error with a single except.
    """
    pass


class ScenarioError(AgentEvalError):
    """Error loading or validating a scenario.

    Raised when:
    - YAML parsing fails
    - Required fields are missing
    - Validation fails (e.g., invalid difficulty)
    - File not found
    """
    pass


class EnvironmentError(AgentEvalError):
    """Error setting up or cleaning the execution environment.

    Raised when:
    - Temp directory creation fails
    - File creation fails
    - Git init fails
    - Setup commands fail
    - Cleanup fails
    """
    pass


class ExecutionError(AgentEvalError):
    """Error executing the agent.

    Raised when:
    - Agent CLI not found
    - Agent process fails to start
    - Agent returns unexpected error
    - All retry attempts exhausted
    """
    pass


class TimeoutError(AgentEvalError):
    """Agent execution timed out.

    Raised when:
    - Agent execution exceeds configured timeout
    - Setup commands exceed timeout
    - Verification commands exceed timeout
    """
    pass


class VerificationError(AgentEvalError):
    """Error during verification (not a verification failure).

    Raised when:
    - Verification command crashes (not just exits non-zero)
    - Custom verifier script fails to parse
    - File system access errors during checks

    Note: A verification check returning 'failed' is NOT this error.
    This is for errors in the verification process itself.
    """
    pass


class WatchdogError(AgentEvalError):
    """Error during watchdog evaluation.

    Raised when:
    - LLM API call fails
    - Response parsing fails completely
    - Rate limiting or authentication errors
    """
    pass


class PersistenceError(AgentEvalError):
    """Error persisting results.

    Raised when:
    - Database connection fails
    - Write operations fail
    - Migration errors
    """
    pass


class ConfigurationError(AgentEvalError):
    """Error in configuration.

    Raised when:
    - Config file not found
    - Config validation fails
    - Required config missing
    """
    pass
