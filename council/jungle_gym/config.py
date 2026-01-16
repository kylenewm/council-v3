"""
Configuration for Jungle Gym test harness.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class AgentConfig:
    """Configuration for a single test agent."""
    name: str
    pane_id: str
    worktree: Path
    mode: str = "default"  # default, strict, sandbox, plan, review
    auto_audit: bool = False
    transcript_path: Optional[Path] = None
    invariants_path: Optional[Path] = None

    def is_experimental(self) -> bool:
        """Returns True if this agent has enforcement enabled."""
        return self.mode == "strict" and self.auto_audit


@dataclass
class OutputConfig:
    """Configuration for test output."""
    json_path: Path = field(default_factory=lambda: Path.home() / "jungle_gym" / "results" / "latest.json")
    markdown_path: Path = field(default_factory=lambda: Path.home() / "jungle_gym" / "results" / "latest.md")
    history_dir: Path = field(default_factory=lambda: Path.home() / "jungle_gym" / "results" / "history")


@dataclass
class JungleGymConfig:
    """Main configuration for the test harness."""
    control_agent: AgentConfig
    experimental_agent: AgentConfig
    output: OutputConfig = field(default_factory=OutputConfig)
    timeout_seconds: int = 300  # 5 minutes per scenario per agent
    poll_interval: float = 2.0  # How often to check agent state

    @classmethod
    def from_yaml(cls, path: Path) -> "JungleGymConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        agents = data.get("agents", {})
        output_data = data.get("output", {})

        control = AgentConfig(
            name=agents.get("A", {}).get("name", "Control"),
            pane_id=agents.get("A", {}).get("pane_id", "%0"),
            worktree=Path(agents.get("A", {}).get("worktree", "~/jungle_gym/sandbox_a")).expanduser(),
            mode=agents.get("A", {}).get("mode", "default"),
            auto_audit=agents.get("A", {}).get("auto_audit", False),
            transcript_path=Path(agents["A"]["transcript_path"]).expanduser() if agents.get("A", {}).get("transcript_path") else None,
            invariants_path=Path(agents["A"]["invariants_path"]).expanduser() if agents.get("A", {}).get("invariants_path") else None,
        )

        experimental = AgentConfig(
            name=agents.get("B", {}).get("name", "Experimental"),
            pane_id=agents.get("B", {}).get("pane_id", "%1"),
            worktree=Path(agents.get("B", {}).get("worktree", "~/jungle_gym/sandbox_b")).expanduser(),
            mode=agents.get("B", {}).get("mode", "strict"),
            auto_audit=agents.get("B", {}).get("auto_audit", True),
            transcript_path=Path(agents["B"]["transcript_path"]).expanduser() if agents.get("B", {}).get("transcript_path") else None,
            invariants_path=Path(agents["B"]["invariants_path"]).expanduser() if agents.get("B", {}).get("invariants_path") else None,
        )

        output = OutputConfig(
            json_path=Path(output_data.get("json_path", "~/jungle_gym/results/latest.json")).expanduser(),
            markdown_path=Path(output_data.get("markdown_path", "~/jungle_gym/results/latest.md")).expanduser(),
            history_dir=Path(output_data.get("history_dir", "~/jungle_gym/results/history")).expanduser(),
        )

        return cls(
            control_agent=control,
            experimental_agent=experimental,
            output=output,
            timeout_seconds=data.get("timeout_seconds", 300),
            poll_interval=data.get("poll_interval", 2.0),
        )

    @classmethod
    def default(cls) -> "JungleGymConfig":
        """Create default configuration for quick testing."""
        return cls(
            control_agent=AgentConfig(
                name="Control",
                pane_id="%0",
                worktree=Path.home() / "jungle_gym" / "sandbox_a",
                mode="default",
                auto_audit=False,
            ),
            experimental_agent=AgentConfig(
                name="Experimental",
                pane_id="%1",
                worktree=Path.home() / "jungle_gym" / "sandbox_b",
                mode="strict",
                auto_audit=True,
                transcript_path=Path.home() / ".council" / "transcripts" / "agent_b.jsonl",
                invariants_path=Path.home() / ".council" / "invariants.yaml",
            ),
        )
