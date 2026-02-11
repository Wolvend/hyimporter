from __future__ import annotations

import argparse
import json

from .config import load_config
from .export import run_pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Hytale OBJ tiles from WoW exports")
    p.add_argument("--config", required=True, help="Path to YAML config")
    p.add_argument(
        "--allow-8bit-height",
        action="store_true",
        help="Override safety gate and allow 8-bit heightmap inputs (not recommended).",
    )
    p.add_argument(
        "--sync-tiles",
        action="store_true",
        help="Disable asynchronous tile export and force deterministic single-thread mode.",
    )
    p.add_argument(
        "--tile-workers",
        type=int,
        default=None,
        help="Tile export worker count for async mode (0=auto, default from config).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if args.sync_tiles:
        cfg.runtime.async_tile_export = False
    if args.tile_workers is not None:
        if args.tile_workers < 0:
            raise ValueError("--tile-workers must be >= 0")
        cfg.runtime.tile_workers = int(args.tile_workers)
    summary = run_pipeline(cfg, allow_8bit_override=args.allow_8bit_height)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
