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
    ├── modes/
    │   ├── production.sh  # Right > Fast
    │   ├── strict.sh      # Evidence over narrative
    │   ├── plan.sh        # Design before building
    │   ├── review.sh      # Adversarial critique
    │   ├── sandbox.sh     # Quick POC iteration
    │   ├── scrappy.sh     # Rapid validation
    │   └── critical.sh    # High stakes
    └── python/
        ├── tdd_guard.py   # TDD enforcement (PreToolUse)
        └── file_checker.py # Auto-format & lint (PostToolUse)
```

### Project (`.claude/`, `.council/`)

```
.claude/
├── settings.json              # Permissions and hooks
├── memory-bank/               # RIPER plans and reviews
├── commands/
│   ├── test.md               # Run tests
│   ├── commit.md             # Stage and commit
│   ├── done.md               # Verify before complete
│   ├── ship.md               # Test, commit, push, PR
│   ├── save.md               # Save context
│   ├── review.md             # Code review (subagent)
│   ├── inject.md             # Mode switching
│   ├── bug.md                # Bug fix workflow
│   ├── feature.md            # Feature workflow
│   ├── refactor.md           # Refactor workflow
│   ├── setup.md              # Project setup
│   └── riper/                # RIPER workflow commands
│       ├── strict.md         # Activate RIPER protocol
│       ├── research.md       # Research mode (read-only)
│       ├── innovate.md       # Brainstorm mode
│       ├── plan.md           # Create specifications
│       ├── execute.md        # Implement plan
│       └── review.md         # Validate implementation
└── agents/
    ├── strict.md             # Production mindset
    ├── code-architect.md     # Architecture specialist
    ├── verify-app.md         # Verification specialist
    ├── research-innovate.md  # RIPER research/innovate agent
    ├── plan-execute.md       # RIPER plan/execute agent
    └── review.md             # RIPER review agent

.council/
├── mode                      # Current mode (production, strict, etc)
└── invariants.yaml           # Forbidden/protected paths
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

## RIPER Workflow

For complex multi-step tasks, use the RIPER workflow with dedicated commands:

| Command | Mode | Allowed Actions |
|---------|------|-----------------|
| `/riper:strict` | Activate protocol | Sets up mode enforcement |
| `/riper:research` | RESEARCH | Read code, search, document - NO suggestions |
| `/riper:innovate` | INNOVATE | Brainstorm approaches - NO implementation |
| `/riper:plan` | PLAN | Write specs to memory-bank only |
| `/riper:execute` | EXECUTE | Implement approved plan exactly |
| `/riper:review` | REVIEW | Validate, run tests - NO fixing |

### Mode Capabilities Matrix

| Mode | Read | Write | Execute | Plan | Validate |
|------|------|-------|---------|------|----------|
| RESEARCH | Yes | No | No | No | No |
| INNOVATE | Yes | No | No | No | No |
| PLAN | Yes | memory-bank | No | Yes | No |
| EXECUTE | Yes | Yes | Yes | No | No |
| REVIEW | Yes | memory-bank | tests | No | Yes |

### RIPER Agents

The workflow uses 3 consolidated agents with restricted tool access:

1. **research-innovate** - Tools: Read, Grep, Glob, LS, WebSearch, WebFetch (NO Write/Edit)
2. **plan-execute** - Tools: All (but PLAN mode restricts writes to memory-bank)
3. **review** - Tools: Read, Bash, Grep, Glob, LS, WebFetch (NO Write/Edit)

### Example RIPER Session

```bash
# Start with strict mode
/riper:strict

# Research the codebase
/riper:research analyze the authentication system

# Brainstorm approaches (optional)
/riper:innovate explore OAuth integration options

# Create detailed plan
/riper:plan add OAuth2 support to auth module

# Implement the plan
/riper:execute

# Validate implementation
/riper:review
```

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

## TDD Guard (PreToolUse Hook)

TDD Guard enforces test-first development by warning when you try to edit implementation code without failing tests.

### How It Works

1. **PreToolUse hook** intercepts Write/Edit operations
2. **Checks for failing tests**:
   - Python: Looks for `.pytest_cache/v/cache/lastfailed`
   - TypeScript: Checks for corresponding `.test.ts` file
3. **First warning** records the file and blocks
4. **Retry within 60 seconds** allows override

### What Gets Checked

| Language | Enforcement |
|----------|-------------|
| Python (.py) | Must have failing tests in pytest cache |
| TypeScript (.ts, .tsx) | Must have corresponding .test.ts file |
| JavaScript (.js, .jsx) | Must have corresponding .test.js file |

### What's Skipped

- Test files themselves (test_*.py, *.test.ts, etc.)
- Config files (.json, .yaml, .toml, .md, etc.)
- Generated code (node_modules, dist, build, etc.)
- Infrastructure code (terraform, cdk, migrations, etc.)
- Files in .claude/ directory

### Example

```
$ # Try to edit implementation without failing test
TDD Guard: No failing tests detected
    Consider writing a failing test first before implementing.
    (Retry to proceed anyway)

$ # Retry immediately to override
TDD Guard: Proceeding (override acknowledged)
```

### Disabling TDD Guard

Remove the PreToolUse hook from `.claude/settings.json` or comment it out.

## Python File Checker (PostToolUse Hook)

Auto-formats and type-checks Python files after Write/Edit operations.

### Features

1. **Auto-format** with ruff (or black as fallback)
2. **Lint** with ruff check
3. **Type check** with basedpyright (or pyright as fallback)
4. **Reports errors** inline for Claude to fix

### Requirements

```bash
pip install ruff basedpyright  # Preferred
# Or
pip install black pyright      # Fallback
```

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
- Python 3 (for Python hooks and YAML parsing)

### Recommended Tools

| Tool | Purpose |
|------|---------|
| ruff | Python linting and formatting |
| basedpyright | Python type checking |
| pytest | Python testing |
| tsc | TypeScript type checking |

## Credits

This quality pack incorporates implementations from:

- **RIPER Workflow**: Based on [claude-code-riper-5](https://github.com/tony/claude-code-riper-5) by Tony Narlock, which is based on the RIPER-5 workflow by [robotlovehuman](https://forum.cursor.com/u/robotlovehuman/) on the Cursor Forums.
- **TDD Guard**: Based on [claude-codepro](https://github.com/maxritter/claude-codepro) by Max Ritter.

## License

MIT
