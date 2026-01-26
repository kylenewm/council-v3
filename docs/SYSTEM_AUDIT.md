# Full System Audit: Council v3, Everything-Claude-Code, and Quality System Spec

**Generated:** 2026-01-25
**Purpose:** Honest evaluation of what works, what's broken, and what to build

## TL;DR

**Council v3 has tools that exist but don't work. Everything-Claude-Code has cleaner architecture. The quality system spec we discussed earlier has good ideas but assumed Council worked.**

---

# PART A: Everything-Claude-Code - Full Inventory

## What They Have (Complete List)

### Agents (10 files)
| Agent | Purpose | Useful? |
|-------|---------|---------|
| `architect.md` | System design and architecture | Maybe - we have plan mode |
| `build-error-resolver.md` | Fix compilation/build issues | Yes - useful for autonomous |
| `code-reviewer.md` | Code quality review | Maybe - we have /review |
| `database-reviewer.md` | DB schema/query review | Niche - only if using DBs |
| `doc-updater.md` | Documentation maintenance | Low value |
| `e2e-runner.md` | Playwright E2E testing | Yes - structured E2E |
| `planner.md` | Task breakdown | Maybe - we have plan mode |
| `refactor-cleaner.md` | Code cleanup | Low value |
| `security-reviewer.md` | Security vulnerability scan | Yes - we lack this |
| `tdd-guide.md` | Test-first enforcement | Yes - addresses test fitting |

### Skills (14 folders)
| Skill | Purpose | Useful? |
|-------|---------|---------|
| `backend-patterns` | Backend code patterns | Low - generic |
| `clickhouse-io` | ClickHouse specific | No - too specific |
| `coding-standards` | Style guides | Low - we have modes |
| `continuous-learning` | Pattern capture v1 | Superseded by v2 |
| `continuous-learning-v2` | Pattern → instincts → skills | **YES - novel, we lack this** |
| `eval-harness` | Define pass/fail upfront | **YES - addresses test fitting** |
| `frontend-patterns` | Frontend patterns | Low - generic |
| `iterative-retrieval` | RAG-like retrieval | Maybe - for large codebases |
| `postgres-patterns` | Postgres specific | No - too specific |
| `project-guidelines-example` | Example config | Reference only |
| `security-review` | Security scanning | Yes - we lack this |
| `strategic-compact` | Context compaction | Maybe - for long sessions |
| `tdd-workflow` | TDD process | Yes - structured TDD |
| `verification-loop` | 6-phase verification | **YES - better than our /done** |

### Commands (11 files)
| Command | Purpose | Useful? |
|---------|---------|---------|
| `/tdd` | Start TDD workflow | Yes |
| `/plan` | Create plan | We have this |
| `/e2e` | Run E2E tests | Yes |
| `/code-review` | Trigger review | We have /review |
| `/build-fix` | Fix build errors | Yes - autonomous recovery |
| `/refactor-clean` | Cleanup code | Low value |
| `/learn` | Capture patterns | **YES - continuous learning** |
| `/checkpoint` | Save state | We have /save |
| `/verify` | Run verification | **YES - 6-phase** |
| `/setup-pm` | Setup package manager | Low value |

### Rules (6 files)
| Rule | Purpose | Useful? |
|------|---------|---------|
| `security.md` | Security guidelines | Yes |
| `coding-style.md` | Style rules | We have modes |
| `testing.md` | Testing rules | Yes - 80% coverage |
| `git-workflow.md` | Git practices | We have modes |
| `agents.md` | Agent guidelines | Reference |
| `performance.md` | Performance rules | Low value |

### Hooks (hooks.json)
| Hook | Trigger | Useful? |
|------|---------|---------|
| Dev server blocking | PreToolUse | **YES - prevents freezes** |
| Long-running command reminder | PreToolUse | Yes |
| Git push review | PreToolUse | Maybe |
| Documentation guard | PreToolUse | **YES - prevents doc sprawl** |
| Compaction suggestion | PreToolUse | Maybe |
| PR logging | PostToolUse | Low value |
| Build analysis | PostToolUse | Maybe |
| Prettier formatting | PostToolUse | Low value |
| TypeScript validation | PostToolUse | Maybe |
| Console.log warnings | PostToolUse | Yes |
| Stop: console.log check | Stop | Yes |
| Session state save | SessionEnd | We have this |
| Pattern extraction | SessionEnd | **YES - continuous learning** |

