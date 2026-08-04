from __future__ import annotations

import argparse
import configparser
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import grp
from io import StringIO
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile


HOSTNAME_PREFIX = "nnct-oc-rp"
SERVICE_NAME = "crowded-edge.service"


@dataclass(frozen=True)
class Assignment:
    device_id: int
    location_id: int
    room_name: str
    zone_name: str = ""

    def validate(self) -> None:
        if not 1 <= self.device_id <= 24:
            raise ValueError("device_id must be between 1 and 24")
        if not 1 <= self.location_id <= 12:
            raise ValueError("location_id must be between 1 and 12")
        if (
            not self.room_name
            or len(self.room_name) > 100
            or "\n" in self.room_name
            or "\r" in self.room_name
        ):
            raise ValueError("room_name must contain 1 to 100 characters")
        if (
            len(self.zone_name) > 100
            or "\n" in self.zone_name
            or "\r" in self.zone_name
        ):
            raise ValueError("zone_name must contain at most 100 characters")


def device_hostname(device_id: int, prefix: str = HOSTNAME_PREFIX) -> str:
    if not 1 <= device_id <= 24:
        raise ValueError("device_id must be between 1 and 24")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", prefix):
        raise ValueError("hostname prefix contains invalid characters")
    hostname = f"{prefix}-{device_id:02d}"
    if len(hostname) > 63:
        raise ValueError("generated hostname is longer than 63 characters")
    return hostname


def load_assignment(inventory_path: Path, device_id: int) -> Assignment:
    with inventory_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"device_id", "location_id", "room_name", "zone_name"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(
                "inventory must contain device_id, location_id, room_name, "
                "and zone_name columns"
            )
        matches = [
            row
            for row in reader
            if row.get("device_id", "").strip() == str(device_id)
        ]
    if not matches:
        raise ValueError(f"device_id {device_id} was not found in inventory")
    if len(matches) > 1:
        raise ValueError(f"device_id {device_id} is duplicated in inventory")
    row = matches[0]
    assignment = Assignment(
        device_id=device_id,
        location_id=int(row["location_id"]),
        room_name=row["room_name"].strip(),
        zone_name=row["zone_name"].strip(),
    )
    assignment.validate()
    return assignment


def render_device_config(existing: str, assignment: Assignment) -> str:
    assignment.validate()
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(existing)
    for required_section in ("backend", "camera"):
        if not parser.has_section(required_section):
            raise ValueError(
                f"existing device configuration is missing [{required_section}]"
            )
    if not parser.has_section("device"):
        parser.add_section("device")
    parser.set("device", "id", str(assignment.device_id))
    parser.set("device", "location_id", str(assignment.location_id))
    parser.set("device", "room_name", assignment.room_name)
    parser.set("device", "zone_name", assignment.zone_name)
    output = StringIO()
    parser.write(output)
    return output.getvalue()


