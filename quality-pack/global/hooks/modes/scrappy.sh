#!/bin/bash
# Scrappy mode - rapid integration/validation at scale
# For: bulk operations, URL testing, data parsing, experiments
# Activated via: /inject scrappy

cat << 'EOF'
[CONTEXT INJECTION - SCRAPPY MODE]
Fast AND thorough. Brute force is fine. Use more compute.

SKIP:
- No DONE_REPORT required
- No upfront file reading (except INVARIANTS.md - always check)
- No elaborate error handling
- No premature optimization

SAFETY FLOOR:
- STILL respect invariants (forbidden paths, protected files)
- Don't touch .env, credentials, secrets
- Scrappy != reckless

DO:
1. Try immediately, see what happens
2. If broken - fix and retry (max 3 attempts per item)
3. Parallelize where possible
4. Use more API calls/simulations if it gets better results
5. Batch similar operations
6. Brute force > clever when time matters

ALLOWED:
- Multiple retries with variations
- Redundant checks for confidence
- Over-fetching then filtering
- Running things multiple ways to compare

OUTPUT:
- Working result OR "doesn't work: X"
- Summary: N/M succeeded, key failures listed

Efficiency over elegance. Scale aggressively. Get to the answer.
EOF

exit 0
