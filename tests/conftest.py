"""Shared fixtures for dispatcher tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from council.dispatcher.simple import Agent, Config


@pytest.fixture
def sample_agent():
    """Create a sample agent for testing."""
    return Agent(
        id=1,
        pane_id="%0",
        name="Test Agent",
        worktree=Path("/tmp/test-worktree"),
        state="unknown",
    )


@pytest.fixture
def sample_config(sample_agent):
    """Create a sample config for testing."""
    return Config(
        agents={1: sample_agent},
        poll_interval=2.0,
        fifo_path=Path("/tmp/test.fifo"),
    )


@pytest.fixture
def multi_agent_config():
    """Config with multiple agents."""
    return Config(
        agents={
            1: Agent(id=1, pane_id="%0", name="Agent 1"),
            2: Agent(id=2, pane_id="%1", name="Agent 2"),
            3: Agent(id=3, pane_id="%2", name="Agent 3"),
        },
        poll_interval=2.0,
    )


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for tmux commands."""
    with patch("council.dispatcher.simple.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock


# === Enforcement system fixtures ===

import subprocess
import shutil

ENFORCEMENT_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "repos"


def create_mock_repo(name: str, files: dict, invariants: dict = None):
    """Create a mock git repo with specified files."""
    repo_path = ENFORCEMENT_FIXTURES_DIR / name

    # Clean existing
    if repo_path.exists():
        shutil.rmtree(repo_path)

    repo_path.mkdir(parents=True, exist_ok=True)

    # Init git
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True)

    # Create invariants config
    council_dir = repo_path / ".council"
    council_dir.mkdir(exist_ok=True)

    inv_content = invariants or {
        "forbidden_paths": ["*.env", "credentials/*", ".secrets/*"],
        "protected_paths": ["api/schema.py", "migrations/*", "config/production.yaml"]
    }

    inv_yaml = "forbidden_paths:\n"
    for p in inv_content.get("forbidden_paths", []):
        inv_yaml += f'  - "{p}"\n'
    inv_yaml += "\nprotected_paths:\n"
    for p in inv_content.get("protected_paths", []):
        inv_yaml += f'  - "{p}"\n'

    (council_dir / "invariants.yaml").write_text(inv_yaml)

    # Initial commit
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial commit"], cwd=repo_path, check=True)

    # Add test files
    for filepath, content in files.items():
        full_path = repo_path / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    # Commit the files
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Add test files"], cwd=repo_path, check=True)

    return repo_path


@pytest.fixture(scope="session", autouse=True)
def setup_enforcement_repos():
    """Create all mock git repos before enforcement tests run."""

    # clean_diff - no violations
    create_mock_repo("clean_diff", {
        "main.py": "print('hello')",
        "utils.py": "def helper(): pass",
    })

    # forbidden_touched - touches credentials/*
    create_mock_repo("forbidden_touched", {
        "main.py": "print('main')",
        "credentials/api_key.txt": "API_KEY=secret123",
    })

    # protected_touched - touches api/schema.py
    create_mock_repo("protected_touched", {
        "main.py": "print('main')",
        "api/schema.py": "class Schema: pass",
    })

    # mixed_violations - multiple issues
    create_mock_repo("mixed_violations", {
        "main.py": "print('main')",
        ".env": "SECRET=xxx",
        "credentials/config.yaml": "key: value",
        "api/schema.py": "class Schema: pass",
    })

    yield
