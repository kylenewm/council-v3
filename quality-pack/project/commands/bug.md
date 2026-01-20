# Bug Fix Workflow

Structured approach for fixing bugs safely.

## What This Does

Sets up strict mode with bug-specific anti-patterns and gates.

## Steps

1. **Set mode**
```bash
echo "strict" > .council/mode
```
Confirm: "Bug fix mode activated (strict + verification gates)"

2. **Understand the bug first**
   - Ask user to describe the bug or provide reproduction steps
   - If error message exists, read it carefully
   - Identify the affected file(s)

3. **Reproduce before fixing**
   - Run the failing test or reproduction case
   - Confirm you can see the bug
   - If you can't reproduce, ask for more details

4. **Read before changing**
   - Read the affected file(s) completely
   - Understand the surrounding code
   - Check for related tests

5. **Make minimal fix**
   - Fix only what's broken
   - Don't refactor unrelated code
   - Don't "improve" adjacent code

6. **Verify the fix**
   - Run the specific failing test
   - Run the full test suite
   - Confirm no regressions

7. **Human gate before commit**
   - Show the diff
   - Ask: "Does this fix look correct? Any unintended changes?"
   - Wait for approval

## Anti-Patterns (Don't Do These)

- Don't modify unrelated files
- Don't change tests to match broken code
- Don't add features while fixing bugs
- Don't refactor while fixing bugs
- Don't assume - verify the bug exists first

## Exit Criteria

- Bug is fixed (verified by test)
- No regressions (all tests pass)
- Minimal diff (only bug-related changes)
- User approved the fix
