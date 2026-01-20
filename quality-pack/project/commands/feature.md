# Feature Workflow

Structured approach for implementing new features.

## What This Does

Starts in plan mode for design, then switches to strict mode for implementation.

## Steps

### Phase 1: Planning

1. **Set plan mode**
```bash
echo "plan" > .council/mode
```
Confirm: "Feature planning mode activated"

2. **Read similar features first**
   - Find existing features that work similarly
   - Understand the patterns used
   - Note conventions to follow

3. **Design the feature**
   - Break into phases with clear deliverables
   - Identify files to create/modify
   - Define tests that will prove it works
   - List risks and edge cases

4. **Present plan**
   - Show plan to user
   - Ask: "Does this approach look right? Any concerns?"
   - Wait for approval before implementing

### Phase 2: Implementation

5. **Set strict mode**
```bash
echo "strict" > .council/mode
```
Confirm: "Implementation mode activated (strict)"

6. **Implement phase by phase**
   - Complete one phase at a time
   - Test after each phase
   - Don't move on until current phase works

7. **Write tests**
   - Tests are part of the feature, not afterthought
   - Cover happy path and edge cases
   - If unsure what to test, ask

8. **Final verification**
   - Run full test suite
   - Review against original requirements
   - Ask: "Does this meet your requirements?"

## Anti-Patterns (Don't Do These)

- Don't over-engineer - build for now, not hypotheticals
- Don't skip the planning phase for complex features
- Don't implement without understanding existing patterns
- Don't add extra features beyond what was asked
- Don't write tests after the fact - write them as you go

## Exit Criteria

- Feature works as specified
- All tests pass
- Follows existing patterns
- User confirmed it meets requirements
