from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from crowded_edge.provision import (
    Assignment,
    device_hostname,
    load_assignment,
    render_device_config,
    render_systemd_unit,
    update_hosts_content,
)


class ProvisionTest(unittest.TestCase):
    def test_generates_two_digit_hostname(self) -> None:
        self.assertEqual(device_hostname(1), "nnct-oc-rp-01")
        self.assertEqual(device_hostname(24), "nnct-oc-rp-24")

    def test_reads_assignment_from_inventory(self) -> None:
        content = (
            "device_id,location_id,room_name,zone_name\n"
            "13,3,大体育館,左側\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "devices.csv"
            inventory.write_text(content, encoding="utf-8")
            assignment = load_assignment(inventory, 13)
        self.assertEqual(assignment.location_id, 3)
        self.assertEqual(assignment.room_name, "大体育館")
        self.assertEqual(assignment.zone_name, "左側")

    def test_updates_device_section_and_preserves_secret_sections(self) -> None:
        existing = """[device]
id = 6
room_name = テスト会場
[backend]
url = http://backend.test/api/v1/observations
token = secret-api-token
[camera]
device = 0
interval_seconds = 10
"""
        rendered = render_device_config(
            existing,
            Assignment(13, 3, "大体育館", "左側"),
        )
        self.assertIn("id = 13", rendered)
        self.assertIn("location_id = 3", rendered)
        self.assertIn("room_name = 大体育館", rendered)
        self.assertIn("zone_name = 左側", rendered)
        self.assertIn("token = secret-api-token", rendered)
        self.assertIn("interval_seconds = 10", rendered)

    def test_replaces_hosts_entry(self) -> None:
        existing = "127.0.0.1\tlocalhost\n127.0.1.1\told-host\n"
        rendered = update_hosts_content(existing, "nnct-oc-rp-06")
        self.assertIn("127.0.1.1\tnnct-oc-rp-06", rendered)
        self.assertNotIn("old-host", rendered)

    def test_systemd_unit_uses_selected_config_path(self) -> None:
        rendered = render_systemd_unit(
            "nnct-pi",
            "nnct-pi",
            Path("/home/nnct-pi/CrowdedDetector"),
            Path("/etc/crowded-detector/device.ini"),
        )
        self.assertIn("User=nnct-pi", rendered)
        self.assertIn("Group=nnct-pi", rendered)
        self.assertIn(
            "ExecStart=/home/nnct-pi/CrowdedDetector/edge/.venv/bin/"
            "crowded-edge --config /etc/crowded-detector/device.ini",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
