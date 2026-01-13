# STATE.md

## Latest: Eval Audit (2026-01-12)

**deep-research-v0 eval infrastructure audit:**
- Created EVAL_AUDIT_2026-01-12.md with full status matrix
- Found citation_sandbox + resynthesis_test.py measured wrong metric (fact usage vs accuracy)
- Fixed resynthesis_test.py → now checks citation ACCURACY via LLM
- Results: 96% accuracy (52/55 correct), found 3 real mismatches

**Remaining eval gaps:**
- Source authority distribution
- Query answering eval
- Search quality measurement

---

## Current Phase: Demo Enhancement (2026-01-12)

**Current Work:**
- ✅ LLM Council layer migrated from v2 (council.py, client.py, cli.py, bootstrap.py)
- ✅ Architecture documentation created (4 HTML visual docs)
- ✅ docs/demo.html - Full animated end-to-end demo (28 seconds)
- 🔄 Restructuring demo layout + adding flow visualization

**Demo Enhancement Plan:**

### 1. Terminal Layout Restructure
Current: Agent 1 terminal at bottom, mini terminals (2,3) in right column
New layout:
```
[Agent 2 mini] [Agent 3 mini]   <- top row, each ~25% width
[      Agent 1 main         ]   <- bottom row, full width
```
- Move mini terminals out of output column
- Create grid layout for terminal section
- Agent 1 gets more visual prominence

### 2. Animated Flow Trail
Add visual trace showing data flow through system:
```
Telegram → LLM Council → Dispatcher → Agent 1 → Pushover
```
- SVG or CSS-based animated line/pulse
- Highlights active component as flow moves through
- Makes the architecture immediately understandable

### 3. Current Demo Features
- Telegram voice input (Wispr Flow transcription)
- LLM Council with Opus 4.5 vs GPT-5.2 debate
- Dispatcher routing to Agent 1
- Parallel agents (2: interactive tour, 3: eval harness)
- Pushover + Mac notification output
- Loop indicator for continuous workflow

**Remaining tasks:**
1. Restructure terminal layout (grid with 2+3 top, 1 bottom)
2. Add animated flow trail
3. Record as MP4
4. Update README with video + value prop
5. Commit and push

**Agent Configuration:**
| Agent | Project | Task |
|-------|---------|------|
| Agent 1 (CodeflowViz) | codeflow-viz | Building Council execution trace visualization |
| Agent 2 (DeepResearch) | deep-research-v0 | Investigating citation rate metrics |

**LLM Council Layer (Newly Migrated):**
- `council/council.py` - Multi-model draft/critique/synthesis via OpenRouter
- `council/client.py` - OpenRouter API client
- `council/cli.py` - CLI commands (`council` entrypoint)
- `council/bootstrap.py` - Project bootstrapping

---

## Original Build (2026-01-12)

Building council-v3 as hybrid of:
1. **Dispatcher** (from council-v2) - FIFO, Pushover, Telegram, tmux routing
2. **Boris Setup** (community interpretation) - .claude/agents, commands, settings, CLAUDE.md
3. **Simplified guardrails** - circuit breaker (no-progress only), optional gitwatch

## Research Complete

See `CLAUDE-RESEARCH.md` for full analysis.

**Key finding:** The bcherny-claude repo is a community interpretation, not Boris's actual files.

