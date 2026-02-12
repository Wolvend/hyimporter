from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class ProjectConfig:
    map_name: str = "example_zone"


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    release = platform.release().lower()
    version = platform.version().lower()
    return "microsoft" in release or "microsoft" in version


def _default_base_dir() -> Path:
    base_override = os.environ.get("HYIMPORTER_BASE_DIR")
    if base_override:
        return Path(base_override).expanduser()
    if _is_windows():
        return Path("C:/hyimporter")
    if _is_wsl() and Path("/mnt/c").exists():
        return Path("/mnt/c/hyimporter")
    return Path.home() / "hyimporter"


def _default_input_root() -> str:
    direct = os.environ.get("HYIMPORTER_INPUT_ROOT")
    if direct:
        return str(Path(direct).expanduser())
    return str(_default_base_dir() / "input")


def _default_output_root() -> str:
    direct = os.environ.get("HYIMPORTER_OUTPUT_ROOT")
    if direct:
        return str(Path(direct).expanduser())
    return str(_default_base_dir() / "out")


@dataclass
class PathsConfig:
    input_root: str = field(default_factory=_default_input_root)
    output_root: str = field(default_factory=_default_output_root)


@dataclass
class InputConfig:
    allow_8bit_height: bool = False


@dataclass
class HeightConfig:
    total_height: int = 320
    margin_bottom: int = 12
    margin_top: int = 24
    percentile_low: float = 1.0
    percentile_high: float = 99.0
    gamma: float = 0.85
    sea_level_y: int = 96
    bottom_y: int = 0


@dataclass
class HydrologyConfig:
    enabled: bool = True
    fill_sinks: bool = True
    river_threshold_percentile: float = 99.2
    carve_depth: int = 2
    river_mask_name: str = "river"


@dataclass
class NoiseConfig:
    enabled: bool = True
    macro_amplitude: float = 6.0
    macro_wavelength: float = 256.0
    micro_amplitude: float = 2.0
    micro_wavelength: float = 32.0
    seed: int = 1337
    suppress_near_water_radius: int = 5
    road_mask_name: str = "road"


@dataclass
class PaletteMatchConfig:
    enabled: bool = False
    dither: bool = False


@dataclass
class MaterialsConfig:
    enabled: bool = True
    default_layer: str = "grass"
    layers: List[str] = field(
        default_factory=lambda: ["grass", "dirt", "rock", "sand", "snow", "mud", "gravel"]
    )
    snowline_y: int = 220
    beach_band_dy: int = 6
    cliff_slope_high: float = 2.2
    cliff_slope_low: float = 1.6
    majority_radius: int = 1
    island_min_area: int = 32
    palette_match: PaletteMatchConfig = field(default_factory=PaletteMatchConfig)


@dataclass
class ResampleConfig:
    target_resolution: Optional[int] = None


@dataclass
class TilingConfig:
    tile_size: int = 512
    overlap: int = 16


@dataclass
class OutputsConfig:
    export_obj: bool = True
    export_schematic: bool = True
    export_bo2: bool = False
    schematic_full_volume: bool = False
    bo2_include_subsurface: bool = False
    minecraft_block_ids: Dict[str, int] = field(
        default_factory=lambda: {
            "grass": 2,
            "dirt": 3,
            "rock": 1,
            "sand": 12,
            "snow": 80,
            "mud": 3,
            "gravel": 13,
            "default": 1,
        }
    )


@dataclass
class RuntimeConfig:
    async_tile_export: bool = True
    tile_workers: int = 0  # 0 => auto


@dataclass
class StabilizeBBoxConfig:
    enabled: bool = True
    bbox_min: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bbox_max: Tuple[float, float, float] = (512.0, 320.0, 512.0)


@dataclass
class MeshConfig:
    export_base: bool = True
    export_shells: bool = True
    shell_thickness: int = 1
    triangulate: bool = True
    stabilize_bbox: StabilizeBBoxConfig = field(default_factory=StabilizeBBoxConfig)


