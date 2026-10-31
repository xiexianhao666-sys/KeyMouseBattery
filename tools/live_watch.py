"""真实读取：按间隔轮询本机键盘，直到拿到足够的读数（用于验收取证）。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from keymousebattery import mchose_plugin  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="轮询键盘电量并记录")
    parser.add_argument("--seconds", type=float, default=180.0)
    parser.add_argument("--gap", type=float, default=2.0)
    parser.add_argument("--want", type=int, default=3)
    args = parser.parse_args(argv)

    sensor = mchose_plugin.KeyboardSensor()
    deadline = time.monotonic() + args.seconds
    readings = 0
    while time.monotonic() < deadline and readings < args.want:
        probe = sensor.probe()
        stamp = time.strftime("%H:%M:%S")
        if probe.sample.level is not None:
            readings += 1
            print("%s  model=%s level=%d charging=%s  ack=%s" % (
                stamp, probe.model, probe.sample.level,
                probe.sample.charging, (probe.session_ack or "")[:23]), flush=True)
        else:
            print("%s  no reading (%s)" % (stamp, probe.error or "无应答"), flush=True)
        if readings >= args.want:
            break
        time.sleep(args.gap)
    print("collected %d readings" % readings, flush=True)
    return 0 if readings else 1


if __name__ == "__main__":
    raise SystemExit(main())
