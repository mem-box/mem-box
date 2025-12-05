"""JSON bridge for VS Code extension communication.

This module provides a stdin/stdout JSON-RPC style interface for
VS Code extensions (or other tools) to communicate with Memory Box.

Usage:
    python -m memory_box.bridge

Communication Protocol:
    - Send: JSON object on stdin: {"method": "add_command", "params": {...}}
    - Receive: JSON response on stdout: {"result": "...", "error": null}
"""

import argparse
import json
import sys
from typing import Any

from lib import MemoryBox


def handle_request(mb: MemoryBox, request: dict[str, Any]) -> dict[str, Any]:
    """Handle a single JSON-RPC style request.

    Args:
        mb: MemoryBox instance
        request: Dictionary with 'method' and 'params' keys

    Returns:
        Response dictionary with 'result' and 'error' keys
    """
    method = request.get("method")
    params = request.get("params", {})

    # Map methods to handlers
    handlers: dict[str, Any] = {
        "add_command": lambda: mb.add_command(**params),
        "search_commands": lambda: [
            r.model_dump(mode="json") for r in mb.search_commands(**params)
        ],
        "get_command": lambda: (
            result.model_dump(mode="json") if (result := mb.get_command(**params)) else None
        ),
        "list_commands": lambda: [r.model_dump(mode="json") for r in mb.list_commands(**params)],
        "delete_command": lambda: mb.delete_command(**params),
        "get_all_tags": lambda: mb.get_all_tags(),
        "get_all_categories": lambda: mb.get_all_categories(),
        "ping": lambda: "pong",
    }

    if method not in handlers:
        return {"result": None, "error": f"Unknown method: {method}"}

    try:
        result = handlers[method]()
    except Exception as e:
        return {"result": None, "error": str(e)}
    else:
        return {"result": result, "error": None}


def write_response(response: dict[str, Any]) -> None:
    """Write JSON response to stdout.

    Args:
        response: Response dictionary to write
    """
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def main() -> None:
    """Main bridge loop - reads JSON from stdin, writes JSON to stdout."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=None, help="Neo4j URI")
    parser.add_argument("--neo4j-user", default=None, help="Neo4j username")
    parser.add_argument("--neo4j-password", default=None, help="Neo4j password")
    args = parser.parse_args()

    mb = MemoryBox(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
    )

    try:
        # Process requests line by line
        for raw_line in sys.stdin:
            cleaned_line = raw_line.strip()
            if not cleaned_line:
                continue

            try:
                request = json.loads(cleaned_line)
                response = handle_request(mb, request)
                write_response(response)

            except json.JSONDecodeError as e:
                error_response = {"result": None, "error": f"Invalid JSON: {e}"}
                write_response(error_response)

    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        sys.stderr.write("Received interrupt signal, shutting down gracefully...\n")
        sys.stderr.flush()
    finally:
        mb.close()


if __name__ == "__main__":
    main()
