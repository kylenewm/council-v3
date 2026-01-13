#!/bin/bash
# Cross-Project Workflow Simulation Setup (V4 - Corrected)
# Creates 3 mock projects with git repos and tmux panes.
# NO FIFOs - dispatcher uses tmux send-keys directly.

set -e

echo "=== Setting up simulation environment ==="

# Create mock projects
for name in council research codeflow; do
    dir="/tmp/sim-$name"
    echo "Creating $dir..."
    rm -rf "$dir"
    mkdir -p "$dir"
    cd "$dir"

    # Git setup with identity
    git init -q
    git config user.email "sim@example.com"
    git config user.name "sim"
    echo "# $name" > README.md
    echo "" > STATE.md
    git add . && git commit -q -m "init"
done

echo "Mock projects created."

# Create tmux session
echo "Creating tmux session 'sim'..."
tmux kill-session -t sim 2>/dev/null || true
tmux new-session -d -s sim -c /tmp/sim-council -n main

# Split panes
tmux split-window -h -t sim:main -c /tmp/sim-research
tmux select-pane -t sim:main.0
tmux split-window -v -t sim:main.0 -c /tmp/sim-codeflow

# Capture stable pane IDs
PANE_COUNCIL=$(tmux display-message -p -t sim:main.0 '#{pane_id}')
PANE_CODEFLOW=$(tmux display-message -p -t sim:main.1 '#{pane_id}')
PANE_RESEARCH=$(tmux display-message -p -t sim:main.2 '#{pane_id}')

echo "Pane IDs:"
echo "  Agent 1 (Council):  $PANE_COUNCIL -> /tmp/sim-council"
echo "  Agent 2 (Research): $PANE_RESEARCH -> /tmp/sim-research"
echo "  Agent 3 (Codeflow): $PANE_CODEFLOW -> /tmp/sim-codeflow"

# Generate config
echo "Generating test config..."
mkdir -p ~/.council
cat > ~/.council/test-config.yaml << EOF
agents:
  1:
    pane_id: "$PANE_COUNCIL"
    name: "Council-Sim"
    worktree: /tmp/sim-council
  2:
    pane_id: "$PANE_RESEARCH"
    name: "Research-Sim"
    worktree: /tmp/sim-research
  3:
    pane_id: "$PANE_CODEFLOW"
    name: "Codeflow-Sim"
    worktree: /tmp/sim-codeflow

poll_interval: 1.0
EOF

echo ""
echo "=== Simulation Ready ==="
echo ""
echo "Config: ~/.council/test-config.yaml"
echo ""
echo "To attach: tmux attach -t sim"
echo ""
echo "To test dispatcher:"
echo "  python -m council.dispatcher.simple ~/.council/test-config.yaml"
echo ""
