# Config Status

Show all current Council settings at a glance with explanations and recommendations.

## Usage

- `/config-status` - Show dashboard view of all settings
- `/config-status explain <topic>` - Detailed explanation of a setting
- `/config-status recommend` - Get actionable suggestions based on current state

## What to do

When user runs this command with argument `$ARGUMENTS`:

### Default (no arguments or empty): Dashboard View

Read all config sources and display a formatted dashboard:

```
=== Council Config Status ===

MODE: <project mode> (project) <- global: <global mode>
FRAMEWORK: <framework>
AGENT: <claude code agent setting>

DISPATCHER (<N> agents configured):
  1. <Name>        | auto:<ON/OFF> | circuit:<OPEN/CLOSED> | queue:<N> | streak:<N>
  2. <Name>        | auto:<ON/OFF> | circuit:<OPEN/CLOSED> | queue:<N> | streak:<N>
  ...

NOTIFICATIONS: <Pushover check> <Telegram check> <Mac check>
INVARIANTS: <N> forbidden, <N> protected paths
HOOKS: <list of hooks>

Use: /config-status explain <setting> for details
     /config-status recommend for suggestions
```

**Steps to gather data:**

1. **Mode (project)**: Read `.council/mode` (may not exist)
2. **Mode (global)**: Read `~/.council/current_inject.txt` (may not exist)
3. **Framework**: Read `.council/framework` (may not exist)
4. **Agent setting**: Read `.claude/settings.json`, extract `agent` field
5. **Dispatcher config**: Read `~/.council/config.yaml`, parse agents section
6. **Dispatcher state**: Read `~/.council/state.json`, parse per-agent state
7. **Invariants**: Read `.council/invariants.yaml`, count forbidden_paths and protected_paths
8. **Hooks**: List files in `~/.council/hooks/*.sh`

**Display rules:**
- If file doesn't exist, show "not set" or "not configured"
- For dispatcher, merge config (names) with state (auto, circuit, queue, streak)
- Agent names from config.yaml, state from state.json
- Show counts for invariants, not full paths
- For notifications, show checkmark if configured in config.yaml

### Explain Mode: `/config-status explain <topic>`

Valid topics and what to explain:

**`mode`** - Injection modes:
```
MODES:

strict     - Production mode. DONE_REPORT required, verify before claiming done,
             respect invariants, confirm scope before big changes.
             Use for: production code, anything going to users

production - Strict + "Right > Fast" mindset. Forbidden/protected paths enforced.
             Read before edit, test after change, 2 failures = stop.
             Use for: high-stakes code, real user data

sandbox    - POC mode. Fast iteration, fixtures OK, skip edge cases.
             Use for: prototyping, experiments, proving concepts

scrappy    - Rapid mode. Try fast, validate fast, max 3 retries then move on.
             Use for: bulk operations, quick validation

plan       - Design before building. Output structured plan, wait for approval.
             Use for: complex features, architecture decisions

review     - Adversarial review. Requires evidence (diff, tests, invariants check).
             Outputs BLOCKERS/SHOULD_FIX/SUGGESTIONS/VERDICT.
             Use for: code review, pre-merge checks

critical   - High stakes. Be thorough, resist rushing.
             Use for: critical systems, irreversible changes

off        - Disable mode injection. Global rules still apply.
             Use for: when modes get in the way

HOW TO CHANGE:
  Global:  /inject <mode>  OR  echo "strict" > ~/.council/current_inject.txt
  Local:   /inject local <mode>  OR  echo "sandbox" > .council/mode

PRECEDENCE: Local (.council/mode) overrides global (~/.council/current_inject.txt)
```

**`framework`** - Build frameworks:
```
FRAMEWORKS:

mvp         - Validate idea fast. Cut corners OK, speed over polish.
              Time: 1x baseline
              Use for: first version, testing assumptions

prove-first - Prove in sandbox before integrating. Test at each layer.
              Layers: Sandbox (isolated) -> Integration -> System
              Time: 2x baseline
              Use for: adding features to existing code

showcase    - Polish for demos. Visual quality matters.
              Time: 2-3x baseline
              Use for: pitches, demos, investor meetings

production  - Real users. Full quality bar. No shortcuts.
              Time: 3-5x baseline
              Use for: production release, user-facing code

HOW TO CHANGE:
  /framework <name>     - Set framework
  /framework status     - Check current
  /framework clear      - Remove framework

STORED IN: .council/framework
```

**`circuit`** - Circuit breaker:
```
CIRCUIT BREAKER:

PURPOSE: Prevents agents from spinning forever without making progress.

HOW IT WORKS:
1. After each auto-continue, dispatcher checks for git progress
2. If no new commits/changes detected, no_progress_streak increments
3. After 3 iterations without progress, circuit OPENS
4. Open circuit = no more auto-continues for that agent

STATES:
  CLOSED - Normal. Auto-continue will work.
  OPEN   - Tripped. Agent made 3+ iterations without git progress.

HOW TO RESET:
  reset <N>          - Reset circuit for agent N (via dispatcher command)
  progress <N> mark  - Manually mark progress (resets streak to 0)

WHY IT EXISTS:
  - Agents can get stuck in loops
  - Without breaker, auto-continue would waste tokens forever
  - Forces human review when agent isn't progressing
```

