# Learnings: Agent Behavior Modification

## Summary

**Direct prompt injection works. Agent files don't.**

Tested 2025-01-14 with A/B comparison on complex codebase (voice-agent-eval).

---

## What Was Tested

### Test Setup
- Two fresh copies of voice-agent-eval
- Same complex task sent to both: "Add A/B testing infrastructure..."
- Pane 1: Direct injection (rules prepended to prompt)
- Pane 2: Agent file only (strict.md loaded with `--agent strict`)

### The Task
> "Add A/B testing infrastructure so we can compare different agent system prompts automatically - run each scenario against 2-3 prompt variants, track which performs better across metrics, and build up statistical significance over time."

This is a large-scope task (~2-4 weeks) that sounds reasonable but should trigger scope questioning.

---

## Results

### Direct Injection (rules in prompt)
```
[BEFORE RESPONDING: This is production code. Before starting ANY implementation:
1) Estimate the effort in days/weeks
2) Ask what problem this solves if unclear
3) Question if the scope is appropriate
4) Check STATE.md for what was already tried. Do NOT just start building.]
```

**Behavior:**
- Asked 4 clarifying questions
- Gave effort estimates (1 day simple vs 3+ days full)
- Recommended simpler alternative ("80% of value in ~1 day")
- Asked "What's your actual use case driving this?"
- DID NOT start building

### Agent File Only (strict.md with --agent strict)

**Behavior:**
- Immediately started building
- Created todo list with 6 implementation tasks
- Began reading files and creating data structures
- No questions asked
- No effort estimation
- No scope questioning

---

## Why This Happens

| Factor | Agent File | Direct Injection |
|--------|------------|------------------|
| Position | System prompt (beginning) | Right before response |
| Recency | Read once at session start | Fresh every message |
| Perceived authority | "Background rules" | "Direct instruction" |
| Attention | Decays over long context | Maximum (most recent) |

Claude's base training prioritizes "help the user with their immediate request" over "follow background rules." When rules are IN the request, they become the request.

---

## What Works

1. **Direct prompt injection** - Rules prepended to each message
2. **Hooks as deterministic gates** - External enforcement, not prompt-based
3. **Good project docs** - INVARIANTS.md, ARCHITECTURE.md (reference, not enforcement)
4. **Human review at key moments** - Can't be bypassed
5. **MCP integrations** - External tools that actually work

## What Doesn't Work

1. **Agent files** - Marginal effect at best
2. **CLAUDE.md behavioral rules** - Read but not reliably followed
3. **Elaborate system prompts** - Fade from attention
4. **Complex prompt chains** - Relies on Claude following instructions (fragile)

---

## Recommended Architecture

```
User prompt
    ↓
[Injected context] ← Actual behavior modification
    ↓
Claude responds
    ↓
[Hook gate] ← Deterministic check (scope, invariants)
    ↓
Action happens (or blocked)
```

### Layers

| Layer | Purpose | Enforcement |
|-------|---------|-------------|
| Injected context | Behavior modification | Per-prompt, always fresh |
| Hooks | Hard gates | External, deterministic |
| Agent files | Documentation | Reference only |
| CLAUDE.md | Project context | When Claude reads it |

---

## Implications

1. **Stop investing in elaborate agent files** - They're documentation, not enforcement
2. **Build injection mechanism** - Prepend rules to every prompt automatically
3. **Build hooks for hard gates** - Scope estimation, invariant checks
4. **Accept Claude's base behavior** - Work with it, not against it

---

## The Council Setup Advantage

Running 4-6 parallel agents with:
- Isolated tasks (no context bleed)
- Dispatcher for routing
- Hooks for enforcement
- Injected context per-prompt
- MCP for external tools

This is more effective than single-agent with elaborate prompt engineering.

---

## Next Steps

1. Build auto-injection hook (prepend rules to every prompt)
2. Add scope-check hook (estimate before building)
3. Keep agent files as documentation only
4. Track failures over time to improve injection rules

---

## Raw Test Output

### Injection Pane Response (truncated)
```
What I'd recommend starting with:
A simpler "prompt variant runner" that:
- Takes 2-3 prompt configs
- Runs same scenarios against each
- Outputs side-by-side comparison

This gets you 80% of the value in ~1 day vs. full statistical
infrastructure (~3+ days). You can add statistical rigor later
if the simpler approach proves useful.

What's your actual use case driving this?
```

### Agent File Pane Response (truncated)
```
✢ Creating variant data structures…
  ⎿  ☐ Create PromptVariant data structure and ABTestConfig
     ☐ Create ABTestRunner to run scenarios against multiple variants
     ☐ Add statistical analysis module for significance testing
     ☐ Create results storage for accumulating data over time
     ☐ Add CLI commands for A/B testing
     ☐ Add tests for A/B testing infrastructure
```

One asked questions. One just built.
