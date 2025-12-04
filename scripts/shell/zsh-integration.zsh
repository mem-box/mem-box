#!/usr/bin/env zsh
# Memory Box Zsh Integration
# Automatically captures commands to Memory Box
#
# Usage: Add to your ~/.zshrc:
#   source /path/to/memory-box/shell/zsh-integration.zsh
#
# Configuration (optional):
#   export MEMORY_BOX_CAPTURE_SUCCESS_ONLY=1  # Only capture successful commands
#   export MEMORY_BOX_PYTHON=python3           # Python executable path

# Configuration
MEMORY_BOX_CAPTURE_SUCCESS_ONLY="${MEMORY_BOX_CAPTURE_SUCCESS_ONLY:-0}"
MEMORY_BOX_PYTHON="${MEMORY_BOX_PYTHON:-python3}"

# Store the last command
typeset -g __memory_box_last_command=""

# Called before command execution
__memory_box_preexec() {
    __memory_box_last_command="$1"
}

# Called after command execution (before displaying prompt)
__memory_box_precmd() {
    local exit_code=$?

    # Skip if no command or if it's the memory-box capture command itself
    if [[ -z "$__memory_box_last_command" ]] || [[ "$__memory_box_last_command" == *"memory-box capture"* ]]; then
        __memory_box_last_command=""
        return
    fi

    # Capture the command
    local success_only_flag=""
    if [[ "$MEMORY_BOX_CAPTURE_SUCCESS_ONLY" == "1" ]]; then
        success_only_flag="--success-only"
    fi

    # Run capture in background to avoid blocking the prompt
    "$MEMORY_BOX_PYTHON" -m server.cli capture \
        "$__memory_box_last_command" \
        --exit-code "$exit_code" \
        --cwd "$PWD" \
        $success_only_flag \
        2>/dev/null &

    # Clear the command
    __memory_box_last_command=""
}

# Register hooks
# Zsh has native hook support
autoload -Uz add-zsh-hook
add-zsh-hook preexec __memory_box_preexec
add-zsh-hook precmd __memory_box_precmd

echo "Memory Box zsh integration loaded. Commands will be automatically captured."
