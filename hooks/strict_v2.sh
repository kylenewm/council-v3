#!/bin/bash
# Strict mode - production code, evidence over narrative
# Activated via: /inject strict

cat << 'EOF'
[CONTEXT INJECTION - STRICT MODE]
Production software. Evidence over narrative.

BEFORE:
1. Read INVARIANTS.md, STATE.md, CLAUDE.md
2. Read files before editing - never guess
3. Large scope? State: goal, constraints, acceptance criteria, tests

DURING:
1. Test after each significant change
2. Don't add features beyond request
3. 2 failures on same error → STOP, summarize, propose alternative
4. Task > 30 min? Split into 3-7 micro-tasks, implement first only

DONE (required - auditable):
```
DONE_REPORT:
- changed_files: [git diff --name-only]
- commands_run: [exact commands + exit codes]
- test_output: [summary or last N lines]
- invariants: [check_invariants.py result]
- next_actions: [if any]
```

If you can't fill DONE_REPORT with real outputs, you're not done.
EOF

exit 0
