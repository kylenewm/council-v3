# MVP Build Framework

Build fast, verify at the end. For initial builds where speed matters more than perfection.

---

## When to Use This

- Greenfield project (nothing exists yet)
- Prototype/POC that needs to exist quickly
- Validating an idea before investing in quality
- Hackathon-style building
- "Does this concept even work?" exploration

**NOT for:**
- Adding features to existing production systems (use SANDBOX_TO_SCALE.md)
- Showcase/demo builds that need polish (use SHOWCASE_BUILD.md)
- Critical infrastructure

---

## Philosophy

```
Build → Smoke Test → Build More → Smoke Test → ... → End-to-End Verify
```

**Key insight:** Don't optimize during the build. Get it working first, then verify everything works together at the end.

---

## The Process

### Phase 1: Scaffold (10% of time)

```bash
# Create project structure
mkdir -p src tests docs
touch README.md CLAUDE.md STATE.md

# Define the skeleton
# - Main entry point
# - Core modules (empty)
# - Basic config
```

**Deliverable:** Project structure exists, can run (even if it does nothing).

### Phase 2: Build Vertically (70% of time)

Build feature by feature, top to bottom. Each feature:

1. **Implement** - Get it working (ugly is fine)
2. **Smoke test** - Does it not crash? Basic happy path works?
3. **Move on** - Don't polish, don't optimize

```
Feature 1: [Implement] → [Smoke ✓] → Next
Feature 2: [Implement] → [Smoke ✓] → Next
Feature 3: [Implement] → [Smoke ✓] → Next
...
```

**Smoke test bar:**
- Does it run without crashing?
- Does the happy path work?
- Can you demo it (even if ugly)?

**Don't do yet:**
- Error handling (beyond basic try/catch)
- Edge cases
- Performance optimization
- Code cleanup
- Documentation

### Phase 3: Wire Together (10% of time)

Connect all the pieces:

1. Hook up the full flow
2. Run end-to-end
3. Fix any integration breaks
4. Verify the core use case works

### Phase 4: End-to-End Verify (10% of time)

Now and only now, verify everything:

```bash
# 1. Full flow works
python main.py  # or npm start, etc.

# 2. Core use cases pass
python test_e2e.py

# 3. No obvious crashes
# Manual testing of main paths

# 4. Document what works and what doesn't
# Update README.md with actual status
```

---

## Parallel Building (Speed Boost)

When features are independent, build in parallel:

```
Main Agent: "Build auth system"
├── Spawn: agent-1 "Build login flow"
├── Spawn: agent-2 "Build signup flow"
├── Spawn: agent-3 "Build password reset"
└── Collect results → Wire together
```

**Rule:** Only parallelize if features don't share state.

---

## MVP Checklist

### Before Starting
- [ ] Scope is clear (what's in, what's out)
- [ ] Success criteria defined ("it works when...")
- [ ] Time box set (stop at X hours regardless)

### During Build
- [ ] Each feature gets smoke tested
- [ ] Moving fast, not polishing
- [ ] Capturing TODOs for later (not fixing now)
- [ ] No yak shaving

### Before "Done"
- [ ] Core flow works end-to-end
- [ ] Can demo the main use case
- [ ] Known issues documented
- [ ] README reflects actual state

---

## What "Done" Means for MVP

**Done = Demonstrable core functionality**

NOT:
- All edge cases handled
- Production-ready
- Fully tested
- Optimized
- Beautiful code

YES:
- Main use case works
- Can show someone
- Foundation for iteration

---

## Example: Build a CLI Todo App

### Phase 1: Scaffold (5 min)
```bash
mkdir todo-cli && cd todo-cli
touch main.py todos.json README.md
# main.py: argparse skeleton
```

### Phase 2: Build Vertically (45 min)
```
Feature: Add todo
- Implement: append to JSON file
- Smoke: python main.py add "test" → works
- Move on

Feature: List todos
- Implement: read JSON, print
- Smoke: python main.py list → shows todos
- Move on

Feature: Complete todo
- Implement: update JSON with done=true
- Smoke: python main.py done 1 → marks complete
- Move on

Feature: Delete todo
- Implement: remove from JSON
- Smoke: python main.py delete 1 → removes
- Move on
```

### Phase 3: Wire Together (5 min)
- All commands work together
- JSON stays consistent

### Phase 4: E2E Verify (5 min)
```bash
python main.py add "Buy milk"
python main.py add "Call mom"
python main.py list  # Shows both
python main.py done 1  # Marks first done
python main.py list  # Shows status
python main.py delete 2  # Removes second
python main.py list  # Shows only first
```

**Total: 1 hour → Working CLI todo app**

---

## Common Mistakes

### 1. Polishing too early
**Wrong:** Spend 30 min making the first feature perfect
**Right:** Get it working, move on

### 2. Testing edge cases during build
**Wrong:** "What if the user enters emoji?"
**Right:** That's a Phase 4 problem

### 3. Refactoring mid-build
**Wrong:** "This function is ugly, let me clean it up"
**Right:** It works. Move on. Clean up later (or never).

### 4. Building horizontally
**Wrong:** Build all models, then all views, then all controllers
**Right:** Build feature 1 fully, then feature 2 fully

### 5. No smoke tests
**Wrong:** Build 5 features, then test
**Right:** Smoke test each feature before moving on

---

## When MVP is Done, Then What?

After MVP works:

1. **Demo it** - Show someone, get feedback
2. **Decide** - Worth continuing?
3. **If yes** - Use SANDBOX_TO_SCALE.md for adding features
4. **If showcase needed** - Use SHOWCASE_BUILD.md to polish

---

## Time Boxes by Project Size

| Project | MVP Time Box | Scope |
|---------|-------------|-------|
| Micro | 1-2 hours | 1-3 features |
| Small | 4-8 hours | 5-10 features |
| Medium | 1-2 days | 10-20 features |
| Large | 1 week | 20+ features |

**Rule:** If you're not done at the time box, cut scope. Don't extend time.

---

## Summary

```
1. SCAFFOLD: Project structure (10%)
2. BUILD: Feature by feature with smoke tests (70%)
3. WIRE: Connect everything (10%)
4. VERIFY: End-to-end check (10%)

Speed > Perfection
Working > Beautiful
Demonstrable > Complete
```
