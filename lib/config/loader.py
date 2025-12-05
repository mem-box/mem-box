"""Static configuration loader for Memory Box."""

import json
from pathlib import Path

# Config directory
_CONFIG_DIR = Path(__file__).parent

# Load all configurations once at module import
with (_CONFIG_DIR / "commands.json").open() as f:
    COMMANDS_CONFIG = json.load(f)

with (_CONFIG_DIR / "categories.json").open() as f:
    CATEGORIES_CONFIG = json.load(f)

with (_CONFIG_DIR / "tags.json").open() as f:
    TAGS_CONFIG = json.load(f)

with (_CONFIG_DIR / "project-types.json").open() as f:
    PROJECT_TYPES_CONFIG = json.load(f)

with (_CONFIG_DIR / "secrets.json").open() as f:
    SECRETS_CONFIG = json.load(f)

# Lookup maps
COMMAND_MAP = COMMANDS_CONFIG["commands"]
CATEGORIES_MAP = CATEGORIES_CONFIG["categories"]
TAGS_MAP = TAGS_CONFIG["tags"]
PROJECT_TYPES_MAP = PROJECT_TYPES_CONFIG["project_types"]
SECRETS_PATTERNS = SECRETS_CONFIG["patterns"]

# Build reverse lookup: indicator file -> project type
INDICATOR_MAP = {}
for project_type, config in PROJECT_TYPES_MAP.items():
    for indicator in config["indicators"]:
        if indicator not in INDICATOR_MAP:
            INDICATOR_MAP[indicator] = project_type
