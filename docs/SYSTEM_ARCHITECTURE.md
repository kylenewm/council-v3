# Building Effective AI Agent Systems

A practical guide to building reliable, controllable AI agent workflows based on empirical testing and iteration.

---

## The Core Problem

When working with AI agents (Claude Code, etc.), you need them to:
1. Follow rules consistently (don't build without asking, test before marking done)
2. Respect project invariants (don't break existing behavior)
3. Adapt to different work modes (production vs POC vs planning)

**The naive approach** is to write rules in markdown files (CLAUDE.md, agent files) and hope the AI follows them.

**The discovery:** This doesn't work reliably. Direct prompt injection does.

---

## Key Finding: Injection > Documentation

### The A/B Test

**Setup:**
- Two fresh sessions, same complex task
- Pane 1: Rules injected directly into prompt
- Pane 2: Same rules in agent file (`--agent strict`)

**Task:** "Add A/B testing infrastructure..." (large scope, ~2-4 weeks, should trigger scope questioning)

**Results:**

| Behavior | Direct Injection | Agent File |
|----------|------------------|------------|
| Asked clarifying questions | ✅ 4 questions | ❌ None |
| Gave effort estimate | ✅ "1 day vs 3+ days" | ❌ No |
| Suggested simpler approach | ✅ "80% of value in ~1 day" | ❌ No |
| Started building immediately | ❌ No | ✅ Yes |

**One asked questions. One just built.**

### Why This Happens

| Factor | Agent/MD Files | Direct Injection |
|--------|----------------|------------------|
| Position | System prompt (beginning) | Right before response |
| Recency | Read once at session start | Fresh every message |
| Perceived authority | "Background rules" | "Direct instruction" |
| Attention | Decays over long context | Maximum (most recent) |

Claude's base training prioritizes "help with the immediate request" over "follow background rules." When rules are IN the request, they become the request.

---

## The Solution: Hook-Based Context Injection

### Architecture

```
User sends message
       ↓
[UserPromptSubmit Hook] ← Injects context automatically
       ↓
Claude sees: [INJECTED RULES] + [USER MESSAGE]
       ↓
Claude responds with modified behavior
       ↓
[Stop Hook] ← Can block/continue (ralph-loop uses this)
       ↓
Action happens
```

### Implementation

**Hook router** (`~/.council/hooks/inject.sh`):
```bash
#!/bin/bash
# Always inject global rules
"$HOME/.council/hooks/auto-inject.sh"

# Add mode-specific rules based on current mode
MODE=$(cat "$HOME/.council/current_inject.txt")
case "$MODE" in
    strict)  "$HOME/.council/hooks/strict.sh" ;;
    sandbox) "$HOME/.council/hooks/sandbox.sh" ;;
    plan)    "$HOME/.council/hooks/plan.sh" ;;
esac
```

**Registered in** `~/.claude/settings.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "/path/to/inject.sh"
      }]
    }]
  }
}
```

### The Three Modes

**1. Strict Mode** (production work)
```
BEFORE:
1. Read INVARIANTS.md, STATE.md, CLAUDE.md
2. Read any file before editing - never guess
3. Estimate effort if scope is large

DURING:
1. Test after each significant change
2. Don't add features beyond what was asked
3. If 3+ attempts fail, stop and reassess

AFTER:
1. Run tests - prove it works
2. If tests fail, fix it - don't mark done
3. Check for regressions
```

**2. Sandbox Mode** (rapid POC iteration)
```
PATTERNS:
1. Create fixtures first - capture real data, iterate infinitely
2. Decouple expensive ops (API/LLM) from cheap ops (filtering/logic)
3. Use test_mode configs (smaller limits, skip reviews)
4. Output structured metrics: pass/fail + timing + quality scores
5. Tier fixtures: core (~30s) vs extended (full check)

WORKFLOW:
1. Capture: Run once with real data, save intermediate state
2. Iterate: Replay cached state with code changes (zero API cost)
3. Validate: Check metrics pass before integrating
```

**3. Plan Mode** (design before building)
```
BEFORE writing any code:
1. Break work into phases with clear deliverables
2. Document invariants that must not be broken
3. Identify which tool/subagent to use at each step
4. Define success metrics for each phase

OUTPUT:
- A structured plan document
- Wait for approval before implementing
- If uncertain, present options with tradeoffs
```

### Global Rules (always injected)

```
Your goal is not to please. Push back if:
- The approach seems wrong or overcomplicated
- Scope is too large without clear justification
- You're being asked to repeat something already tried
- Requirements are ambiguous

Investigate before assuming. Ask if uncertain.
Don't be a yes-man.
```

---

## Sandbox Testing Methodology

### The Problem with Traditional Testing

AI-powered features have expensive operations (API calls, LLM inference) mixed with cheap operations (filtering, formatting, logic). Running full tests is:
- Slow (minutes per run)
- Expensive (API costs)
- Flaky (non-deterministic LLM outputs)

### The Solution: Fixture-Based Iteration

**Principle:** Capture real data once, iterate infinitely.

```
tests/fixtures/
├── component_name/
│   ├── input_1.json      # Real captured request
│   ├── output_1.json     # Real captured response
│   └── _meta.json        # tier: core/extended
└── gold_queries/         # Full pipeline golden outputs
```

**Workflow:**

1. **Capture Phase** - Run with real APIs, save intermediate state
   ```python
   if CAPTURE_MODE:
       result = call_real_api(input)
       save_fixture(f"fixtures/{name}.json", result)
   ```

2. **Iterate Phase** - Replay cached state, change logic
   ```python
   if TEST_MODE:
       result = load_fixture(f"fixtures/{name}.json")
   else:
       result = call_real_api(input)
   # Now test your filtering/formatting logic
   ```

3. **Validate Phase** - Check metrics before integrating
   ```python
   assert pass_rate >= 0.95
   assert avg_latency < 500  # ms
   assert quality_score >= 4.0
   ```

### Fixture Tiers

| Tier | Purpose | Runtime | When to Run |
|------|---------|---------|-------------|
| Core | Smoke test | ~30s | Every change |
| Extended | Full validation | ~5min | Before merge |
| Gold | Regression detection | ~10min | Before release |

### Metrics to Track

```python
@dataclass
class EvalResult:
    pass_rate: float      # % of scenarios passing
    avg_latency_ms: float # Response time
    quality_score: float  # 1-5 LLM-judged quality
    cost_usd: float       # API spend

    def meets_bar(self) -> bool:
        return (
            self.pass_rate >= 0.95 and
            self.quality_score >= 4.0 and
            self.avg_latency_ms < 1000
        )
```

---

## Multi-Agent Philosophy

### Why Multiple Agents?

Single agent with elaborate prompts has problems:
- Context window fills up
- Instructions fade from attention
- One stuck task blocks everything
- No isolation between concerns

Multiple agents provide:
- **Isolation** - Each agent has fresh context per task
- **Parallelism** - Work on multiple things simultaneously
- **Specialization** - Different agents for different work types
- **Fault tolerance** - One stuck agent doesn't block others

### Agent Setup

```
┌─────────────────────────────────────────────────────────┐
│                      DISPATCHER                          │
│  Routes commands from voice/phone/telegram to agents     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│   │ Agent 1  │  │ Agent 2  │  │ Agent 3  │  │ Agent 4│  │
│   │ Project A│  │ Project B│  │ Project C│  │Proj D  │  │
│   │ (tmux %0)│  │ (tmux %1)│  │ (tmux %3)│  │(tmux %4│  │
│   └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                          │
│   Each agent:                                            │
│   - Has own Claude Code session                          │
│   - Works on isolated project                            │
│   - Receives injected context via hooks                  │
│   - Reports status via notifications                     │
└─────────────────────────────────────────────────────────┘
```

### Input Sources

| Source | Use Case |
|--------|----------|
| Voice (FIFO) | Hands-free commands via Wispr Flow |
| Telegram | Phone-based commands when away from desk |
| Pushover | Receive notifications on phone |
| Direct tmux | Manual intervention when needed |

### Circuit Breaker

Prevents infinite loops when agent is stuck:
- Opens after 3 iterations without git progress
- Blocks auto-continue until manually reset
- Git-based detection: no new commits = no progress

---

## What Works vs What Doesn't

### Works Well

| Approach | Why |
|----------|-----|
| Direct prompt injection | Fresh every message, maximum attention |
| Hooks as deterministic gates | External enforcement, not prompt-based |
| Fixture-based testing | Decouple expensive from cheap operations |
| Multi-agent isolation | Fresh context, parallel work |
| Git-based progress detection | Objective, can't be gamed |

### Doesn't Work

| Approach | Why |
|----------|-----|
| Agent files (--agent) | Marginal effect, fades from attention |
| CLAUDE.md behavioral rules | Read but not reliably followed |
| Elaborate system prompts | Decay over long conversations |
| Complex prompt chains | Relies on AI following instructions (fragile) |
| Single agent for everything | Context pollution, single point of failure |

---

## Design Decisions

### Why hooks instead of CLAUDE.md?

CLAUDE.md is treated as reference material. Hooks inject into the actual prompt, which gets instruction-level compliance.

### Why global mode instead of per-project?

You're one operator with one mindset. "I'm in production mode" or "I'm in sandbox mode" reflects YOUR state, not the project's nature.

### Why git-based progress detection?

It's objective and can't be gamed. The agent either made commits or didn't. No subjective "I'm making progress" claims.

### Why raw tmux instead of libtmux?

Fewer dependencies, more control, easier debugging. `subprocess.run(["tmux", "send-keys", ...])` is simple and reliable.

### Why FIFO for voice input?

Decouples transcription from dispatch. Any tool that can write to a file can send commands. Wispr Flow → FIFO → Dispatcher.

---

## File Structure

```
~/.council/
├── hooks/
│   ├── inject.sh         # Router (runs on every prompt)
│   ├── auto-inject.sh    # Global rules (always runs)
│   ├── strict.sh         # Production mode
│   ├── sandbox.sh        # POC mode
│   └── plan.sh           # Planning mode
├── current_inject.txt    # Current mode (strict/sandbox/plan/off)
├── config.yaml           # Agent configuration
└── state.json            # Persisted state (queues, circuits)

~/.claude/
├── settings.json         # Hook registration
├── commands/             # Slash commands (/inject, etc.)
└── agents/               # Agent definitions (documentation only)
```

---

## Quick Start

### 1. Set up hooks

```bash
mkdir -p ~/.council/hooks
# Copy hook scripts from council-v3/examples/hooks/
```

### 2. Register in settings.json

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "~/.council/hooks/inject.sh"
      }]
    }]
  }
}
```

### 3. Set mode

```bash
echo "strict" > ~/.council/current_inject.txt
```

### 4. Restart Claude Code session

Settings.json is read at session start. Hook script changes take effect immediately.

---

## Changing Modes

Use the `/inject` command:

```
/inject strict   # Production: ask first, verify after
/inject sandbox  # POC: fixtures, fast iteration
/inject plan     # Design: thorough planning before code
/inject off      # Disable mode (global rules still apply)
/inject status   # Show current mode
```

---

## Summary

1. **Inject rules directly** - Don't rely on markdown files
2. **Use hooks for automation** - UserPromptSubmit injects context every message
3. **Capture fixtures** - Run expensive ops once, iterate on cheap logic
4. **Isolate agents** - Multiple sessions > one elaborate session
5. **Detect progress objectively** - Git commits, not AI claims
6. **Keep it simple** - Raw tmux, simple bash scripts, minimal dependencies

The system is effective because it works WITH Claude's base behavior (follow immediate instructions) rather than against it (hope it remembers background rules).
