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

# Update config with new pane IDs
cat > ~/.council/config.yaml << EOF
# Council v3 Configuration (auto-generated)
agents:
  1:
    pane_id: "$PANE0"
    name: "CodeflowViz"
    worktree: ~/Downloads/codeflow-viz
  2:
    pane_id: "$PANE1"
    name: "Council"
    worktree: ~/Downloads/council-v3
  3:
    pane_id: "$PANE2"
    name: "DeepResearch"
    worktree: ~/Downloads/deep-research-v0
  4:
    pane_id: "$PANE3"
    name: "VoiceAgentEval"
    worktree: ~/Downloads/voice-agent-eval

fifo_path: ~/.council/in.fifo
poll_interval: 2.0

pushover:
  user_key: uwzyipxuofop8di6ov3faipv4wbp2i
  api_token: aiqquvw4adzdjaqaqm3ge47txsfuqk

telegram:
  bot_token: "8542901362:AAHbTrx9UMS-sinyqDyRET52AXtCODqhQAI"
  allowed_user_ids: [8595421506]
EOF

echo "Config updated: ~/.council/config.yaml"

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