def update_hosts_content(existing: str, hostname: str) -> str:
    output: list[str] = []
    replaced = False
    for line in existing.splitlines():
        content = line.split("#", 1)[0].split()
        if content and content[0] == "127.0.1.1":
            output.append(f"127.0.1.1\t{hostname}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        if output and output[-1]:
            output.append("")
        output.append(f"127.0.1.1\t{hostname}")
    return "\n".join(output) + "\n"


def render_systemd_unit(
    user: str,
    group: str,
    repository: Path,
    config_path: Path,
) -> str:
    edge_root = repository / "edge"
    executable = edge_root / ".venv/bin/crowded-edge"
    return f"""[Unit]
Description=CrowdedDetector Raspberry Pi edge client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
SupplementaryGroups=video
WorkingDirectory={edge_root}
ExecStart={executable} --config {config_path}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""


def _atomic_write(
    path: Path,
    content: str,
    mode: int,
    uid: int,
    gid: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, mode)
        os.chown(temporary_name, uid, gid)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _backup(path: Path, stamp: str, secret: bool = False) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.before-provision-{stamp}")
    shutil.copy2(path, backup)
    if secret:
        backup.chmod(0o600)
    return backup


def _run(*command: str) -> None:
    subprocess.run(command, check=True)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision one cloned CrowdedDetector Raspberry Pi."
    )
    parser.add_argument("--device-id", type=int, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--location-id", type=int)
    parser.add_argument("--room-name")
    parser.add_argument("--zone-name", default="")
    parser.add_argument("--hostname-prefix", default=HOSTNAME_PREFIX)
    parser.add_argument("--user", default="nnct-pi")
    parser.add_argument("--repository", type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/crowded-detector/device.ini"),
    )
    parser.add_argument(
        "--unit",
        type=Path,
        default=Path("/etc/systemd/system/crowded-edge.service"),
    )
    parser.add_argument(
        "--hosts-file",
        type=Path,
        default=Path("/etc/hosts"),
    )
    parser.add_argument(
        "--hostname-file",
        type=Path,
        default=Path("/etc/hostname"),
    )
    parser.add_argument(
        "--enable-service",
        action="store_true",
        help="enable and start crowded-edge after provisioning",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _assignment_from_args(args: argparse.Namespace) -> Assignment:
    if args.inventory is not None:
        if args.location_id is not None or args.room_name is not None or args.zone_name:
            raise ValueError(
                "--inventory cannot be combined with location, room, or zone options"
            )
        return load_assignment(args.inventory, args.device_id)
    location_id = args.location_id
    if location_id is None:
        if args.device_id > 12:
            raise ValueError("--location-id is required when device_id exceeds 12")
        location_id = args.device_id
    if args.room_name is None:
        raise ValueError("--room-name is required without --inventory")
    assignment = Assignment(
        device_id=args.device_id,
        location_id=location_id,
        room_name=args.room_name.strip(),
        zone_name=args.zone_name.strip(),
    )
    assignment.validate()
    return assignment


def main() -> int:
    args = _arguments()
    try:
        assignment = _assignment_from_args(args)
        hostname = device_hostname(assignment.device_id, args.hostname_prefix)
        account = pwd.getpwnam(args.user)
        primary_group = grp.getgrgid(account.pw_gid).gr_name
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    repository = (
        args.repository
        if args.repository is not None
        else Path(account.pw_dir) / "CrowdedDetector"
    ).resolve()
    executable = repository / "edge/.venv/bin/crowded-edge"
    if not repository.is_dir():
        raise SystemExit(f"ERROR: repository does not exist: {repository}")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise SystemExit(f"ERROR: edge executable is missing: {executable}")
    if not args.config.is_file():
        raise SystemExit(f"ERROR: existing configuration is missing: {args.config}")
    if not args.hosts_file.is_file():
        raise SystemExit(f"ERROR: hosts file is missing: {args.hosts_file}")
    if not args.hostname_file.is_file():
        raise SystemExit(
            f"ERROR: hostname file is missing: {args.hostname_file}"
        )
    if shutil.which("systemctl") is None or shutil.which("hostnamectl") is None:
        raise SystemExit("ERROR: systemctl and hostnamectl are required")
    if shutil.which("avahi-daemon") is None and not Path(
        "/usr/sbin/avahi-daemon"
    ).is_file():
        raise SystemExit("ERROR: avahi-daemon is not installed")

    supplementary_groups = {
        group.gr_name for group in grp.getgrall() if args.user in group.gr_mem
    }
    if "video" not in supplementary_groups and primary_group != "video":
        raise SystemExit(f"ERROR: {args.user} is not a member of the video group")

    config_content = render_device_config(
        args.config.read_text(encoding="utf-8"),
        assignment,
    )
    hosts_content = update_hosts_content(
        args.hosts_file.read_text(encoding="utf-8"),
        hostname,
    )
    unit_content = render_systemd_unit(
        args.user,
        primary_group,
        repository,
        args.config.resolve(),
    )

    print("Device ID:", assignment.device_id)
    print("Location ID:", assignment.location_id)
    print("Room name:", assignment.room_name)
    print("Zone name:", assignment.zone_name or "(empty)")
    print("Hostname:", hostname)
    print("User:", args.user)
    print("Repository:", repository)
    print("Enable service:", args.enable_service)
    if args.dry_run:
        print("Dry run: no files or services were changed")
        return 0
    if os.geteuid() != 0:
        raise SystemExit("ERROR: run this command with sudo")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _run("systemctl", "disable", "--now", SERVICE_NAME)
    _backup(args.config, stamp, secret=True)
    _backup(args.hosts_file, stamp)
    _backup(args.hostname_file, stamp)
    _backup(args.unit, stamp)

    _atomic_write(args.config, config_content, 0o640, 0, account.pw_gid)
    _atomic_write(args.hosts_file, hosts_content, 0o644, 0, 0)
    _atomic_write(args.unit, unit_content, 0o644, 0, 0)
    _run("hostnamectl", "set-hostname", hostname)
    _run("systemctl", "daemon-reload")
    _run("systemctl", "enable", "--now", "avahi-daemon.service")
    if args.enable_service:
        _run("systemctl", "enable", "--now", SERVICE_NAME)
    else:
        _run("systemctl", "disable", "--now", SERVICE_NAME)

    print("Provisioning complete")
    print("Reboot the Raspberry Pi before final verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
