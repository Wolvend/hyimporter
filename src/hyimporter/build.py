from __future__ import annotations

import argparse
import json

from .config import load_config, map_output_dir
from .export import run_pipeline
from .importer_mcp import run_importer_mcp_review


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
    p.add_argument(
        "--skip-importer-mcp",
        action="store_true",
        help="Skip Importer_MCP post-build quality review report generation.",
    )
    p.add_argument(
        "--importer-mcp-fail-on",
        choices=["none", "needs_review", "fail"],
        default="none",
        help="Optional quality gate behavior for Importer_MCP review.",
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
    if not args.skip_importer_mcp:
        report = run_importer_mcp_review(
            map_output_dir(cfg),
            fail_on=args.importer_mcp_fail_on,
            index_with_voxelviewer=False,
        )
        summary["importer_mcp"] = {
            "verdict": report.get("verdict"),
            "score": report.get("score"),
            "review_json": str(map_output_dir(cfg) / "qa" / "importer_mcp_review.json"),
            "review_md": str(map_output_dir(cfg) / "qa" / "importer_mcp_review.md"),
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
