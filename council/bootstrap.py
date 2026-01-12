"""Bootstrap Claude Code files from a project plan."""

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from .client import Message, get_client


# =============================================================================
# PROMPTS FOR FILE GENERATION
# =============================================================================

CLAUDE_MD_PROMPT = """Based on this project plan and invariants, generate a CLAUDE.md file for Claude Code.

PLAN:
{plan_content}

INVARIANTS:
{invariants}

Generate a CLAUDE.md that includes:
1. Project name and brief overview (from the plan)
2. **INVARIANTS section** - copy the invariants exactly, this is critical
3. Tech stack and key dependencies mentioned
4. Testing commands appropriate for the stack (e.g., pytest, npm test)
5. Key files that will be created
6. A "Slash Commands" table showing: /test, /done, /review, /ship, /save
7. References to STATE.md and LOG.md

Format it like this structure:
```
# Project: [name]

## Overview
[brief description]

## Invariants (ALWAYS FOLLOW)
[copy invariants here - these are non-negotiable rules]

## Stack
[tech stack]

## Testing
```bash
[test commands]
```

## Slash Commands
| Command | What |
|---------|------|
| /test | Run tests |
...

## Key Files
[list of main files]

## Context
- STATE.md: Current work
- LOG.md: History
```

Output ONLY the markdown content, no code fences around the whole thing."""

STATE_MD_PROMPT = """Based on this project plan, generate a STATE.md file for tracking current work.

PLAN:
{plan_content}

Generate a STATE.md that includes:
1. "Current Work" section with the first 2-3 tasks from the plan
2. "Blockers" section (probably "None" initially)
3. "Recent Decisions" table (extract key decisions from plan, or leave empty)

Format:
```
# STATE.md

## Current Work
- [ ] First task from plan
- [ ] Second task

## Blockers
None.

## Recent Decisions
| Decision | Why |
|----------|-----|
| [if any from plan] | [rationale] |
```

Output ONLY the markdown content."""

INVARIANTS_PROMPT = """Based on this project plan, generate a list of INVARIANTS - rules that must ALWAYS or NEVER be followed when implementing this project.

PLAN:
{plan_content}

Generate invariants that are:
1. Specific to this project (not generic advice)
2. Actionable and enforceable
3. About code quality, security, architecture, or patterns

Format as a markdown list with categories:

```
## Code Style
- Always use X for Y
- Never do Z

## Security
- Always validate user input before...
- Never store secrets in...

## Architecture
- All X must have Y
- Never bypass the Z layer

## Testing
- Every new feature must have...
- Never merge without...
```

Output 10-15 specific invariants. Be concrete, not generic.
Output ONLY the markdown content, no wrapper fences."""


# =============================================================================
# DEFAULT SETTINGS
# =============================================================================

DEFAULT_SETTINGS = {
    "permissions": {
        "allow": [
            "Bash(pytest *)",
            "Bash(python *)",
            "Bash(git status)",
            "Bash(git diff *)",
            "Bash(git log *)",
            "Bash(git add *)",
            "Bash(git commit *)",
            "Bash(git push *)",
        ]
    },
    "hooks": {
        "Notification": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "osascript -e 'display notification \"Claude needs attention\" with title \"Claude Code\"'"
                    }
                ]
            }
        ]
    }
}


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def generate_invariants(plan_content: str, verbose: bool = False) -> str:
    """Generate project invariants from plan using LLM."""
    if verbose:
        print("Generating invariants...")

    client = get_client()
    prompt = INVARIANTS_PROMPT.format(plan_content=plan_content)

    result = client.complete(
        [
            Message(role="system", content="You generate project invariants - strict rules that must always be followed."),
            Message(role="user", content=prompt),
        ],
        model="anthropic/claude-sonnet-4",
        timeout=60.0,
    )

    return result.content


def generate_claude_md(plan_content: str, invariants: str, verbose: bool = False) -> str:
    """Generate CLAUDE.md content using LLM."""
    if verbose:
        print("Generating CLAUDE.md...")

    client = get_client()
    prompt = CLAUDE_MD_PROMPT.format(plan_content=plan_content, invariants=invariants)

    result = client.complete(
        [
            Message(role="system", content="You generate Claude Code project configuration files."),
            Message(role="user", content=prompt),
        ],
        model="anthropic/claude-sonnet-4",
        timeout=60.0,
    )

    return result.content


def generate_state_md(plan_content: str, verbose: bool = False) -> str:
    """Generate STATE.md content using LLM."""
    if verbose:
        print("Generating STATE.md...")

    client = get_client()
    prompt = STATE_MD_PROMPT.format(plan_content=plan_content)

    result = client.complete(
        [
            Message(role="system", content="You generate Claude Code project tracking files."),
            Message(role="user", content=prompt),
        ],
        model="anthropic/claude-sonnet-4",
        timeout=60.0,
    )

    return result.content


def generate_log_md() -> str:
    """Generate LOG.md with initial entry."""
    today = date.today().isoformat()
    return f"""# LOG.md

> Append-only. Never edit old entries.

---

## {today}

### Project Setup

Project initialized from council plan.
"""


def copy_commands_from_home(dest_dir: Path, verbose: bool = False) -> bool:
    """Copy slash commands from ~/.claude/commands/ if they exist.

    Returns True if any commands were copied.
    """
    home_commands = Path.home() / ".claude" / "commands"
    if not home_commands.exists():
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)

    commands = ["test", "test-cycle", "done", "review", "ship", "save", "summarize", "commit"]
    copied = False

    for cmd in commands:
        src = home_commands / f"{cmd}.md"
        if src.exists():
            dest = dest_dir / f"{cmd}.md"
            if not dest.exists():
                shutil.copy(src, dest)
                if verbose:
                    print(f"  Copied {cmd}.md")
                copied = True

    return copied


def generate_claude_files(plan_content: str, verbose: bool = False) -> None:
    """Generate all Claude Code files from a plan.

    Creates:
    - CLAUDE.md (LLM-generated with invariants)
    - STATE.md (LLM-generated)
    - LOG.md (template)
    - .claude/settings.json
    - .claude/commands/*.md (copied from ~/.claude/commands/ if available)
    """
    # Generate invariants first (1 API call)
    invariants = generate_invariants(plan_content, verbose=verbose)

    # Generate LLM files (2 API calls)
    claude_md = generate_claude_md(plan_content, invariants, verbose=verbose)
    state_md = generate_state_md(plan_content, verbose=verbose)
    log_md = generate_log_md()

    # Write main files
    Path("CLAUDE.md").write_text(claude_md)
    Path("STATE.md").write_text(state_md)
    Path("LOG.md").write_text(log_md)

    if verbose:
        print("Wrote CLAUDE.md, STATE.md, LOG.md")

    # Create .claude directory
    claude_dir = Path(".claude")
    claude_dir.mkdir(exist_ok=True)

    # Write settings.json
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps(DEFAULT_SETTINGS, indent=2))
    if verbose:
        print("Wrote .claude/settings.json")

    # Copy commands from home if available
    commands_dir = claude_dir / "commands"
    if copy_commands_from_home(commands_dir, verbose=verbose):
        if verbose:
            print("Copied slash commands from ~/.claude/commands/")
    else:
        if verbose:
            print("No commands found in ~/.claude/commands/, skipping")
