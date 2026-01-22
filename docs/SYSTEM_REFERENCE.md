# Council v3 System Reference

Quick reference cheat sheet. Read this when context is lost.

**Full docs:** `docs/OPERATING_GUIDE.md`

---

## Mode Injection

**Architecture:**
```
inject.sh (router)
├── global.sh              ← always (push back, investigate)
├── modes/{mode}.sh        ← based on .council/mode
└── framework.sh           ← if .council/framework set
```

**Precedence (LOCAL overrides GLOBAL):**
```
1. .council/mode     ← project-local, checked FIRST
2. ~/.council/mode   ← global fallback
3. default: strict   ← if no mode file exists
```

```bash
# Set locally (one project)
echo "research" > .council/mode

# Set globally (all projects)
echo "strict" > ~/.council/mode
```

| Mode | Purpose |
|------|---------|
| `research` | Collaborative brainstorming, preserve content, stay in phase |
| `plan` | Design: plan before building, wait for approval |
| `sandbox` | POC: fast iteration, fixtures, experimentation |
| `scrappy` | Rapid validation, brute force OK, scale aggressively |
| `strict` | Procedures + paths + DONE_REPORT (no mindset) |
| `production` | Full rigor: mindset + procedures + paths + DONE_REPORT |
| `review` | Adversarial: context-blind review, requires evidence |
| `off` | No mode injection (global rules still apply) |

---

## Project Setup

| Command | Creates |
|---------|---------|
| `/setup` | CLAUDE.md, STATE.md, LOG.md, .claude/commands/ |
| `/enforce` | .council/invariants.yaml, .git/hooks/pre-commit |

**New project needs BOTH:**
```bash
git init && /setup && /enforce
```

---

## Slash Commands

| Command | What |
|---------|------|
| `/test` | Run tests (auto-detects framework) |
| `/test-cycle` | Generate + run tests progressively |
| `/done` | Verify before marking complete |
| `/commit` | Stage and commit |
| `/ship` | test → commit → push → PR |
| `/review` | Code review (spawns subagent) |
| `/inject <mode>` | Change mode |
| `/save` | Update STATE.md + LOG.md |

---

## Dispatcher Commands

```bash
1: <text>         # Send to agent 1
queue 1 "<task>"  # Add task to queue
queue 1           # Show queue
clear 1           # Clear queue
auto 1            # Enable auto-continue
stop 1            # Disable auto-continue
reset 1           # Reset circuit breaker
status            # Show all agents
```

**Circuit breaker:** Opens after 3 iterations without git commits. Reset with `reset N`.

---

## Plugins

| Plugin | Commands |
|--------|----------|
| ralph-loop | `/ralph-loop "prompt"`, `/cancel-ralph` |
| ralph-queue | `/ralph-queue "t1" \| "t2"`, `/ralph-queue-start`, `-status`, `-clear` |
| standup | `/standup` |

**Plugin commands require session restart if installed mid-session.**

---

## Enforcement

**Pre-commit blocks:**
- `forbidden_paths` → always blocked
- `protected_paths` → blocked unless `git commit --no-verify`

**Config:** `.council/invariants.yaml`
```yaml
forbidden_paths:
  - "*.env"
  - ".secrets/*"
protected_paths:
  - "migrations/*"
```

**Check manually:**
```bash
python scripts/check_invariants.py --diff HEAD~1
python scripts/check_invariants.py --diff main --allow-protected
```

---

## Quality Hooks (PreToolUse/PostToolUse)

| Hook | Type | What |
|------|------|------|
| `tdd_guard.py` | PreToolUse | Blocks Write/Edit unless failing tests exist |
| `file_checker.py` | PostToolUse | Auto-format + lint/type check Python files |

**Install:** `quality-pack/install.sh` (see `quality-pack/README.md`)

**TDD Guard:** Hard enforcement - can't write implementation code without a failing test first. Override by retrying within 60s.

---

## Audit

```bash
# Audit transcript for lies
python scripts/audit_done.py --transcript ~/.claude/projects/.../session.jsonl

# Exit codes: 0=verified, 1=discrepancy, 2=no DONE_REPORT
```

---

## DONE_REPORT Format (Strict Mode)

```
DONE_REPORT:
- changed_files: [git diff --name-only]
- commands_run: [exact commands + exit codes]
- test_output: [summary]
- invariants: [check_invariants.py result]
- next_actions: [if any]
```

---

## LLM Council

