from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from crowded_edge.settings import DeviceSettings


class DeviceSettingsTest(unittest.TestCase):
    def test_reads_unicode_configuration(self) -> None:
        content = """[device]
id = 2
room_name = ロボット展示室
[backend]
url = https://example.test/api/v1/observations
token = secret
[camera]
device = 0
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device.ini"
            path.write_text(content, encoding="utf-8")
            settings = DeviceSettings.from_file(path)
        self.assertEqual(settings.device_id, 2)
        self.assertEqual(settings.location_id, 2)
        self.assertEqual(settings.room_name, "ロボット展示室")
        self.assertEqual(settings.zone_name, "")
        self.assertEqual(settings.interval_seconds, 10)

    def test_reads_multi_camera_assignment(self) -> None:
        content = """[device]
id = 13
location_id = 3
room_name = 大体育館
zone_name = 左側
[backend]
url = http://example.test/api/v1/observations
token = secret
[camera]
device = 0
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device.ini"
            path.write_text(content, encoding="utf-8")
            settings = DeviceSettings.from_file(path)
        self.assertEqual(settings.device_id, 13)
        self.assertEqual(settings.location_id, 3)
        self.assertEqual(settings.room_name, "大体育館")
        self.assertEqual(settings.zone_name, "左側")

    def test_rejects_ids_out_of_range(self) -> None:
        content = """[device]
id = 25
location_id = 13
room_name = 範囲外
[backend]
url = http://example.test/api/v1/observations
token = secret
[camera]
device = 0
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device.ini"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                DeviceSettings.from_file(path)


if __name__ == "__main__":
    unittest.main()
