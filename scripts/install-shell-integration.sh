#!/usr/bin/env bash
# Memory Box Shell Integration Installer
# Automatically adds Memory Box integration to your shell config

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Memory Box Shell Integration Installer${NC}\n"

# Detect shell
SHELL_NAME=$(basename "$SHELL")
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "Detected shell: ${GREEN}$SHELL_NAME${NC}"
echo -e "Repository: ${BLUE}$REPO_DIR${NC}\n"

# Determine which shell config file to use
case "$SHELL_NAME" in
    bash)
        CONFIG_FILE="$HOME/.bashrc"
        INTEGRATION_FILE="$REPO_DIR/scripts/shell/bash-integration.sh"
        ;;
    zsh)
        CONFIG_FILE="$HOME/.zshrc"
        INTEGRATION_FILE="$REPO_DIR/scripts/shell/zsh-integration.zsh"
        ;;
    *)
        echo -e "${RED}Unsupported shell: $SHELL_NAME${NC}"
        echo "Currently supported: bash, zsh"
        exit 1
        ;;
esac

# Check if integration file exists
if [[ ! -f "$INTEGRATION_FILE" ]]; then
    echo -e "${RED}Error: Integration file not found: $INTEGRATION_FILE${NC}"
    exit 1
fi

# Check if already installed
if grep -q "memory-box.*integration" "$CONFIG_FILE" 2>/dev/null; then
    echo -e "${YELLOW}Memory Box integration already installed in $CONFIG_FILE${NC}"
    echo -e "If you want to reinstall, please remove the existing lines first."
    exit 0
fi

# Ask for confirmation
echo -e "This will add Memory Box integration to: ${GREEN}$CONFIG_FILE${NC}"
echo -e "\nConfiguration options:"
read -p "Only capture successful commands (exit code 0)? [y/N]: " SUCCESS_ONLY

# Prepare the integration block
INTEGRATION_BLOCK="
# Memory Box - Automatic command capture
export MEMORY_BOX_PYTHON=\"${MEMORY_BOX_PYTHON:-python3}\"
"

if [[ "$SUCCESS_ONLY" =~ ^[Yy]$ ]]; then
    INTEGRATION_BLOCK+="export MEMORY_BOX_CAPTURE_SUCCESS_ONLY=1
"
fi

INTEGRATION_BLOCK+="source \"$INTEGRATION_FILE\"
"

# Backup existing config
if [[ -f "$CONFIG_FILE" ]]; then
    BACKUP_FILE="${CONFIG_FILE}.backup-$(date +%Y%m%d-%H%M%S)"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo -e "${GREEN}✓${NC} Backed up existing config to: $BACKUP_FILE"
fi

# Add integration
echo "$INTEGRATION_BLOCK" >> "$CONFIG_FILE"

echo -e "\n${GREEN}✓ Memory Box shell integration installed!${NC}\n"
echo -e "To activate in current session, run:"
echo -e "  ${BLUE}source $CONFIG_FILE${NC}\n"
echo -e "Or simply open a new terminal.\n"

echo -e "Configuration:"
echo -e "  • Integration file: ${BLUE}$INTEGRATION_FILE${NC}"
echo -e "  • Python: ${BLUE}${MEMORY_BOX_PYTHON:-python3}${NC}"
echo -e "  • Success only: ${BLUE}$([ "$SUCCESS_ONLY" = "y" ] || [ "$SUCCESS_ONLY" = "Y" ] && echo "Yes" || echo "No")${NC}"

echo -e "\n${YELLOW}Note:${NC} Make sure Memory Box is installed:"
echo -e "  ${BLUE}uv sync${NC}"
