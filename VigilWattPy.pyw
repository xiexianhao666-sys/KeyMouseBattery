"""VigilWatt Python（非官方）入口。"""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from vigilwatt_py.cli import main  # noqa: E402

raise SystemExit(main(sys.argv))
