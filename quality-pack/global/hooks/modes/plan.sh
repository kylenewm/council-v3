#!/bin/bash
# Plan mode - design before building
# For complex features, architectural changes, multi-step tasks
# Activated via: /inject plan

cat << 'EOF'
[CONTEXT INJECTION - PLAN MODE]
Thoroughness over speed. Design before building.

BEFORE any code:
1. Break into phases with clear deliverables
2. Identify invariants that must not break
3. Check ARCHITECTURE.md for existing patterns
4. Define success metrics per phase

PHASE STRUCTURE:
## Phase N: [Name]
- Problem: What's broken/missing
- Solution: Implementation approach
- Files: Exact locations
- Tests: How to verify
- Done: Success criteria

OUTPUT:
- Structured plan document
- Wait for approval before implementing
- Present options with tradeoffs if uncertain

A good plan prevents wasted work.
EOF

exit 0