---

# PART B: Council v3 - What Works vs What's Dead

## WORKS (Keep)

| Component | Location | Status |
|-----------|----------|--------|
| Mode injection (8 modes) | `hooks/modes/*.sh` | ✅ Works, fires every prompt |
| Global rules | `hooks/global.sh` | ✅ Works |
| Framework injection | `hooks/framework.sh` | ✅ Works |
| Dispatcher routing | `dispatcher/simple.py` | ✅ Works - sends to tmux |
| Circuit breaker | `dispatcher/simple.py` | ✅ Works - opens after 3 no-progress |
| Git progress detection | `dispatcher/gitwatch.py` | ✅ Works |
| Task queue | `dispatcher/simple.py` | ✅ Works - queues tasks |
| State persistence | `~/.council/state.json` | ✅ Works |
| Socket server | `dispatcher/socket_server.py` | ✅ Works |
| Telegram bot | `dispatcher/telegram.py` | ✅ Works |
| Notifications | `dispatcher/simple.py` | ✅ Works |
| check_invariants.py | `scripts/` | ✅ Works when called manually |
| audit_done.py | `scripts/` | ✅ Works when called manually |

## DEAD CODE (Remove or Fix)

| Component | Location | Problem |
|-----------|----------|---------|
| DONE_REPORT detection | `simple.py:414-450` | transcript_path never set |
| awaiting_done_report flag | `simple.py:145` | Never set to True |
| run_auto_audit() | `simple.py:478-577` | Never called |
| format_done_status() | `simple.py:452-476` | Never shows useful info |
| auto_audit config | Agent dataclass | Defaults to False, never enabled |
| transcript_path config | Agent dataclass | Never populated |
| deprecated/ folder | `hooks/deprecated/` | 9 old scripts, delete |
| current_inject.txt refs | Various docs | Wrong file, causes confusion |

## WORKS BUT PROBLEMATIC

| Component | Problem |
|-----------|---------|
| simple.py | 1780 lines, 42 functions, needs split |
| Mode file path | Docs say current_inject.txt, code uses mode |
| TDD Guard | Exists but not installed by default |
| check_invariants | Not enforced, only manual |

---

# PART C: Quality System Spec - What Was Practical

From our earlier discussion of the quality system spec:

## KEEP (Still Valid Ideas)

| Idea | Why Keep |
|------|----------|
| **policy.yaml with gate definitions** | Formalizes what gates run for /test, /commit, /ship per mode |
| **Gate runner (council/gates.py)** | Structured gate checking before /ship |
| **Blind test concept** | Addresses test fitting - tests from another model |
| **Enhanced /config-status** | Show effective gates for current mode |
| **SPEC.md template** | Upfront criteria definition (like eval-harness) |

## REMOVE (Based on New Findings)

| Idea | Why Remove |
|------|------------|
| **RUN_LOG.md** | Already have JSONL logs in ~/.council/logs/ |
| **DONE_REPORT.md file** | Keep transcript-based, but fix detection first |
| **council/policy.py mode detection** | inject.sh already works |
| **RIPER artifact validation** | Too heavy, current modes work |
| **Manual blind test workflow** | Must automate via API or skip |

## REVISE (Based on New Findings)

| Idea | Revision |
|------|----------|
| **Fix DONE_REPORT detection** | Before adding features, fix what's broken |
| **Blind tests** | Expand to blind plan review, blind code review |
| **Verification loop** | Adopt Everything's 6-phase structure for /done |

---

# PART D: What To Actually Build

## Priority 1: Fix Broken Stuff (Before Adding Anything)

| Fix | Effort | Impact |
|-----|--------|--------|
| Wire transcript_path in config | 2h | Enables DONE_REPORT detection |
| Add awaiting_done_report=True setter | 1h | Enables status tracking |
| Enable auto_audit by default in strict | 1h | Enables audit |
| Fix mode file path in docs | 1h | Prevents confusion |
| Delete current_inject.txt refs | 1h | Cleanup |
| Delete deprecated/ folder | 0.5h | Cleanup |

**Total: ~6.5 hours to fix what's broken**

## Priority 2: Adopt from Everything-Claude-Code

