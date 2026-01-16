# Sandbox to Scale Framework

A systematic process for integrating probabilistic features (LLMs, APIs, uncertain logic) without cutting corners or integrating sloppily.

---

## The Problem This Solves

Common failure modes when adding new features:

1. **Premature integration** - Wiring into codebase before the feature actually works
2. **Corner cutting** - Skipping simulations because "it probably works"
3. **Wrong approach locked in** - Discovering the API/LLM/logic doesn't fit after deep integration
4. **Sloppy integration** - Feature works in isolation but breaks when connected
5. **Insufficient iteration** - Not enough test runs to surface edge cases

**The goal is NOT to add the feature. The goal is to determine IF the feature is viable.**

---

## Core Principles

### 1. Prove Before Integrate
Never integrate unproven code. A feature must demonstrate viability in isolation before touching the main codebase.

### 2. Fail Fast, Fail Cheap
Discovery happens in sandboxes where mistakes cost nothing. The expensive integration only happens after confidence is high.

### 3. Test at Every Layer
Like testing a city: test the brick (unit), test the building (integration), test the city (system).

### 4. Go/No-Go Gates
Explicit decision points where you ask: "Should this proceed?" Not every feature survives - that's the point.

### 5. Never Cut Corners
If something feels like a shortcut, it's probably a landmine. Do the work upfront.

---

## The Three Layers

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: SYSTEM (The City)                                  │
│ Full integration testing with real data flows               │
│ Question: Does this break anything? Does it scale?          │
├─────────────────────────────────────────────────────────────┤
│ LAYER 2: INTEGRATION (The Building)                         │
│ Feature connected to adjacent components                    │
│ Question: Does it fit? Are the interfaces right?            │
├─────────────────────────────────────────────────────────────┤
│ LAYER 1: SANDBOX (The Brick)                                │
│ Feature in complete isolation with fixtures                 │
│ Question: Does it even work? What's the right approach?     │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Sandbox (The Brick)

### Purpose
Prove the feature works AT ALL before writing any integration code.

### What You Do
1. Create isolated test directory (not in main codebase)
2. Build minimal implementation
3. Use fixtures/mocks for external dependencies
4. Run N iterations (not just 1)
5. Document what works and what doesn't

### Directory Structure
```
/tmp/sandbox-{feature-name}/
├── main.py           # Minimal implementation
├── fixtures/         # Captured real data (APIs, LLM responses)
├── test_cases.py     # Edge cases, failure modes
├── results/          # Iteration outputs
├── FINDINGS.md       # What you learned
└── DECISION.md       # Go/No-Go recommendation
```

### Minimum Iteration Requirements

| Feature Type | Minimum Iterations | Why |
|--------------|-------------------|-----|
| LLM/AI | 10+ | High variance in outputs |
| External API | 5+ | Rate limits, error modes |
| Algorithm | 20+ | Edge cases |
| Data pipeline | 10+ | Data quality variance |
| UI/UX | 5+ | Interaction patterns |

### Go/No-Go Criteria (Layer 1)

**PROCEED if:**
- [ ] Core functionality works in 80%+ of test iterations
- [ ] Edge cases identified and handled
- [ ] Performance is acceptable (measured, not guessed)
- [ ] Approach is validated (not just "first thing I tried")
- [ ] FINDINGS.md documents what you learned

**STOP if:**
- [ ] Success rate < 50% after 10+ iterations
- [ ] Fundamental approach is wrong (pivot needed)
- [ ] External dependency is unreliable
- [ ] Complexity exceeds value

### Sandbox Skill Usage
```bash
/sandbox "feature name"

# Creates:
# 1. Isolated directory
# 2. Fixture capture scripts
# 3. Iteration runner
# 4. FINDINGS.md template
# 5. DECISION.md template
```

---

## Layer 2: Integration (The Building)

### Purpose
Prove the feature fits with adjacent components before full system integration.

### Prerequisites
- Layer 1 DECISION.md says "GO"
- FINDINGS.md documents the viable approach
- Test fixtures captured

