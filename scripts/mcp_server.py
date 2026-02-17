#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    from hyimporter.mcp_server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
