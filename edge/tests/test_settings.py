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
        self.assertEqual(settings.room_name, "ロボット展示室")
        self.assertEqual(settings.interval_seconds, 10)


if __name__ == "__main__":
    unittest.main()

