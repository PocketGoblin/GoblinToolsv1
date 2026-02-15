from __future__ import annotations

import argparse

from goblintools.common import set_safe_mode
from goblintools.launcher.app import launch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GoblinTools launcher')
    parser.add_argument('--safe-mode', action='store_true', help='Disable AI/network features and drag-drop integrations')
    args = parser.parse_args()
    set_safe_mode(bool(args.safe_mode))
    launch(safe_mode=bool(args.safe_mode))