**Council-v3 has 80-90% of Boris's PUBLIC setup:**
- ✅ All 5 agents (identical structure)
- ✅ 13 commands (superset of Boris's 5)
- ✅ PostToolUse, Stop, Notification hooks
- ❌ MCP integrations (Slack, BigQuery, Sentry)
- ❌ GitHub action (@.claude on PRs)

**Better repos exist** (claude-code-showcase has 4.1k stars) but council-v3's unique value is the dispatcher (voice, phone, multi-agent routing).

## Architecture

```
council-v3/
├── council/
│   ├── council.py         # LLM Council - multi-model planning
│   ├── client.py          # OpenRouter API client
│   ├── cli.py             # CLI entrypoint
│   ├── bootstrap.py       # Project bootstrapping
│   └── dispatcher/
│       └── simple.py      # ~650 lines (routing + circuit breaker + task queue)
├── .claude/
│   ├── agents/            # code-architect, verify-app, code-simplifier, etc.
│   ├── commands/          # commit, ship, test-cycle, etc.
│   └── settings.json      # permissions + Stop hooks for notifications
├── CLAUDE.md              # Project memory
├── STATE.md               # Current work
└── LOG.md                 # History
```

## What's Different from council-v2

| Removed | Why |
|---------|-----|
| tasks.py | Agents use TodoWrite |
| Error signature extraction | Overkill |
| Task file parsing | Agents manage own todos |

| Kept | Why |
|------|-----|
| FIFO input | Voice routing (unique value) |
| Pushover | Phone notifications (unique value) |
| Telegram | Phone commands (unique value) |
| tmux routing | Multi-agent dispatch |
| Circuit breaker | Stuck detection (simplified) |

| Added | Why |
|-------|-----|
| .claude/agents/ | Boris-style subagents |
| .claude/commands/ | Workflow automation |
| Stop hooks | Native notifications |

## Implementation Progress

- [x] Create council-v3 repo
- [x] Clone Boris template
- [x] Copy Boris .claude/ structure (agents, commands, settings, skills)
- [x] Copy essential dispatcher from council-v2 (gitwatch.py, telegram.py)
- [x] Simplify simple.py (1095 -> 875 lines)
- [x] Add Stop hooks for notifications
- [x] Create CLAUDE.md
- [x] Test with real agents - ALL 4 DETECTED, ROUTING WORKS
- [x] Copy custom commands from council-v2
- [x] Merge Boris + custom commands + Notification hook
- [x] Update config to 2 agents (Council + DeepResearch)
- [x] Reset state.json for clean circuits
- [x] Sandbox test Boris components - ALL PASSED
- [x] Research Boris's actual setup vs community repos
- [x] Document findings in CLAUDE-RESEARCH.md

## Shared Setup

Both projects (codeflow-viz, deep-research-v0) have:
- ✅ 5 Boris agents (code-architect, verify-app, etc.)
- ✅ Stop hook for rich notifications
- ✅ Boris-style workflow documentation

## v1 Features Complete

- [x] Rich notifications (Stop hook + Pushover)
- [x] Ralph plugin installed and documented
- [x] power() function added to sandbox calculator
- [x] modulo() function added to sandbox calculator
- [x] CLAUDE-RESEARCH.md with Boris comparison
- [x] QUIRKS.md with common issues
- [x] Push to GitHub - all changes pushed to origin
- [x] Notification system tested end-to-end (Mac + Pushover)
- [x] Dispatcher writes current_task.txt for rich notifications
- [x] **Dispatcher test suite** - 57 tests covering state detection, command parsing, circuit breaker, tmux
- [x] **Task queue system** - Send multiple pipe-separated tasks, execute sequentially (84 tests total)

## Future Tasks

All planned features complete. Remaining ideas evaluated and skipped:

- ~~Task queue system~~ - DONE
- ~~Cross-agent visibility~~ - SKIP (agents on separate projects, not useful)
- ~~Voice command parsing~~ - SKIP (working fine)
- ~~Status dashboard~~ - SKIP (`status` command sufficient)

**Philosophy:** Build for friction, not features. Add when real pain points emerge.

## How to Run

```bash
# Start dispatcher
python -m council.dispatcher.simple

# Commands:
#   1: <text>       Send to agent 1
#   1: t1 | t2      Send t1 now, queue t2
#   queue 1         Show queue
#   clear 1         Clear queue
#   status          Show all agents
#   quit            Exit
```

---

## Cross-Project Work: deep-research-v0 Eval Framework (2026-01-12)

### Current Status
Eval framework complete and tuned. All code review issues resolved (4 fixed, 6 were false positives).

### What Was Built
Standalone evaluation framework for research pipeline quality:
- `eval/run_eval.py` - CLI runner
- `eval/metrics.py` - Thresholds and EvalResult dataclass
- `eval/prompts/upstream_eval.txt` - Fact quality prompt
- `eval/prompts/downstream_eval.txt` - Citation accuracy prompt

### Latest Results (15 facts, mini mode)
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Fact quality | 4.33 | ≥3.5 | ✅ |
| Theme coverage | 4.20 | ≥3.5 | ✅ |
| Duplicate rate | 0.0% | ≤15% | ✅ |
| Citation accuracy | 4.80 | ≥4.0 | ✅ |
| Uncited rate | 7.7% | ≤5% | ⚠️ |

### Optimization Work (2026-01-12)

**Table artifact fix:**
- Problem: 37/43 facts had markdown table pipes (`| cell |`)
- Fix: Lowered pipe threshold from >3 to >=2 in pointer_extract.py
- Result: match_score 0.63 → 0.76, 0 table artifacts

**Synthesis prompt strengthening:**
- Problem: 27% uncited rate on new runs
- Fix: Added explicit GOOD/BAD examples, raised target 80%→90%
- Verified: citation_sandbox 100%, eval no regression

**Next:** Re-run synthesis on saved facts to verify improvement without full pipeline

### Code Review Findings

**Eval Framework (FIXED):**
- ✅ LLM response validation
- ✅ Type safety on match_score
- ✅ Null check patterns
- ✅ LLM error handling
- ✅ Prompt injection protection
- ✅ Empty dataset rejection
- ✅ "full" mode fix
- ✅ gold_dir existence check

**Deep Research Codebase (ALL RESOLVED 2026-01-12):**

| # | File | Issue | Resolution |
|---|------|-------|------------|
| 1 | safeguarded_report.py:108-122 | LLM call no error handling | ✅ FIXED - Added try/except + empty response check |
| 2 | safeguarded_report.py:111 | "Invalid" model name | ✅ OK - gpt-4.1-mini is valid |
| 3 | pointer_extract.py:340 | IndexError on empty | ✅ OK - Already has `if candidates else 0.0` |
| 4 | verification.py:316 | None key collision | ✅ FIXED - Added `if s.get('url')` filter |
| 5 | utils.py:789-792 | Index out of range | ✅ OK - startswith guarantees 2+ elements |
| 6 | pipeline_v2.py:542-545 | Unvalidated LLM IDs | ✅ OK - Has bounds check `if 0 <= idx < len()` |
| 7 | graph.py:41-44, 58-61 | Config null checks | ✅ OK - Uses `getattr(x, 'attr', default)` |
| 8 | state.py:148-149 | Reducer crash on None | ✅ FIXED - Added None check, defaults to [] |
| 9 | verification.py:240-241 | Unprotected API calls | ✅ OK - Wrapped in try/except (lines 239-333) |
| 10 | claim_gate.py:162-168 | Unvalidated structured output | ✅ FIXED - Added type validation |

**Summary:** 4 real fixes, 6 false positives (code already had proper handling)
