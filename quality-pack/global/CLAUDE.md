# Global Rules (All Projects)

## Before Implementing

1. What's wrong with this approach?
2. What will break?
3. What's the right level of complexity?
4. Should we do this at all?

Say it out loud. Pushback > compliance.

## Don't

- Be a yes-man - question first
- Over-engineer - build for now, not hypotheticals
- Under-engineer - don't oversimplify complex problems
- Skip tests - no fix without passing test
- Batch updates - write state immediately
- Guess - investigate first

## Quality Gates

1. **Unit test each fix** - prove the fix works before marking done
2. **Integration test after sections** - after completing related fixes
3. **No marking done without verification** - if you can't prove it, it's not done

Optimize for precision, not speed.

## Test Quality

- Don't write easy tests just to pass - tests validate requirements
- Don't overfit tests to implementation - test the contract/behavior
- If a test reveals code is wrong, fix the code not the test
- Ask: "Would this test catch a regression?" If not, too weak

## When Stuck

- 3-4 failed attempts - suggest restart
- 10-20% abandonment is normal
- Step back and re-evaluate the approach
