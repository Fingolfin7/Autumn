"""Compatibility entry point for the packaged Autumn MCP server."""

try:
    from autumn_cli.mcp_server import main, mcp
except ModuleNotFoundError as exc:
    if exc.name != "autumn_cli":
        raise
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "cli"))
    from autumn_cli.mcp_server import main, mcp


if __name__ == "__main__":
    main()
