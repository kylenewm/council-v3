#!/bin/bash
# Sandbox mode - quick POC/test building
# Based on deep-research-v0 patterns
# Activated via: /inject sandbox

cat << 'EOF'
[CONTEXT INJECTION - SANDBOX MODE]
Quick POC for rapid iteration. Move fast, respect invariants.

PATTERNS:
1. Fixtures first - capture real data once, iterate infinitely
2. Decouple expensive (API/LLM) from cheap (filtering/logic)
3. test_mode configs - smaller limits, skip reviews
4. Structured metrics: pass/fail + timing + quality scores
5. Tier fixtures: core (~30s) vs extended (full check)

WORKFLOW:
1. Capture: Real data → save intermediate state
2. Iterate: Replay cached state (zero API cost)
3. Validate: Metrics pass before integrating

Skip elaborate error handling. Hardcode where sensible.
EOF

exit 0
