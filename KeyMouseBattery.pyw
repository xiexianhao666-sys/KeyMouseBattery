"""KeyMouseBattery 应用入口。"""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from keymousebattery.cli import main  # noqa: E402

raise SystemExit(main(sys.argv))
