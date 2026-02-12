# HyImporter Multi-Platform Setup

HyImporter runtime supports Windows, WSL/Linux, and macOS.

## 1) Choose input/output roots
Set these explicitly in `config.yaml`:

- `paths.input_root`
- `paths.output_root`

Recommended conventions:
- Windows: `C:/hyimporter/input`, `C:/hyimporter/out`
- WSL: `/mnt/c/hyimporter/input`, `/mnt/c/hyimporter/out`
- macOS/Linux: `/Users/<you>/hyimporter/input`, `/Users/<you>/hyimporter/out`

## 2) Environment setup

### Windows
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

### WSL/Linux/macOS
```bash
bash scripts/setup_unix.sh
```

WSL-specific system dependency bootstrap:
```bash
bash scripts/wsl_setup.sh
```

## 3) Build

### Windows
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_world.ps1 -Config config.yaml
```

### WSL/Linux/macOS
```bash
bash scripts/build_world.sh config.yaml
```

## 4) Validate
Quick deterministic smoke check:
```bash
bash scripts/self_test.sh quick
```

Windows equivalent:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 5) Environment variable overrides (optional)
- `HYIMPORTER_BASE_DIR`
- `HYIMPORTER_INPUT_ROOT`
- `HYIMPORTER_OUTPUT_ROOT`

Direct path vars override base dir behavior.