| Adopt | Effort | Value |
|-------|--------|-------|
| Verification loop (6-phase /done) | 3h | High - structured verification |
| Dev server blocking hook | 1h | High - prevents freezes |
| Documentation guard hook | 1h | Medium - prevents sprawl |
| Security reviewer agent | 2h | Medium - we lack this |
| Console.log check on stop | 1h | Low but easy |

**Total: ~8 hours for high-value adoptions**

## Priority 3: Cross-Model Validation (HIGH VALUE)

**The Core Insight: Everything Benefits from a Second Perspective**

The problem isn't just tests. It's that **any single model overfits to its own understanding**:

| What Claude Does | The Overfitting Problem |
|------------------|------------------------|
| Writes tests | Tests pass buggy code (tests match implementation, not spec) |
| Writes code | Code has blind spots (same assumptions baked in) |
| Creates plans | Plans miss edge cases (same mental model) |
| Reviews own work | Misses issues it would catch in others' code |
| Writes docs | Docs assume reader knows what Claude knows |

**Another model breaks every cycle:**

| Same Model | Different Model (GPT-4, etc.) |
|------------|-------------------------------|
| Has assumption X | Never saw assumption X |
| Tests/plans assume X | Tests/plans what spec SAYS |
| Bug hidden | Bug exposed |

### 3.1 Blind Tests (Core)

| Component | Effort | Notes |
|-----------|--------|-------|
| SPEC.md template | 1h | Define interface + behavior + edge cases |
| /spec command | 1h | Create SPEC from template |
| /blind-tests via GPT API | 4h | Auto-call GPT-4, not manual Cursor |
| tests/blind/ folder | 0.5h | Isolated blind test storage |
| blind_tests gate | 1h | Run tests/blind/ before /ship |
| Spec drift detection | 1h | Warn if SPEC changed since tests generated |

**Total: ~8.5 hours**

### 3.2 Blind Plan Review (New)

Before implementing complex features, get a second model's perspective on the plan:

| Component | Effort | Notes |
|-----------|--------|-------|
| /blind-plan command | 2h | Send PLAN.md to GPT-4 for critique |
| Plan critique template | 1h | "What's missing? What could go wrong?" |
| Integration with /inject plan | 1h | Auto-suggest blind review for complex plans |

**What GPT-4 sees:** Only the PLAN.md (no chat history, no code context)
**What GPT-4 returns:** Critique, missing considerations, risks Claude didn't think of

### 3.3 Blind Code Review (New)

After implementation, get a second model's review:

| Component | Effort | Notes |
|-----------|--------|-------|
| /blind-review command | 2h | Send diff + spec to GPT-4 |
| Review criteria template | 1h | Security, edge cases, spec compliance |
| Integration with /ship | 1h | Gate on blind review for production mode |

**What GPT-4 sees:** SPEC.md + git diff (no reasoning, no chat history)
**What GPT-4 returns:** Issues, questions, concerns Claude missed

### 3.4 The Pattern Generalizes

| Blind... | Claude Produces | GPT-4 Validates | What GPT-4 Sees |
|----------|-----------------|-----------------|-----------------|
| Tests | Implementation | Tests | SPEC only |
| Plan | Plan | Critique | SPEC + constraints only |
| Review | Code | Issues | SPEC + diff only |
| Docs | Documentation | Accuracy check | SPEC + code only |

**Total for full cross-model validation: ~18 hours**

### 3.5 Implementation Priority

1. **Blind tests first** (8.5h) - Highest value, addresses test fitting
2. **Blind plan review second** (4h) - Catches architecture issues early
3. **Blind code review third** (4h) - Final check before shipping
4. **Blind docs later** - Lower priority

**Automation is mandatory.** All of these call GPT-4 API directly. No manual copy-paste workflows.

## Priority 4: Consider (Evaluate After Priorities 1-3)

| Consider | Effort | Decision Point |
|----------|--------|----------------|
| Continuous learning v2 | 10h+ | After blind testing works |
| Full gate runner | 6h | After blind tests integrated |
| TDD workflow skill | 3h | May not need if blind tests work |

---

# PART E: Recommended Order

## Phase 1: Cleanup & Fix (Week 1)
1. Delete deprecated/ folder
2. Fix mode file path in all docs
3. Delete ~/.council/current_inject.txt
4. Add transcript_path to config example
5. Wire awaiting_done_report=True
6. Enable auto_audit in strict mode
7. Test DONE_REPORT detection works

