#!/bin/bash
# Framework injection - injects build framework guidance
# Reads from .council/framework if it exists

FRAMEWORK_FILE=".council/framework"

# Check if framework is set for this project
if [[ ! -f "$FRAMEWORK_FILE" ]]; then
    exit 0
fi

FRAMEWORK=$(cat "$FRAMEWORK_FILE" | tr -d '[:space:]')

case "$FRAMEWORK" in
    mvp)
        cat << 'EOF'
[BUILD FRAMEWORK: MVP]
Speed > Perfection. Build fast, verify at end.

PROCESS:
1. Scaffold (10%) → Structure exists
2. Build Vertically (70%) → Feature + smoke test + next
3. Wire Together (10%) → Connect all pieces
4. E2E Verify (10%) → Full flow works

RULES:
- Smoke test each feature before moving on
- Don't polish during build
- No edge cases yet
- Cut scope if behind, not time

SMOKE TEST BAR:
- Does it run?
- Does happy path work?
- Can you demo it?

"Done" = Core use case works end-to-end
EOF
        ;;
    prove-first)
        cat << 'EOF'
[BUILD FRAMEWORK: PROVE FIRST]
Prove before integrate. Test at every layer.

LAYERS:
1. Sandbox (Brick) → Isolated, fixtures, N iterations
2. Integration (Building) → Connect to adjacent components
3. System (City) → Full system verification

GO/NO-GO at each layer. Some features die in sandbox - that's success.

MINIMUM ITERATIONS:
- LLM/AI: 10+
- External API: 5+
- Algorithm: 20+

RED FLAGS (cut corners):
- "It worked once"
- "I'll add tests later"
- Integrating before sandbox validation

Never integrate unproven code.
EOF
        ;;
    showcase)
        cat << 'EOF'
[BUILD FRAMEWORK: SHOWCASE DEMO]
Impressive = Sophistication + Polish + Story

PROCESS:
1. Script Demo (20%) → Write demo script before code
2. Golden Path (40%) → Only what demo needs, perfectly
3. Wow Factor (20%) → The moment that impresses
4. Polish & Practice (20%) → 10+ practice runs

THREE PILLARS:
- Visual Impact: Looks sophisticated
- Technical Depth: Is sophisticated
- Narrative Flow: Tells a story

EVERY DEMO NEEDS:
- One clear "whoa" moment
- Recovery plan for failures
- Backup video ready

Build ONLY what the demo needs. Polish that perfectly.
EOF
        ;;
    production)
        cat << 'EOF'
[BUILD FRAMEWORK: PRODUCTION SYSTEM]
AI startup quality. Works when you're not watching.

PROCESS:
1. Architecture (15%) → Design before building
2. Foundation (25%) → Infra, logging, auth, CI/CD
3. Core Features (35%) → With tests, logging, docs
4. Hardening (15%) → Security, performance
5. Launch Prep (10%) → Monitoring, runbooks

FIVE PILLARS:
1. Reliability → Handles failures gracefully
2. Observability → Logging, metrics, traces, alerts
3. Security → Auth, validation, encryption
4. Scalability → Horizontal scaling path
5. Operability → CI/CD, rollback, runbooks

NON-NEGOTIABLE:
- Tests are part of the feature
- Security is built in, not bolted on
- Structured logging from day one
- Every deploy has rollback plan

Quality bar: Would you trust this with your credit card?
EOF
        ;;
    *)
        # Unknown framework, no injection
        exit 0
        ;;
esac

exit 0
