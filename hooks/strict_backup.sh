#!/bin/bash
# Strict mode - production code, ask first, verify after
# Activated via: /inject strict

cat << 'EOF'
[CONTEXT INJECTION - STRICT MODE]
Production software with real impact.

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
EOF

exit 0
