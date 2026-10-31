import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_TMP = ROOT / ".testtmp"


def temp_dir(prefix: str = "t") -> Path:
    TEST_TMP.mkdir(parents=True, exist_ok=True)
    folder = TEST_TMP / ("%s-%d" % (prefix, os.getpid()))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup(folder: Path) -> None:
    for child in sorted(folder.rglob("*"), reverse=True):
        try:
            child.unlink() if child.is_file() else child.rmdir()
        except OSError:
            pass
    try:
        folder.rmdir()
    except OSError:
        pass
