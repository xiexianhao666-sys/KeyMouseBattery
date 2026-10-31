import unittest

from keymousebattery import protocol_mchose as proto


def build(payload: bytes) -> bytes:
    body = bytearray(20)
    body[: len(payload)] = payload
    body[19] = sum(body[:19]) & 0xFF
    return bytes(body)


class FrameTests(unittest.TestCase):
    def test_session_frame_matches_documented_bytes(self):
        self.assertEqual(proto.session_frame().hex(" ").upper(),
                         "13 05 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 19")

    def test_battery_frame_matches_documented_bytes(self):
        self.assertEqual(proto.battery_frame().hex(" ").upper(),
                         "13 4A 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 5E")

    def test_checksum_is_sum_of_first_nineteen(self):
        frame = proto.frame(0x4A, 0x01)
        self.assertEqual(frame[19], sum(frame[:19]) & 0xFF)


class ModelTests(unittest.TestCase):
    def test_g75_pro_password_maps_to_model(self):
        self.assertEqual(proto.model_from_password(bytes.fromhex("030000000115")), "G75 Pro")

    def test_unknown_password_returns_none(self):
        self.assertIsNone(proto.model_from_password(bytes.fromhex("030000000158")))

    def test_session_ack_reads_password_from_offset_five(self):
        ack = build(bytes([0x13, 0x05, 0x01, 0x00, 0x0A, 0x03, 0x00, 0x00, 0x00, 0x01, 0x15, 0x01]))
        self.assertEqual(proto.model_from_session_ack(ack), "G75 Pro")

    def test_session_ack_accepts_shifted_layout(self):
        ack = build(bytes([0x13, 0x05, 0x01, 0x00, 0x0A, 0x00, 0x03, 0x00, 0x00, 0x00, 0x01, 0x15]))
        self.assertEqual(proto.model_from_session_ack(ack), "G75 Pro")

    def test_session_ack_without_known_model_returns_none(self):
        ack = build(bytes([0x13, 0x05, 0x01, 0x00, 0x0A, 0x03, 0x00, 0x00, 0x00, 0x01, 0x58, 0x01]))
        self.assertIsNone(proto.model_from_session_ack(ack))


class BatteryParseTests(unittest.TestCase):
    def test_documented_sample_parses(self):
        raw = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x24, 0x01]))
        battery = proto.parse_battery(raw)
        self.assertIsNotNone(battery)
        self.assertEqual(battery.percent, 0x24)
        self.assertFalse(battery.charging)
        self.assertTrue(battery.valid)

    def test_charging_bit_is_reported(self):
        raw = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x63, 0x10]))
        battery = proto.parse_battery(raw)
        self.assertTrue(battery.charging)

    def test_unknown_state_byte_keeps_charging_unknown(self):
        raw = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x50, 0x02]))
        self.assertIsNone(proto.parse_battery(raw).charging)

    def test_zero_and_one_percent_are_flagged_invalid_but_kept_raw(self):
        for value in (0, 1):
            raw = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, value, 0x01]))
            battery = proto.parse_battery(raw)
            self.assertFalse(battery.valid)
            self.assertEqual(battery.raw_percent, value)

    def test_hundred_percent_is_valid(self):
        raw = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x64, 0x01]))
        self.assertTrue(proto.parse_battery(raw).valid)

    def test_101_is_not_valid(self):
        raw = build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x65, 0x01]))
        self.assertFalse(proto.parse_battery(raw).valid)

    def test_bad_checksum_is_rejected(self):
        raw = bytearray(build(bytes([0x13, 0x4A, 0x01, 0x00, 0x02, 0x24, 0x01])))
        raw[19] ^= 0xFF
        self.assertIsNone(proto.parse_battery(bytes(raw)))

    def test_short_frame_is_rejected(self):
        self.assertIsNone(proto.parse_battery(bytes([0x13, 0x4A, 0x01])))

    def test_other_command_is_rejected(self):
        raw = build(bytes([0x13, 0x05, 0x01]))
        self.assertIsNone(proto.parse_battery(raw))


class PushTests(unittest.TestCase):
    def test_battery_push_reads_type_then_percent(self):
        raw = build(bytes([0x13, 0x0A, 0x01, 0x00, 0x04, 0x05, 0x42, 0x01]))
        push = proto.parse_push(raw)
        self.assertEqual(push.kind, "battery")
        self.assertEqual(push.percent, 0x42)
        self.assertFalse(push.charging)

    def test_state_push_is_not_battery(self):
        raw = build(bytes([0x13, 0x0A, 0x01, 0x00, 0x04, 0x02, 0x01]))
        push = proto.parse_push(raw)
        self.assertEqual(push.kind, "state")
        self.assertIsNone(push.percent)

    def test_unknown_push_type_is_other(self):
        raw = build(bytes([0x13, 0x0A, 0x01, 0x00, 0x04, 0x07, 0x50]))
        self.assertEqual(proto.parse_push(raw).kind, "other")

    def test_push_with_bad_checksum_is_ignored(self):
        raw = bytearray(build(bytes([0x13, 0x0A, 0x01, 0x00, 0x04, 0x05, 0x42, 0x01])))
        raw[19] ^= 0xFF
        self.assertIsNone(proto.parse_push(bytes(raw)))

    def test_invalid_percent_in_push_is_none(self):
        raw = build(bytes([0x13, 0x0A, 0x01, 0x00, 0x04, 0x05, 0x00, 0x01]))
        self.assertIsNone(proto.parse_push(raw).percent)


if __name__ == "__main__":
    unittest.main()