@dataclass
class QAConfig:
    assert_height_range: Tuple[int, int] = (0, 319)
    assert_max_seam_diff: int = 0
    write_plots: bool = True


@dataclass
class SafetyConfig:
    max_vertices_per_tile: int = 1_500_000
    max_obj_bytes_per_tile: int = 100 * 1024 * 1024
    warn_max_tiles: int = 256


@dataclass
class HytaleConfig:
    default_import_height: int = 320
    base_fill_item_id: str = "hytale:stone"
    material_item_ids: Dict[str, str] = field(
        default_factory=lambda: {
            "grass": "hytale:grass",
            "dirt": "hytale:dirt",
            "rock": "hytale:stone",
            "sand": "hytale:sand",
            "snow": "hytale:snow",
            "mud": "hytale:mud",
            "gravel": "hytale:gravel",
        }
    )


@dataclass
class PipelineConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    input: InputConfig = field(default_factory=InputConfig)
    height: HeightConfig = field(default_factory=HeightConfig)
    hydrology: HydrologyConfig = field(default_factory=HydrologyConfig)
    noise: NoiseConfig = field(default_factory=NoiseConfig)
    materials: MaterialsConfig = field(default_factory=MaterialsConfig)
    resample: ResampleConfig = field(default_factory=ResampleConfig)
    tiling: TilingConfig = field(default_factory=TilingConfig)
    outputs: OutputsConfig = field(default_factory=OutputsConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    qa: QAConfig = field(default_factory=QAConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    hytale: HytaleConfig = field(default_factory=HytaleConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _merge_dict(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def _parse_pipeline_config(raw: Dict[str, Any]) -> PipelineConfig:
    defaults = PipelineConfig().to_dict()
    merged = _merge_dict(defaults, raw)

    return PipelineConfig(
        project=ProjectConfig(**merged["project"]),
        paths=PathsConfig(**merged["paths"]),
        input=InputConfig(**merged["input"]),
        height=HeightConfig(**merged["height"]),
        hydrology=HydrologyConfig(**merged["hydrology"]),
        noise=NoiseConfig(**merged["noise"]),
        materials=MaterialsConfig(
            **{
                **merged["materials"],
                "palette_match": PaletteMatchConfig(**merged["materials"]["palette_match"]),
            }
        ),
        resample=ResampleConfig(**merged["resample"]),
        tiling=TilingConfig(**merged["tiling"]),
        outputs=OutputsConfig(**merged["outputs"]),
        runtime=RuntimeConfig(**merged["runtime"]),
        mesh=MeshConfig(
            **{
                **merged["mesh"],
                "stabilize_bbox": StabilizeBBoxConfig(**merged["mesh"]["stabilize_bbox"]),
            }
        ),
        qa=QAConfig(**merged["qa"]),
        safety=SafetyConfig(**merged["safety"]),
        hytale=HytaleConfig(**merged["hytale"]),
    )


def load_config(path: str | Path) -> PipelineConfig:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    cfg = _parse_pipeline_config(raw)

    if cfg.height.total_height != 320:
        raise ValueError("total_height must remain 320 for this pipeline")

    if cfg.height.margin_bottom + cfg.height.margin_top >= cfg.height.total_height:
        raise ValueError("Invalid margins: no effective height remains")

    if not (0.0 <= cfg.height.percentile_low < cfg.height.percentile_high <= 100.0):
        raise ValueError("Invalid percentiles")

    if cfg.tiling.tile_size != 512:
        raise ValueError("tile_size must be 512 for deterministic safety constraints")

    if cfg.tiling.overlap <= 0:
        raise ValueError("tiling.overlap must be > 0")

    return cfg


def map_input_dir(cfg: PipelineConfig) -> Path:
    return Path(cfg.paths.input_root) / cfg.project.map_name


def map_output_dir(cfg: PipelineConfig) -> Path:
    return Path(cfg.paths.output_root) / cfg.project.map_name
