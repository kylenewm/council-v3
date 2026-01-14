#!/bin/bash
# Start Council with 4 agents
# Usage: ./scripts/start-council.sh

set -e

SESSION="council"

# Check if session exists
if tmux has-session -t $SESSION 2>/dev/null; then
    echo "Session '$SESSION' already exists."
    echo "Attach with: tmux attach -t $SESSION"
    echo "Or kill it:  tmux kill-session -t $SESSION"
    exit 1
fi

echo "=== Starting Council ==="

# Create session with first pane (codeflow-viz)
tmux new-session -d -s $SESSION -c ~/Downloads/codeflow-viz -n main

# Split for other agents
tmux split-window -h -t $SESSION:main -c ~/Downloads/council-v3
tmux split-window -v -t $SESSION:main.0 -c ~/Downloads/deep-research-v0
tmux split-window -v -t $SESSION:main.1 -c ~/Downloads/voice-agent-eval

# Get pane IDs
PANE0=$(tmux display-message -p -t $SESSION:main.0 '#{pane_id}')
PANE1=$(tmux display-message -p -t $SESSION:main.1 '#{pane_id}')
PANE2=$(tmux display-message -p -t $SESSION:main.2 '#{pane_id}')
PANE3=$(tmux display-message -p -t $SESSION:main.3 '#{pane_id}')

echo "Panes created:"
echo "  $PANE0 → codeflow-viz"
echo "  $PANE1 → council-v3"
echo "  $PANE2 → deep-research-v0"
echo "  $PANE3 → voice-agent-eval"

# Update config - preserve existing credentials if config exists
if [[ -f ~/.council/config.yaml ]]; then
    # Just update pane IDs in existing config
    sed -i '' "s/pane_id: \"%.*/pane_id: \"$PANE0\"/" ~/.council/config.yaml 2>/dev/null || true
    # Note: This simple sed only updates first match. For full update, manually edit config.
    echo "Config exists - you may need to update pane_ids manually if they changed"
    echo "  Agent 1: $PANE0, Agent 2: $PANE1, Agent 3: $PANE2, Agent 4: $PANE3"
else
    # Create new config with placeholders (NO CREDENTIALS - user must add)
    cat > ~/.council/config.yaml << 'CONFIGEOF'
# Council v3 Configuration
# NOTE: Add your credentials below before running dispatcher

agents:
  1:
    pane_id: "%0"  # Update with actual pane ID
    name: "Agent1"
    worktree: ~/your-project-1
  2:
    pane_id: "%1"
    name: "Agent2"
    worktree: ~/your-project-2

fifo_path: ~/.council/in.fifo
poll_interval: 2.0

# Get from Pushover app
pushover:
  user_key: YOUR_PUSHOVER_USER_KEY
  api_token: YOUR_PUSHOVER_API_TOKEN

# Get from @BotFather on Telegram
telegram:
  bot_token: YOUR_TELEGRAM_BOT_TOKEN
  allowed_user_ids: [YOUR_TELEGRAM_USER_ID]
CONFIGEOF
    echo "Created ~/.council/config.yaml - ADD YOUR CREDENTIALS before running"
fi

# Start claude in each pane
echo "Starting claude in each pane..."
tmux send-keys -t $PANE0 "claude" Enter
tmux send-keys -t $PANE1 "claude" Enter
tmux send-keys -t $PANE2 "claude" Enter
tmux send-keys -t $PANE3 "claude" Enter

echo ""
echo "=== Council Ready ==="
echo ""
echo "Attach:     tmux attach -t $SESSION"
echo "Dispatcher: python3 -m council.dispatcher.simple"
echo ""