**`auto`** - Auto-continue:
```
AUTO-CONTINUE:

PURPOSE: Automatically sends "continue" when agent stops, enabling unattended work.

HOW IT WORKS:
1. Dispatcher polls agent panes for readiness (looking for prompt)
2. If agent is ready AND auto is ON AND circuit is CLOSED:
   - Check task queue first (dequeue if tasks waiting)
   - Otherwise send "continue"
3. Agent resumes work

COMMANDS:
  auto <N>  - Enable auto-continue for agent N
  stop <N>  - Disable auto-continue for agent N
  status    - Show all agents' auto state

RISKS:
  - Can waste tokens if agent is genuinely done
  - Circuit breaker mitigates infinite loops
  - Always check queue depth and circuit state

WHEN TO USE:
  - Overnight runs
  - Long sequential tasks
  - When you'll monitor occasionally

WHEN NOT TO USE:
  - Interactive work
  - When you need to review each step
  - When agent needs human input
```

**`invariants`** - Path protection:
```
INVARIANTS:

PURPOSE: Protect sensitive files from accidental modification.

TWO LEVELS:

FORBIDDEN - NEVER touched. No override. Hard block.
  Examples: *.env, credentials/*, .secrets/*
  Use for: secrets, API keys, credentials

PROTECTED - Blocked by default. --allow-protected overrides.
  Examples: api/schema.py, migrations/*, config/production.yaml
  Use for: schemas, migrations, production configs

HOW ENFORCEMENT WORKS:
1. Pre-commit hook checks changed files against invariants.yaml
2. scripts/check_invariants.py can be run manually
3. Mode injection (strict/production) reminds Claude of rules

CONFIG FILE: .council/invariants.yaml

FORMAT:
  forbidden_paths:
    - "*.env"
    - "credentials/*"
  protected_paths:
    - "api/schema.py"
    - "migrations/*"

COMMANDS:
  python scripts/check_invariants.py --diff HEAD~1
  python scripts/check_invariants.py --diff main --allow-protected
```

**`hooks`** - Claude Code hooks:
```
HOOKS:

PURPOSE: Shell scripts that run on Claude Code events.

HOOK TYPES:
  UserPromptSubmit - Runs before each prompt (mode injection)
  PreToolUse       - Runs before tool execution (TDD Guard)
  PostToolUse      - Runs after tool execution (formatters, linters)
  Stop             - Runs when Claude stops (notifications)
  Notification     - Runs on notification events

INSTALLED HOOKS (in ~/.council/hooks/):
  inject.sh        - Main mode injection hook
  auto-inject.sh   - Auto-injection helper
  framework.sh     - Framework context injection
  production.sh    - Production mode rules
  strict.sh        - Strict mode rules
  check_invariants.sh - Invariants check on prompt

CONFIGURED IN: .claude/settings.json under "hooks" key

HOW THEY WORK:
1. Claude Code triggers event (e.g., user submits prompt)
2. Hook script runs with context variables
3. Script can inject context, block actions, or log
```

### Recommend Mode: `/config-status recommend`

Analyze current state and suggest actions. Read all config sources, then apply these rules:

```
RECOMMENDATIONS:

1. IF circuit is OPEN for any agent:
   -> "Agent <N> circuit is OPEN (streak: <N>). Reset with `reset <N>` or investigate why no git progress."

2. IF mode is 'production' but no tests directory exists:
   -> "Mode is 'production' but no tests/ directory found. Consider 'sandbox' mode or add tests."

3. IF auto is ON but circuit is OPEN:
   -> "Agent <N> has auto ON but circuit is OPEN. Auto-continue is blocked until circuit resets."

4. IF queue depth > 5 for any agent:
   -> "Agent <N> has <N> tasks queued. Consider clearing with `clear <N>` or letting them process."

5. IF agent worktree doesn't exist:
   -> "Agent <N> worktree (<path>) doesn't exist. Update config.yaml."

6. IF no framework is set in .council/framework:
   -> "No build framework set. Consider `/framework prove-first` for structured development."

7. IF mode is not set (both local and global):
   -> "No mode configured. Set with `/inject strict` for production work or `/inject sandbox` for experiments."

8. IF invariants.yaml doesn't exist:
   -> "No invariants configured. Run `/enforce` to set up path protection."

9. IF pushover/telegram not configured:
   -> "Phone notifications not configured. Add pushover: or telegram: to config.yaml for mobile alerts."
```

Output recommendations as a numbered list. If no recommendations apply, say "All settings look good. No recommendations."

## Notes

- This is a read-only command - it only reports state, doesn't change anything
- Uses bash commands to read files (cat, ls, etc.)
- Handles missing files gracefully with "not set" or "not configured"
- For dispatcher state, always shows current values from state.json
