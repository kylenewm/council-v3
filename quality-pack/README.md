# Quality Pack for Claude Code

A portable, templated quality system that enforces consistent development practices across all your projects.

## What This Is

Quality Pack provides two layers of infrastructure for Claude Code:

1. **Layer 1: Global Defaults** - Rules and modes that apply to ALL projects
2. **Layer 2: Project Overrides** - Per-project customizations

This enables:
- Consistent quality standards across all work
- Mode-based workflows (strict, plan, review, etc.)
- Task-specific templates (/bug, /feature, /refactor)
- Structured verification before marking work "done"

## Quick Start

```bash
# Clone or copy quality-pack to your machine
cd quality-pack

# Install global configs (safe, doesn't touch projects)
./install.sh

# Set up a specific project
cd /path/to/your/project
/path/to/quality-pack/install.sh --project
```

## What Gets Installed

### Global (`~/.claude/`, `~/.council/`)

```
~/.claude/
└── CLAUDE.md              # Quality rules for all projects

~/.council/
└── hooks/
    ├── inject.sh          # Main injection router
    ├── auto-inject.sh     # Global mindset rules
    ├── type-check.sh      # Language-aware type checking
    ├── notify-rich.sh     # Notification on stop
    └── modes/
        ├── production.sh  # Right > Fast
        ├── strict.sh      # Evidence over narrative
        ├── plan.sh        # Design before building
        ├── review.sh      # Adversarial critique
        ├── sandbox.sh     # Quick POC iteration
        ├── scrappy.sh     # Rapid validation
        ├── critical.sh    # High stakes
        └── riper.sh       # 5-phase workflow
```

### Project (`.claude/`, `.council/`)

```
.claude/
├── settings.json          # Permissions and hooks
├── commands/
│   ├── test.md           # Run tests
│   ├── commit.md         # Stage and commit
│   ├── done.md           # Verify before complete
│   ├── ship.md           # Test, commit, push, PR
│   ├── save.md           # Save context
│   ├── review.md         # Code review (subagent)
│   ├── inject.md         # Mode switching
│   ├── bug.md            # Bug fix workflow
│   ├── feature.md        # Feature workflow
│   ├── refactor.md       # Refactor workflow
│   └── setup.md          # Project setup
└── agents/
    ├── strict.md         # Production mindset
    ├── code-architect.md # Architecture specialist
    └── verify-app.md     # Verification specialist

.council/
├── mode                  # Current mode (production, strict, etc)
└── invariants.yaml       # Forbidden/protected paths
```

## Modes

Switch modes with `/inject <mode>`:

| Mode | When to Use |
|------|-------------|
| `production` | Default. Right > Fast. Real users depend on this. |
| `strict` | Production code with DONE_REPORT requirements |
| `plan` | Complex features needing upfront design |
| `review` | Adversarial context-blind code review |
| `sandbox` | POC/experiments with fixtures |
| `scrappy` | Bulk operations, rapid validation |
| `critical` | Highest stakes, maximum thoroughness |
| `riper` | 5-phase: Research-Innovate-Plan-Execute-Review |

### Mode Precedence

Local (`.council/mode`) overrides global (`~/.council/current_inject.txt`)

```bash
# Set global mode (affects all projects)
/inject strict

# Set local mode (only this project)
/inject local strict
```

## Slash Commands

### Core Workflow

| Command | What It Does |
|---------|--------------|
| `/test` | Auto-detect test framework and run tests |
| `/commit` | Stage all changes and commit with message |
| `/done` | Verify tests pass, lint passes, requirements met |
| `/ship` | Full workflow: verify, commit, push, create PR |
| `/save` | Save context to STATE.md and LOG.md |
| `/review` | Spawn subagent for context-blind code review |

### Task-Specific

| Command | What It Does |
|---------|--------------|
| `/bug` | Bug fix workflow with minimal-diff enforcement |
| `/feature` | Plan mode then strict mode implementation |
| `/refactor` | Tests-must-stay-green throughout |
| `/setup` | Set up quality infrastructure in current project |

### Mode Control

| Command | What It Does |
|---------|--------------|
| `/inject strict` | Set strict mode |
| `/inject production` | Set production mode (default) |
| `/inject plan` | Set planning mode |
| `/inject off` | Disable mode injection |
| `/inject status` | Show current mode |

## Invariants (Protected Paths)

Edit `.council/invariants.yaml` to protect sensitive files:

```yaml
# NEVER touch these
forbidden_paths:
  - "*.env"
  - ".env.*"
  - "credentials/*"
  - "**/secrets.yaml"

# Ask before touching
protected_paths:
  - "api/schema.py"
  - "migrations/*"
  - "config/production.yaml"
```

The mode injection scripts will warn when these paths are about to be modified.

## How It Works

1. **On every prompt**: `inject.sh` runs via UserPromptSubmit hook
2. **inject.sh** outputs global mindset rules (auto-inject.sh)
3. **inject.sh** checks for mode (local then global) and outputs mode-specific rules
4. **Mode scripts** read `invariants.yaml` and output forbidden/protected path warnings

This gives Claude Code context about:
- What mode it's operating in
- What files it shouldn't touch
- What quality standards to maintain

## Customization

### Adding a New Mode

1. Create `~/.council/hooks/modes/mymode.sh`:
```bash
#!/bin/bash
cat << 'EOF'
[CONTEXT INJECTION - MY MODE]
Your mode-specific rules here...
EOF
exit 0
```

2. Make it executable: `chmod +x ~/.council/hooks/modes/mymode.sh`
3. Use it: `/inject mymode`

### Adding a New Command

1. Create `.claude/commands/mycommand.md`:
```markdown
# My Command

What this command does.

## Steps

1. First step
2. Second step
```

2. Use it: `/mycommand`

### Project-Specific Invariants

Edit `.council/invariants.yaml` in your project to add paths specific to that project.

## Type Checking (PostToolUse Hook)

The `type-check.sh` hook runs automatically after Write/Edit operations on code files.

### Supported Languages

| Language | Tool | Requirements |
|----------|------|--------------|
| Python | mypy, pyright | `pip install mypy` or `pip install pyright` |
| TypeScript | tsc | `npm install -g typescript` |
| Go | go vet | Go toolchain |
| Rust | cargo check | Rust toolchain |

### How It Works

1. Detects file extension (.py, .ts, .tsx, .go, .rs)
2. Runs appropriate type checker
3. Reports errors to Claude (doesn't block)
4. Claude can then fix type errors proactively

### Configuration

The hook is enabled by default in `settings.json`. To disable:
- Remove the `type-check.sh` line from PostToolUse hooks
- Or uninstall the type checker tools

Type checking gracefully skips if tools aren't installed.

## Philosophy

### Right > Fast

Speed comes from the system (parallel agents, automation). The agent's job is to be **right** and **thorough**.

### Evidence Over Narrative

Don't say "I fixed it" - show proof:
- Test output
- Git diff
- Command exit codes

### Pushback > Compliance

The agent should question requests that seem wrong:
- "What's wrong with this approach?"
- "What will break?"
- "Should we do this at all?"

### Minimal Changes

Fix what's broken. Don't "improve" adjacent code. Don't add features beyond what was asked.

## Requirements

- Claude Code CLI
- Bash (for hooks)
- Python 3 (for invariants.yaml parsing with PyYAML)

## License

MIT
