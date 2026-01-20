# Refactor Workflow

Structured approach for refactoring code safely.

## What This Does

Refactoring changes structure without changing behavior. This workflow ensures tests stay green throughout.

## Steps

1. **Set strict mode**
```bash
echo "strict" > .council/mode
```
Confirm: "Refactor mode activated (strict + tests-must-stay-green)"

2. **Run tests first**
   - Establish baseline - all tests must pass before refactoring
   - If tests fail, fix them first or ask user which to skip

3. **Understand the code**
   - Read the code to be refactored
   - Identify all callers/dependencies
   - Document current behavior

4. **Plan the refactor**
   - Break into small, testable steps
   - Each step should leave tests green
   - Identify risk points

5. **Refactor incrementally**
   - Make one change at a time
   - Run tests after each change
   - If tests fail, revert and try smaller step

6. **Do NOT change behavior**
   - Refactoring = same behavior, better structure
   - If you find a bug, fix it separately (after refactor)
   - If you want new behavior, that's a feature (after refactor)

7. **Clean up dead code**
   - Remove unused code completely
   - Don't leave commented-out code
   - Don't leave TODO comments for removed features

8. **Final verification**
   - All tests pass
   - No dead code
   - Behavior unchanged

## Anti-Patterns (Don't Do These)

- Don't change behavior during refactor
- Don't leave dead code behind
- Don't refactor without tests
- Don't make large changes in one step
- Don't fix bugs during refactor (note them, fix after)

## Exit Criteria

- All tests pass (same as before)
- Code structure improved
- No dead code
- Behavior unchanged
- User approved the changes
