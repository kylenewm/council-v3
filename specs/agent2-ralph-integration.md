# Agent 2 Task: Ralph-Wiggum Integration

## Objective

Integrate ralph-wiggum style autonomous continuation into council-v3, enhancing or replacing the existing circuit breaker.

## Background: What Ralph Does

Ralph is an iterative loop that:
1. Feeds Claude a prompt
2. Claude works until it stops
3. Stop hook intercepts and decides: continue or done?
4. If not done, feeds the same prompt again
5. Claude sees its previous work (git history, modified files)
6. Repeats until completion signal detected

**Key insight:** Claude improves iteratively because it sees its own previous attempts.

## Current State

Council-v3 has a **circuit breaker** in `simple.py`:
- Tracks git commits per check interval
- Opens after 3 iterations with no progress
- Auto-continue sends "continue" to agent

**Limitation:** Just sends "continue" - doesn't re-feed the original task or check for completion signals.

## Ralph Sources

### Official Plugin (delikat/claude-code)
- Uses Stop hook to intercept exits
- `/ralph-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"`
- Completion detected by exact string match (e.g., `<promise>COMPLETE</promise>`)

### Community Version (frankbria/ralph-claude-code)
- More sophisticated exit detection:
  - All tasks in @fix_plan.md marked complete
  - Two consecutive "done" signals
  - Three consecutive test-only loops
  - Claude's 5-hour API limit
- Circuit breaker: 3 loops no progress OR 5 loops same errors
- Session continuity with `--continue` flag
- Live monitoring dashboard

## Requirements

### 1. Ralph-Style Stop Hook

Create a Stop hook that:
1. Checks for completion signals in Claude's output
2. If not complete, re-prompts with original task
3. Tracks iteration count
4. Respects max iterations limit

```bash
# hooks/ralph-stop.sh
#!/bin/bash

MAX_ITERATIONS=${RALPH_MAX_ITERATIONS:-10}
ITERATION_FILE=~/.council/ralph_iterations

# Increment iteration count
COUNT=$(cat "$ITERATION_FILE" 2>/dev/null || echo 0)
COUNT=$((COUNT + 1))
echo $COUNT > "$ITERATION_FILE"

# Check if we should stop
if [ $COUNT -ge $MAX_ITERATIONS ]; then
  echo "Max iterations reached"
  rm "$ITERATION_FILE"
  exit 0  # Allow stop
fi

# Check for completion signals in last output
LAST_OUTPUT=$(cat ~/.claude/last_output 2>/dev/null)
if echo "$LAST_OUTPUT" | grep -q "TASK_COMPLETE\|All tests passing\|Ready for review"; then
  echo "Completion signal detected"
  rm "$ITERATION_FILE"
  exit 0  # Allow stop
fi

# Not complete - re-prompt
PROMPT_FILE=~/.council/current_prompt
if [ -f "$PROMPT_FILE" ]; then
  # Signal dispatcher to re-send prompt
  echo "CONTINUE:$(cat $PROMPT_FILE)" > ~/.council/ralph_continue
fi

exit 0
```

### 2. Dispatcher Integration

Modify dispatcher to:
1. Store original prompt when task starts
2. Check for ralph_continue signal
3. Re-send original prompt (not just "continue")

Add to `simple.py`:
```python
def check_ralph_continue(self, agent_id):
    """Check if ralph wants to re-prompt"""
    continue_file = Path.home() / ".council" / "ralph_continue"
    if continue_file.exists():
        content = continue_file.read_text()
        if content.startswith("CONTINUE:"):
            prompt = content[9:]
            continue_file.unlink()
            return prompt
    return None
```

### 3. Completion Detection

Detect completion via multiple signals:
- Explicit: `TASK_COMPLETE`, `<promise>DONE</promise>`
- Implicit: "All tests passing", "Ready for review", "No changes needed"
- Git-based: No new commits for 2 iterations (already have this)

### 4. Configuration

Add to config.yaml:
```yaml
ralph:
  enabled: true
  max_iterations: 10
  completion_signals:
    - "TASK_COMPLETE"
    - "All tests passing"
    - "Ready for review"
  circuit_breaker:
    no_progress_limit: 3
    same_error_limit: 5
```

### 5. Monitoring

Add ralph status to dispatcher's `status` command:
```
Agent 1 [Council] - READY
  Ralph: iteration 3/10, last: "Fixing test failures"
Agent 2 [Research] - WORKING
  Ralph: iteration 1/10, last: "Starting task"
```

## Files to Create/Modify

1. **Create:** `hooks/ralph-stop.sh` - Stop hook script
2. **Create:** `~/.council/ralph/` - Ralph state directory
3. **Modify:** `council/dispatcher/simple.py` - Add ralph integration
4. **Modify:** `config/config.yaml.example` - Add ralph config

## Constraints

- Do NOT modify `.claude/settings.json` (Agent 1 is working on hooks there)
- Do NOT create new notification systems (Agent 1's job)
- Integrate with existing circuit breaker, don't duplicate
- Keep it simple - don't need all of frankbria's features

## Success Criteria

1. Agent receives task, works until stops
2. Stop hook checks completion
3. If not complete, original prompt re-sent (not just "continue")
4. Iteration count tracked and limited
5. Completion signals properly detected
6. Status command shows ralph state

## Test Plan

1. Send agent a multi-step task
2. Verify it continues automatically
3. Verify it stops on completion signal
4. Verify max iterations limit works
5. Verify status shows ralph state

## Reference: frankbria Exit Detection Logic

```bash
# Completion signals (should stop)
- "all tasks.*complete" in output
- "COMPLETE" or "DONE" explicit markers
- 2+ consecutive "done" signals
- 3+ test-only loops (no code changes)

# Circuit breaker (should stop with error)
- 3 loops with no git progress
- 5 loops with same error message
- API rate limit hit
```
