# Contributing

## Setup
- Python 3.9+
- Install deps:
  - `pip install pillow rembg`

## Run
- `python main.py`
- Safe mode: `python main.py --safe-mode`

## Checks
- `python scripts/run_checks.py`

## Style
- Keep shared values centralized in `goblintools/common/`.
- Prefer metadata-driven launcher changes via `goblintools.master_metadata.json`.
- Keep tool status accurate (`stable`, `experimental`, `legacy`) in metadata.

## Pull Requests
- Keep PRs focused and small.
- Include a short test plan and before/after behavior notes.