## Phase 2: Adopt High-Value (Week 2)
1. Add dev server blocking hook
2. Add documentation guard hook
3. Implement 6-phase verification loop for /done
4. Add console.log check on stop

## Phase 3: Cross-Model Validation (Week 2-3)
1. Build /spec command + SPEC.md template
2. Build /blind-tests with GPT-4 API integration
3. Build /blind-plan for plan critique
4. Build /blind-review for code review
5. Integrate blind_tests gate into /ship

## Phase 4: Dispatcher Cleanup (Week 3-4)
1. Split simple.py into modules
2. Improve error handling
3. Add better logging

---

# PART F: Summary Tables

## Everything-Claude-Code: Adopt vs Skip

| Component | Verdict | Reason |
|-----------|---------|--------|
| verification-loop | ✅ Adopt | Better than our /done |
| continuous-learning-v2 | 🤔 Evaluate | Novel but complex |
| eval-harness | ✅ Adopt concept | Define criteria upfront |
| tdd-guide agent | ✅ Adopt | Addresses test fitting |
| security-reviewer | ✅ Adopt | We lack this |
| dev-server-blocking hook | ✅ Adopt | Prevents freezes |
| documentation-guard hook | ✅ Adopt | Prevents sprawl |
| console.log check | ✅ Adopt | Easy win |
| DB-specific skills | ❌ Skip | Too specific |
| Pattern libraries | ❌ Skip | Generic, low value |

## Council v3: Keep vs Remove

| Component | Verdict | Reason |
|-----------|---------|--------|
| Mode injection | ✅ Keep | Works, valuable |
| Dispatcher routing | ✅ Keep | Essential for multi-agent |
| Circuit breaker | ✅ Keep | Works, prevents loops |
| check_invariants.py | ✅ Keep | Works, useful |
| audit_done.py | ✅ Keep | Works when called |
| DONE_REPORT detection | 🔧 Fix | Code exists, wiring broken |
| auto_audit | 🔧 Fix | Disabled by default |
| deprecated/ | ❌ Remove | Dead code |
| current_inject.txt refs | ❌ Remove | Wrong file |

## Cross-Model Validation: Build Priority

| Component | Verdict | Reason |
|-----------|---------|--------|
| /blind-tests | ✅ Build first | Addresses test overfitting |
| /blind-plan | ✅ Build second | Catches architecture issues early |
| /blind-review | ✅ Build third | Final check before ship |
| /blind-docs | 🤔 Maybe later | Lower priority |

## Original Spec: Build vs Skip

| Component | Verdict | Reason |
|-----------|---------|--------|
| policy.yaml gates | ✅ Build | Useful, small effort |
| SPEC.md template | ✅ Build | Foundation for blind validation |
| Blind tests | ✅ Build | Core value |
| Blind plan review | ✅ Build | Catches early issues |
| RUN_LOG.md | ❌ Skip | Already have JSONL |
| DONE_REPORT.md file | ❌ Skip | Transcript-based is fine |
| RIPER validation | ❌ Skip | Too heavy |
| Manual blind workflow | ❌ Skip | Must automate |

---

## Estimated Total Effort

| Phase | Hours | Risk |
|-------|-------|------|
| Phase 1: Critical Fixes | 6.5 | Low |
| Phase 2: Adopt from Everything | 8 | Low |
| Phase 3: Cross-Model Validation | 18 | Medium |
| Phase 4: Dispatcher Cleanup | 6 | Medium |
| **Total** | **38.5** | |

---

## What's Actually Broken Right Now

### DONE_REPORT: Completely Non-Functional

The mode injection tells Claude to output a DONE_REPORT. Claude does. **But nobody reads it.**

- `transcript_path` is never set in config
- `awaiting_done_report` is never set to True
- `check_done_report()` always returns False
- `run_auto_audit()` is never called
- 200+ lines of dead code

### Mode Files: Documentation Mismatch

- Hook reads: `~/.council/mode`
- Docs say: `~/.council/current_inject.txt`
- If you follow the docs, mode switching breaks

### Enforcement: Theoretical Only

- check_invariants.py exists but isn't enforced
- TDD Guard exists but isn't installed by default
- auto_audit exists but defaults to False
