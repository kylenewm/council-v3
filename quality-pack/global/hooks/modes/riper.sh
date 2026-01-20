#!/bin/bash
# RIPER mode - 5-phase structured workflow for complex tasks
# Research - Innovate - Plan - Execute - Review
# Activated via: /inject riper

cat << 'EOF'
[CONTEXT INJECTION - RIPER MODE]
5-phase structured workflow. One phase at a time.

PHASES:
1. RESEARCH - Understand the problem space
   - Read relevant code, docs, existing patterns
   - Identify constraints and requirements
   - Note unknowns and assumptions
   - OUTPUT: Summary of findings, key constraints, open questions

2. INNOVATE - Brainstorm approaches
   - Generate 2-3 possible solutions
   - Don't evaluate yet, just explore
   - Consider both obvious and creative approaches
   - OUTPUT: List of approaches with brief descriptions

3. PLAN - Design the implementation
   - Pick the best approach with reasoning
   - Break into concrete steps
   - Identify risks and mitigation
   - Define success criteria
   - OUTPUT: Detailed plan with phases, files, tests

4. EXECUTE - Implement with strict mode
   - Follow the plan exactly
   - Test after each step
   - Don't deviate without explicit approval
   - OUTPUT: Working code, passing tests

5. REVIEW - Verify and clean up
   - Run full test suite
   - Check for edge cases
   - Remove dead code
   - Verify against original requirements
   - OUTPUT: DONE_REPORT with evidence

RULES:
- Complete each phase before moving to next
- Get approval between phases for complex work
- If new requirements emerge, go back to relevant phase
- Use /inject strict when entering EXECUTE phase

Current phase: [STATE WHICH PHASE]
EOF

exit 0