### What You Do
1. Identify the 2-3 components this feature touches
2. Create integration test that connects them
3. Use real interfaces, stubbed backends
4. Test the contract between components
5. Document integration requirements

### Integration Checklist

```markdown
## Integration Readiness Checklist

### Interfaces
- [ ] Input format matches what upstream provides
- [ ] Output format matches what downstream expects
- [ ] Error format matches error handling patterns
- [ ] Logging matches existing log format

### Dependencies
- [ ] Required packages identified
- [ ] Version compatibility checked
- [ ] No conflicting dependencies

### State
- [ ] State storage approach defined (DB, file, memory)
- [ ] State cleanup on failure defined
- [ ] Concurrency behavior defined

### Failure Modes
- [ ] Timeout behavior defined
- [ ] Retry logic defined
- [ ] Fallback behavior defined
- [ ] Circuit breaker if applicable

### Observability
- [ ] Metrics identified
- [ ] Alerts defined
- [ ] Debug logging available
```

### Go/No-Go Criteria (Layer 2)

**PROCEED if:**
- [ ] Integration tests pass
- [ ] Interfaces are clean (not hacky adapters)
- [ ] No changes required to existing components
- [ ] Performance impact measured and acceptable
- [ ] Rollback plan exists

**STOP if:**
- [ ] Requires changes to 3+ existing components
- [ ] Interface is awkward (forcing square peg)
- [ ] Performance degrades existing features
- [ ] Creates circular dependencies

---

## Layer 3: System (The City)

### Purpose
Prove the feature works in the full system without breaking anything.

### Prerequisites
- Layer 2 integration tests pass
- Integration checklist complete
- Rollback plan documented

### What You Do
1. Add feature to actual codebase
2. Run full test suite
3. Test with realistic data volumes
4. Test failure scenarios
5. Monitor for regressions

### System Verification

```bash
# 1. Add feature (minimal footprint)
# 2. Run existing tests - MUST all pass
pytest tests/ -v

# 3. Run new feature tests
pytest tests/test_{feature}.py -v

# 4. Run integration tests
pytest tests/integration/ -v

# 5. Check invariants
python scripts/check_invariants.py --diff main

# 6. Performance check (if applicable)
python scripts/benchmark.py --feature {feature}
```

### Go/No-Go Criteria (Layer 3)

**SHIP if:**
- [ ] All existing tests pass
- [ ] New feature tests pass
- [ ] No invariant violations
- [ ] Performance acceptable
- [ ] Documentation updated
- [ ] Rollback tested

**REVERT if:**
- [ ] Any existing test fails
- [ ] Invariant violations
- [ ] Performance regression > 10%
- [ ] Undefined behavior discovered

---

## Parallel Execution (Efficiency)

Use sub-agents for Layer 1 exploration when evaluating multiple approaches:

```
Main Agent
├── Spawn: sandbox-agent-1 "Try approach A"
├── Spawn: sandbox-agent-2 "Try approach B"
├── Spawn: sandbox-agent-3 "Try approach C"
└── Wait for results → Compare → Pick best

Time: O(1) instead of O(n) for n approaches
```

### When to Parallelize

| Scenario | Parallelize? |
|----------|-------------|
| Multiple API options | Yes |
| Multiple LLM prompts | Yes |
| Multiple algorithms | Yes |
| Sequential dependencies | No |
| Shared state | No |

---

## The "Never Cut Corners" Hook

### What It Catches

```
[CONTEXT INJECTION - SANDBOX MODE]

BEFORE starting probabilistic feature work:
1. Did you create an isolated sandbox? If not, STOP.
2. Did you capture fixtures for external calls? If not, STOP.
3. Did you run minimum iterations? If not, STOP.
4. Did you write FINDINGS.md? If not, STOP.

RED FLAGS (cut corners detected):
- "It worked once, so it's probably fine"
- "I'll add tests later"
- "The API docs say it works like this"
- "This should work" (without evidence)
- Integrating before sandbox validation

If you catch yourself cutting corners:
1. STOP immediately
2. Document what you skipped
3. Go back and do it properly
4. The extra time now saves 10x debugging later
```

