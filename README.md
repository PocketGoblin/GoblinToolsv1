# GoblinTools

Desktop utility suite for asset and file workflows, with a shared launcher and focused single-purpose Goblin apps.

Dev by **PocketGoblin**.

[![Version](https://img.shields.io/badge/version-v1.0.0-00E5FF)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-3CFFB3)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-101A2E)](#requirements)

## Highlights
- One launcher, multiple focused tools.
- Fast local workflows (sort/rename/archive/image pipelines).
- Metadata-driven tool registry for easier v2 porting.
- Safe mode support for reduced integrations.

## Tool Stack (v1.0.0)
| Tool | Status | What It Does |
| --- | --- | --- |
| Palette Goblin | Stable | Extract color palettes from images. |
| Slicer Goblin | Stable | Slice spritesheets, remove backgrounds, export outputs. |
| Zip Goblin | Stable | Inspect/extract archives and create zip/7z bundles. |
| Sort Goblin | Stable | Sort + rename file sets with preview/undo. |
| Error Goblin | Experimental | Parse and explain engine/runtime errors. |

## Repository Layout
- `main.py`: launcher entrypoint
- `goblintools/launcher/`: launcher UI
- `goblintools/palette_goblin/`: palette extraction app
- `goblintools/slicer_goblin/`: spritesheet slicing app
- `goblintools/tools/`: zip, sort, rename, and error windows
- `goblintools/common/`: shared UI/runtime infrastructure
- `core/`: tool logic engines
- `goblintools.master_metadata.json`: suite/tool metadata source

## Requirements
- Python `3.9+`
- `Pillow`
- `rembg` (used by Slicer Goblin background removal)

Install:
```bash
pip install pillow rembg
```

## Run
```bash
python main.py
```

Safe mode:
```bash
python main.py --safe-mode
```

## Checks
```bash
python scripts/run_checks.py
```

## Screenshots
Coming soon.

## Roadmap
- v1: Tkinter suite hardening and UX consistency.
- v2: Port to PySide6 with parity-first architecture.
