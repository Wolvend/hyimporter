from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def _read_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _read_manifest_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _safe_float(x: object, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: object, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def evaluate_results(
    summary: Dict[str, object],
    manifest_rows: List[Dict[str, str]],
    *,
    expected_min_y: int = 0,
    expected_max_y: int = 319,
    max_good_speckle: float = 0.12,
    max_warn_speckle: float = 0.20,
    max_material_dominance: float = 0.95,
) -> Dict[str, object]:
    qa = summary.get("qa", {})
    height_stats = summary.get("height_stats", {})
    warnings = summary.get("warnings", [])

    seam_max_diff = _safe_int(qa.get("seam_max_diff", 9999)) if isinstance(qa, dict) else 9999
    speckle_rate = _safe_float(qa.get("speckle_rate", 1.0)) if isinstance(qa, dict) else 1.0
    y_min = _safe_int(height_stats.get("min", -1)) if isinstance(height_stats, dict) else -1
    y_max = _safe_int(height_stats.get("max", 9999)) if isinstance(height_stats, dict) else 9999
    material_cov = qa.get("material_coverage", {}) if isinstance(qa, dict) else {}
    max_cov = 0.0
    if isinstance(material_cov, dict) and material_cov:
        max_cov = max(_safe_float(v) for v in material_cov.values())

    tile_count = len(manifest_rows)
    warnings_count = len(warnings) if isinstance(warnings, list) else 0

    seam_ok = seam_max_diff == 0
    height_ok = y_min >= expected_min_y and y_max <= expected_max_y
    tiles_ok = tile_count > 0
    speckle_band = "good" if speckle_rate <= max_good_speckle else ("warn" if speckle_rate <= max_warn_speckle else "poor")
    material_balance_ok = max_cov <= max_material_dominance

    # Weighted score (0..100), deterministic and explainable.
    score = 0
    if seam_ok:
        score += 35
    if height_ok:
        score += 30
    if tiles_ok:
        score += 10
    if speckle_band == "good":
        score += 10
    elif speckle_band == "warn":
        score += 5
    if material_balance_ok:
        score += 10
    score += max(0, 5 - min(5, warnings_count))

    if not seam_ok or not height_ok or not tiles_ok:
        verdict = "fail"
    elif score >= 90:
        verdict = "excellent"
    elif score >= 75:
        verdict = "good"
    elif score >= 60:
        verdict = "needs_review"
    else:
        verdict = "fail"

    notes: List[str] = []
    if not seam_ok:
        notes.append(f"Seam mismatch detected (max diff={seam_max_diff}).")
    if not height_ok:
        notes.append(f"Height out of bounds: [{y_min}, {y_max}] expected [{expected_min_y}, {expected_max_y}].")
    if not tiles_ok:
        notes.append("No tiles found in manifest.")
    if speckle_band == "poor":
        notes.append(f"High speckle rate ({speckle_rate:.4f}); cleanup likely insufficient.")
    elif speckle_band == "warn":
        notes.append(f"Moderate speckle rate ({speckle_rate:.4f}); consider stricter cleanup.")
    if not material_balance_ok:
        notes.append(f"One material dominates output (max coverage={max_cov:.4f}); palette may be too narrow.")
    if warnings_count > 0:
        notes.append(f"{warnings_count} pipeline warning(s) present.")
    if not notes:
        notes.append("All core quality gates passed with no actionable warnings.")

    narrative = (
        f"Importer_MCP review verdict: {verdict.upper()} (score {score}/100). "
        f"Seam diff={seam_max_diff}, height=[{y_min},{y_max}], tiles={tile_count}, "
        f"speckle={speckle_rate:.4f}, warnings={warnings_count}."
    )

    return {
        "verdict": verdict,
        "score": int(score),
        "checks": {
            "seam_ok": seam_ok,
            "height_ok": height_ok,
            "tiles_ok": tiles_ok,
            "speckle_band": speckle_band,
            "material_balance_ok": material_balance_ok,
        },
        "metrics": {
            "seam_max_diff": seam_max_diff,
            "height_min": y_min,
            "height_max": y_max,
            "tile_count": tile_count,
            "speckle_rate": speckle_rate,
            "max_material_coverage": max_cov,
            "warnings_count": warnings_count,
        },
        "narrative": narrative,
        "notes": notes,
    }


def _write_markdown_report(path: Path, report: Dict[str, object]) -> None:
    lines = [
        "# Importer_MCP Review",
        "",
        str(report.get("narrative", "")),
        "",
        "## Verdict",
        f"- `{report.get('verdict', 'unknown')}`",
        f"- Score: `{report.get('score', 0)}/100`",
        "",
        "## Metrics",
    ]
    metrics = report.get("metrics", {})
    if isinstance(metrics, dict):
        for k in sorted(metrics):
            lines.append(f"- `{k}`: `{metrics[k]}`")

    lines += ["", "## Notes"]
    notes = report.get("notes", [])
    if isinstance(notes, list) and notes:
        for n in notes:
            lines.append(f"- {n}")
    else:
        lines.append("- No notes.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_wsl() -> bool:
    if os.name != "posix":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    return "microsoft" in platform.release().lower()


def _is_air_like(block_key: str) -> bool:
    k = str(block_key).strip().lower()
    return k == "air" or k.endswith(":air")


def _collect_indexable_files(tiles_dir: Path) -> List[Path]:
    # Keep the bridge deterministic and safe: index only supported object formats.
    allowed_suffixes = (".bo2", ".schem", ".schematic", ".nbt", ".prefab")
    out: List[Path] = []
    for p in sorted(tiles_dir.rglob("*")):
        if not p.is_file():
            continue
        name = p.name.lower()
        if name.endswith(".meta.json"):
            continue
        if name.endswith(".json"):
            # HyImporter tile metadata is not an ingestible voxel object.
            continue
        if name.endswith(allowed_suffixes):
            out.append(p)
    return out


def _stage_index_files(tiles_dir: Path, stage_dir: Path) -> int:
    if stage_dir.exists():
        shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in _collect_indexable_files(tiles_dir):
        rel = src.relative_to(tiles_dir)
        dst = stage_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    return count


def _wsl_to_windows_path(path: Path) -> str:
    proc = subprocess.run(
        ["wslpath", "-w", str(path)],
        text=True,
        capture_output=True,
        check=True,
    )
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError(f"wslpath returned empty output for {path}")
    return out


def _run_command(cmd: List[str]) -> Dict[str, object]:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True)
        payload: Dict[str, object] = {
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        if proc.returncode != 0:
            payload["ok"] = False
            return payload
        payload["ok"] = True
        return payload
    except Exception as e:
        return {"ok": False, "error": str(e), "command": cmd}


def _run_index_windows_fallback(
    *,
    voxelviewer_root: Path,
    scan_root: Path,
    out_db: Path,
    thumbs: Path,
    cache: Path,
    reports: Path,
    workers: int,
) -> Dict[str, object]:
    ps = shutil.which("powershell.exe")
    if not ps:
        return {"ok": False, "error": "powershell.exe not found for WSL Windows bridge fallback."}

    vv_win = _wsl_to_windows_path(voxelviewer_root)
    scan_win = _wsl_to_windows_path(scan_root)
    out_db_win = _wsl_to_windows_path(out_db)
    thumbs_win = _wsl_to_windows_path(thumbs)
    cache_win = _wsl_to_windows_path(cache)
    reports_win = _wsl_to_windows_path(reports)

    def _psq(s: str) -> str:
        return "'" + s.replace("'", "''") + "'"

    command_str = (
        "corepack pnpm "
        f"--dir {_psq(vv_win)} "
        "indexer scan "
        f"{_psq(scan_win)} "
        f"--out {_psq(out_db_win)} "
        f"--thumbs {_psq(thumbs_win)} "
        f"--cache {_psq(cache_win)} "
        f"--reports {_psq(reports_win)} "
        f"--workers {int(max(1, workers))} "
        "--mode strict+salvage"
    )
    return _run_command([ps, "-NoProfile", "-Command", command_str])


def _run_index_native(
    *,
    voxelviewer_root: Path,
    scan_root: Path,
    out_db: Path,
    thumbs: Path,
    cache: Path,
    reports: Path,
    workers: int,
) -> Dict[str, object]:
    corepack_bin = shutil.which("corepack") or shutil.which("corepack.cmd")
    pnpm_bin = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if corepack_bin and not Path(corepack_bin).exists():
        corepack_bin = None
    if pnpm_bin and not Path(pnpm_bin).exists():
        pnpm_bin = None
    if corepack_bin:
        cmd = [
            corepack_bin,
            "pnpm",
            "--dir",
            str(voxelviewer_root),
            "indexer",
            "scan",
            str(scan_root),
            "--out",
            str(out_db),
            "--thumbs",
            str(thumbs),
            "--cache",
            str(cache),
            "--reports",
            str(reports),
            "--workers",
            str(int(max(1, workers))),
            "--mode",
            "strict+salvage",
        ]
        return _run_command(cmd)
    if pnpm_bin:
        cmd = [
            pnpm_bin,
            "--dir",
            str(voxelviewer_root),
            "indexer",
            "scan",
            str(scan_root),
            "--out",
            str(out_db),
            "--thumbs",
            str(thumbs),
            "--cache",
            str(cache),
            "--reports",
            str(reports),
            "--workers",
            str(int(max(1, workers))),
            "--mode",
            "strict+salvage",
        ]
        return _run_command(cmd)
    return {"ok": False, "error": "Neither corepack nor pnpm was found on PATH."}


def _index_with_voxelviewer(map_out_dir: Path, voxelviewer_root: Path) -> Dict[str, object]:
    tiles_dir = map_out_dir / "tiles"
    if not tiles_dir.exists():
        return {"ok": False, "error": f"Tiles directory missing: {tiles_dir}"}

    out_db = voxelviewer_root / "data" / "objects.sqlite"
    thumbs = voxelviewer_root / "data" / "thumbs"
    cache = voxelviewer_root / "data" / "cache"
    reports = voxelviewer_root / "data" / "reports"
    stage_dir = voxelviewer_root / "data" / "hyimporter_stage"

    staged = _stage_index_files(tiles_dir=tiles_dir, stage_dir=stage_dir)
    if staged <= 0:
        return {
            "ok": False,
            "error": f"No indexable files found under {tiles_dir}.",
            "indexed_extensions": [".bo2", ".schem", ".schematic", ".nbt", ".prefab"],
        }
    workers = 1  # Keep indexer load predictable for large tile sets.

    # On WSL, prefer Windows PowerShell fallback because Windows Node/corepack is most common.
    if _is_wsl():
        fallback = _run_index_windows_fallback(
            voxelviewer_root=voxelviewer_root,
            scan_root=stage_dir,
            out_db=out_db,
            thumbs=thumbs,
            cache=cache,
            reports=reports,
            workers=workers,
        )
        if bool(fallback.get("ok")):
            result = fallback
        else:
            native = _run_index_native(
                voxelviewer_root=voxelviewer_root,
                scan_root=stage_dir,
                out_db=out_db,
                thumbs=thumbs,
                cache=cache,
                reports=reports,
                workers=workers,
            )
            result = {"native": native, "windows_fallback": fallback, **native}
    else:
        result = _run_index_native(
            voxelviewer_root=voxelviewer_root,
            scan_root=stage_dir,
            out_db=out_db,
            thumbs=thumbs,
            cache=cache,
            reports=reports,
            workers=workers,
        )

    if not bool(result.get("ok")):
        result["staged_file_count"] = staged
        result["stage_dir"] = str(stage_dir)
        return result

    return {
        "ok": True,
        "db": str(out_db),
        "thumbs": str(thumbs),
        "reports": str(reports),
        "staged_file_count": staged,
        "stage_dir": str(stage_dir),
        "command": result.get("command"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
    }


def run_importer_mcp_review(
    map_out_dir: Path,
    *,
    fail_on: str = "none",
    index_with_voxelviewer: bool = False,
    voxelviewer_root: Optional[Path] = None,
) -> Dict[str, object]:
    summary_path = map_out_dir / "qa" / "summary.json"
    manifest_path = map_out_dir / "runbook" / "tile_manifest.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing summary.json: {summary_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing tile_manifest.csv: {manifest_path}")

    summary = _read_json(summary_path)
    manifest_rows = _read_manifest_rows(manifest_path)
    report = evaluate_results(summary, manifest_rows)

    if index_with_voxelviewer:
        vv_root = voxelviewer_root or (map_out_dir.parents[1] / "voxelviewer")
        report["voxelviewer_index"] = _index_with_voxelviewer(map_out_dir, vv_root)

    qa_dir = map_out_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    json_path = qa_dir / "importer_mcp_review.json"
    md_path = qa_dir / "importer_mcp_review.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown_report(md_path, report)

    verdict = str(report.get("verdict", "needs_review"))
    if fail_on == "needs_review" and verdict in {"needs_review", "fail"}:
        raise RuntimeError(f"Importer_MCP quality gate triggered: verdict={verdict}")
    if fail_on == "fail" and verdict == "fail":
        raise RuntimeError(f"Importer_MCP quality gate triggered: verdict={verdict}")

    return report


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Importer_MCP result reviewer and VoxelViewer bridge")
    p.add_argument("--output-dir", required=True, help="Map output directory (contains qa/ and runbook/)")
    p.add_argument(
        "--fail-on",
        choices=["none", "needs_review", "fail"],
        default="none",
        help="Fail command based on verdict severity.",
    )
    p.add_argument(
        "--index-with-voxelviewer",
        action="store_true",
        help="Run VoxelViewer indexer on generated tiles after review.",
    )
    p.add_argument(
        "--voxelviewer-root",
        default=None,
        help="Path to voxelviewer workspace root (default: <repo>/voxelviewer).",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    voxel_root = Path(args.voxelviewer_root).resolve() if args.voxelviewer_root else None
    report = run_importer_mcp_review(
        Path(args.output_dir).resolve(),
        fail_on=args.fail_on,
        index_with_voxelviewer=bool(args.index_with_voxelviewer),
        voxelviewer_root=voxel_root,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
