---
description: "Add tasks to Ralph queue for sequential execution"
argument-hint: '"task1" "task2" "task3" [--max-iterations N] [--completion-promise TEXT]'
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/queue-manager.sh:*)"]
---

# Ralph Queue Command

Add tasks to the Ralph queue for sequential execution. Each task should be quoted separately.

## Parse Arguments

First, add tasks to the queue:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/queue-manager.sh" add "$ARGUMENTS"
```

## Next Steps

After adding tasks, use `/ralph-queue:ralph-queue-start` to begin execution.

## Queue Behavior

When each Ralph task completes (via completion promise or max iterations):
1. The queue manager marks it complete
2. The stop hook checks for next pending task
3. If found, starts new Ralph loop with that task
4. Continues until queue empty

## Example Usage

```
/ralph-queue:ralph-queue "Implement copy-mode guard" "Implement config validation" "Add --dry-run mode" --max-iterations 20
/ralph-queue:ralph-queue-start
```