---

## Full Workflow Example

### Feature: Add LLM-powered code review

**Layer 1: Sandbox**
```bash
mkdir /tmp/sandbox-llm-review && cd /tmp/sandbox-llm-review

# 1. Capture fixtures
python capture_fixtures.py  # Saves 20 real code diffs + LLM responses

# 2. Build minimal implementation
# main.py: Just the LLM call + parsing logic

# 3. Run 15 iterations with different prompts
python test_iterations.py --runs 15

# 4. Document findings
# FINDINGS.md:
# - Prompt v3 works best (82% good reviews)
# - Needs max_tokens=2000 for large diffs
# - Fails on binary files (need filter)
# - ~$0.02 per review

# 5. Decision
# DECISION.md: GO - approach validated
```

**Layer 2: Integration**
```bash
# 1. Connect to git diff component
# integration_test.py: git_diff -> llm_review -> output_formatter

# 2. Test interfaces
pytest integration_test.py

# 3. Complete checklist
# - Input: git diff format ✓
# - Output: structured review format ✓
# - Error: raises ReviewError ✓
# - Timeout: 30s with retry ✓

# 4. Decision
# All checks pass, interfaces clean: GO
```

**Layer 3: System**
```bash
# 1. Add to codebase
cp /tmp/sandbox-llm-review/main.py council/review/

# 2. Run full test suite
pytest tests/ -v  # All pass

# 3. Run new tests
pytest tests/test_llm_review.py -v  # All pass

# 4. Check invariants
python scripts/check_invariants.py --diff main  # Clean

# 5. Decision: SHIP
```

---

## Skills and Commands

| Skill | Purpose |
|-------|---------|
| `/sandbox <name>` | Create isolated sandbox for feature |
| `/iterate <n>` | Run N iterations of sandbox tests |
| `/findings` | Generate FINDINGS.md from results |
| `/integration-check` | Run integration readiness checklist |
| `/system-check` | Run full system verification |

---

## Anti-Patterns (What NOT to Do)

### 1. "Just wire it up and see"
**Wrong:** Add LLM call directly to codebase, test in production
**Right:** Sandbox → prove it works → then integrate

### 2. "It worked once"
**Wrong:** Run test once, assume it's reliable
**Right:** Run minimum iterations per feature type

### 3. "I'll refactor later"
**Wrong:** Integrate with hacky code, plan to clean up
**Right:** Clean code before integration, or don't integrate

### 4. "The docs say..."
**Wrong:** Trust documentation without verification
**Right:** Verify with real calls, capture fixtures

### 5. "Skip sandbox, it's simple"
**Wrong:** Integrate "simple" feature directly
**Right:** Even simple features get Layer 1 sandbox (faster to verify than debug)

---

## Metrics

Track these to measure framework effectiveness:

| Metric | Target |
|--------|--------|
| Features killed at Layer 1 | 20-30% (finding bad ideas early) |
| Features killed at Layer 2 | 5-10% (integration issues) |
| Features reverted at Layer 3 | < 5% (rare) |
| Time in sandbox vs integration | 60/40 (most time in cheap sandbox) |
| Regressions from new features | 0 |

---

## When to Skip Layers

**Never skip Layer 1** for probabilistic features.

You MAY compress Layers 2+3 when:
- Feature is isolated (no integration points)
- Feature is deterministic (pure function)
- Feature is low-risk (typo fix, copy change)

You MUST do all layers when:
- Feature involves external APIs
- Feature involves AI/LLM
- Feature involves data transformation
- Feature involves state changes
- Feature touches critical paths

---

## Summary

```
1. SANDBOX: Prove it works in isolation (run N iterations)
2. DECIDE: Go or No-Go based on evidence
3. INTEGRATE: Connect to adjacent components
4. VERIFY: Full system tests pass
5. SHIP: Only after all gates pass

The goal is NOT to add the feature.
The goal is to determine IF the feature is viable.
Some features die in sandbox. That's success, not failure.
```
