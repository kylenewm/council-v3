---
description: "Start executing the Ralph queue"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/start-queue.sh:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/queue-manager.sh:*)"]
---

# Start Ralph Queue Execution

Start executing tasks from the queue:

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/start-queue.sh"
```

This will:
1. Get the first pending task from the queue
2. Set up a Ralph loop with that task
3. Begin working on it

When the task completes (via completion promise or max iterations), the queue stop hook will automatically start the next task.

Now work on the task that was just started. Follow the prompt instructions and output the completion promise when done.
