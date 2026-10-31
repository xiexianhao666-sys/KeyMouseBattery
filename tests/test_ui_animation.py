"""电量动效 A（轻快收尾）的定向测试。

不依赖真实设备与桌面：直接喂 Device 给卡片，检查动画的起止值、取消、
同值不重播、旧读数不播，以及"减少动画"时直接落到目标。
"""

from __future__ import annotations

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QVariantAnimation  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keymousebattery import ui  # noqa: E402
from keymousebattery.model import Device, Sample  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _device(level, online=True, stale=False):
    return Device(key="mouse:1", name="鼠标", kind="mouse", connection="ble",
                  source="test",
                  sample=Sample(level=level, charging=None, online=online,
                                sampled_at=time.time()),
                  stale=stale)


class AnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def setUp(self) -> None:
        self._motion = ui.animations_enabled
        ui.animations_enabled = lambda: True
        self.card = ui.DeviceCard()
        self.card.resize(600, 110)
        self.card.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        ui.animations_enabled = self._motion
        self.card.close()

    def test_first_read_animates_from_zero(self):
        self.card.update_view(_device(76), 20)
        self.assertEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._anim.startValue(), 0.0)
        self.assertAlmostEqual(self.card._anim.endValue(), 76.0)
        self.assertEqual(self.card._anim.duration(), 650)
        self.card._anim.setCurrentTime(649)
        self.assertGreater(self.card._shown, 70)
        self.assertLessEqual(self.card._shown, 76)
        self.card.finish_animation()

    def test_same_value_does_not_restart(self):
        self.card.update_view(_device(76), 20)
        self.card.finish_animation()
        self.app.processEvents()
        self.card.update_view(_device(76), 20)
        self.assertNotEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._shown, 76.0)

    def test_new_value_continues_from_displayed(self):
        self.card.update_view(_device(76), 20)
        self.card._anim.setCurrentTime(300)
        shown = self.card._shown
        self.card.update_view(_device(18), 20)
        self.assertEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._anim.startValue(), shown)
        self.assertAlmostEqual(self.card._anim.endValue(), 18.0)
        self.card.finish_animation()
        self.assertAlmostEqual(self.card._shown, 18.0)

    def test_unknown_shows_dash_without_animation(self):
        self.card.update_view(_device(None), 20)
        self.assertNotEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertEqual(self.card.level.text(), "—")
        self.assertIsNone(self.card._shown)

    def test_stale_value_is_hidden_instead_of_shown(self):
        # T004：断开/失去证据的卡不再展示上次读数，整张卡显示"未连接"。
        sample = Sample(level=64, charging=None, online=False, sampled_at=time.time())
        device = Device(key="ble:aa", name="键盘", kind="keyboard", connection="ble",
                        source="windows-ble", sample=sample, stale=True)
        self.card.update_view(device, 20, time.time())
        self.assertIn("未连接", self.card.state.text())
        self.assertEqual(self.card.level.text(), "未连接")
        self.assertFalse(self.card.bar_slot.isVisible())

    def test_offline_card_does_not_paint_battery_track(self):
        # 0.4.2：bar_slot.hide() 之后 geometry 仍在，paintEvent 必须自己跳过，
        # 否则离线卡底部会残留一条灰色电量条。
        self.card.update_view(_device(76), 20)
        self.card.finish_animation()
        self.assertTrue(self.card._bar_visible())
        self.card.update_view(_device(76, online=False), 20, time.time())
        self.assertFalse(self.card.bar_slot.isVisible())
        self.assertFalse(self.card._bar_visible())
        # 重新上线后恢复
        self.card.update_view(_device(52), 20)
        self.assertTrue(self.card._bar_visible())

    def test_reduced_motion_jumps_to_target(self):
        ui.animations_enabled = lambda: False
        self.card.update_view(_device(18), 20)
        self.assertNotEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._shown, 18.0)
        self.assertEqual(self.card.level.text(), "18%")

    def test_zero_is_a_value_not_unknown(self):
        self.card.update_view(_device(0), 20)
        self.card.finish_animation()
        self.assertEqual(self.card.level.text(), "0%")
        self.assertAlmostEqual(self.card._shown, 0.0)

    def test_hidden_card_does_not_animate(self):
        self.card.hide()
        self.card.update_view(_device(76), 20)
        self.assertNotEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._shown, 76.0)

    def test_offline_without_reading_keeps_entrance_animation(self):
        # 先来一轮"离线且无读数"的占位，不能把首次入场动效消耗掉
        self.card.update_view(_device(None, online=False), 20)
        self.assertNotEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertIsNone(self.card._shown)
        self.assertFalse(self.card._entered)
        # 第一条真实读数仍应从 0 涨上来
        self.card.update_view(_device(76), 20)
        self.assertEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._anim.startValue(), 0.0)
        self.assertAlmostEqual(self.card._anim.endValue(), 76.0)
        self.card.finish_animation()

    def test_same_target_mid_animation_keeps_timeline(self):
        self.card.update_view(_device(76), 20)
        self.card._anim.setCurrentTime(300)
        shown = self.card._shown
        self.assertGreater(shown, 0.0)
        self.card.update_view(_device(76), 20)  # 同一目标又刷新一轮
        self.assertEqual(self.card._anim.state(), QVariantAnimation.Running)
        self.assertAlmostEqual(self.card._anim.startValue(), 0.0)  # 没有从当前值重新计时
        self.assertGreaterEqual(self.card._shown, shown - 0.5)
        self.card._anim.setCurrentTime(649)
        self.assertGreater(self.card._shown, 70)
        self.card.finish_animation()
        self.assertAlmostEqual(self.card._shown, 76.0)


class MotionSwitchTests(unittest.TestCase):
    def test_system_switch_returns_bool(self):
        self.assertIsInstance(ui.animations_enabled(), bool)


if __name__ == "__main__":
    unittest.main()