```bash
council plan "build REST API"              # Multi-model plan
council plan "add auth" --context app.py   # With context
council debate "postgres vs mongo?"        # Get opinions
council refine "more detail on testing"    # Refine plan
council bootstrap PLAN.md                  # Generate files
```

---

## Hub/Spoke Architecture

```
~/.council/hooks/ (HUB)
├── inject.sh           ← main router
├── global.sh           ← universal rules
├── modes/
│   ├── research.sh
│   ├── plan.sh
│   ├── sandbox.sh
│   ├── scrappy.sh
│   ├── strict.sh
│   ├── production.sh
│   └── review.sh
└── framework.sh

Target Projects (SPOKES)
├── .council/mode           ← project mode override
├── .council/framework      ← project build framework
├── .council/invariants.yaml ← path protection
└── .git/hooks/pre-commit
```

---

## Key Files

| File | Purpose |
|------|---------|
| `~/.council/config.yaml` | Agent config (panes, worktrees) |
| `~/.council/mode` | Global mode setting |
| `~/.council/state.json` | Runtime state (queues, circuits) |
| `~/.council/hooks/inject.sh` | Main injection router |
| `~/.council/hooks/global.sh` | Minimal universal rules |
| `~/.council/hooks/modes/*.sh` | Mode-specific scripts |
| `~/.council/hooks/framework.sh` | Build framework injection |
| `.council/invariants.yaml` | Project path protection |
| `.council/mode` | Project-local mode override |
| `.council/framework` | Project build framework |
| `~/.claude/commands/` | Global slash commands |
| `.claude/commands/` | Project commands (override global) |

---

## Commands Location

| Location | Scope |
|----------|-------|
| `~/.claude/commands/` | Global (all projects) |
| `.claude/commands/` | Project-local (overrides global) |
| Plugin commands | Session-scoped |

---

## Input Sources

| Source | Config |
|--------|--------|
| Socket | `~/.council/council.sock` (voice via Wispr/Shortcuts) |
| Telegram | bot_token + allowed_user_ids in config.yaml |
| Pushover | user_key + api_token in config.yaml |

---

## Quick Diagnostics

```bash
# Current mode
cat .council/mode 2>/dev/null || cat ~/.council/mode 2>/dev/null || echo "strict (default)"

# Available commands
ls ~/.claude/commands/ .claude/commands/ 2>/dev/null

# Enforcement setup
ls .council/invariants.yaml .git/hooks/pre-commit

# Installed plugins
grep -o '"[^"]*@[^"]*"' ~/.claude/plugins/installed_plugins.json

# Dispatcher state
cat ~/.council/state.json | python -m json.tool
```

---

## Common Mistakes

1. **Mode is only global** → No, `.council/mode` overrides global
2. **Forgot /setup** → New projects need `/setup` AND `/enforce`
3. **Plugin commands missing** → Restart Claude after plugin install
4. **Cutting scope in strict** → Strict = don't touch (no adding OR removing)
5. **Wrong pane IDs** → Use `%N` (stable) not indexes (shift when panes close)

---

## Workflow

```
Plan → /inject plan, design approach
Implement → /inject strict, write code
Test → /test or /test-cycle
Verify → /done
Review → /review
Ship → /ship
```

**Shortcuts:**
- Bug fix: implement → /test → /done → /commit
- Docs: edit → /commit

---

## Build Frameworks

```bash
/framework mvp          # Fast initial builds
/framework prove-first  # Feature integration (prove before integrate)
/framework showcase     # Demos and pitches
/framework production   # Real users, high quality
/framework status       # Check current framework
/framework clear        # Remove framework
```

**Framework is stored in:** `.council/framework`

| Framework | Use Case | Time vs MVP |
|-----------|----------|-------------|
| `mvp` | Validate idea fast | 1x |
| `prove-first` | Add features safely, prove before integrate | 2x |
| `showcase` | Impress people | 2-3x |
| `production` | Real users | 3-5x |

**Full docs:**
- `docs/MVP_BUILD.md`
- `docs/SANDBOX_TO_SCALE.md`
- `docs/SHOWCASE_DEMO.md`
- `docs/PRODUCTION_SYSTEM.md`

---

## When Context Compacts

1. Read this file
2. Read `STATE.md` - current work
3. Read `CLAUDE.md` - project rules
4. Read `.council/invariants.yaml` - what's forbidden

Don't assume. Verify by reading actual files.
