"""ADB command wrapper for device discovery and port forwarding."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass


@dataclass
class AdbDevice:
    serial: str
    state: str  # "device", "offline", "unauthorized"
    model: str = ""
    product: str = ""


class AdbClient:
    """Async wrapper around the ADB command-line tool."""

    def __init__(self, adb_path: str | None = None):
        self.adb_path = adb_path or shutil.which("adb") or "adb"

    async def _run(self, *args: str, serial: str | None = None) -> tuple[int, str, str]:
        cmd = [self.adb_path]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )

    async def devices(self) -> list[AdbDevice]:
        """List all connected devices."""
        code, stdout, _ = await self._run("devices", "-l")
        if code != 0:
            return []

        devices = []
        for line in stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                model = ""
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.split(":", 1)[1]
                devices.append(AdbDevice(serial=serial, state=state, model=model))
        return devices

    async def forward(self, serial: str, local_port: int, remote_port: int) -> bool:
        """Set up ADB port forwarding."""
        code, _, _ = await self._run(
            "forward", f"tcp:{local_port}", f"tcp:{remote_port}", serial=serial
        )
        return code == 0

    async def forward_remove(self, serial: str, local_port: int) -> bool:
        """Remove a port forwarding rule."""
        code, _, _ = await self._run(
            "forward", "--remove", f"tcp:{local_port}", serial=serial
        )
        return code == 0

    async def shell(self, serial: str, command: str) -> tuple[int, str]:
        """Execute a shell command on the device."""
        code, stdout, stderr = await self._run("shell", command, serial=serial)
        return code, stdout or stderr

    async def install(self, serial: str, apk_path: str, replace: bool = True) -> bool:
        """Install an APK on the device."""
        args = ["install"]
        if replace:
            args.append("-r")
        args.append(apk_path)
        code, _, _ = await self._run(*args, serial=serial)
        return code == 0

    async def push(self, serial: str, local: str, remote: str) -> bool:
        """Push a file to the device."""
        code, _, _ = await self._run("push", local, remote, serial=serial)
        return code == 0

    async def pull(self, serial: str, remote: str, local: str) -> bool:
        """Pull a file from the device."""
        code, _, _ = await self._run("pull", remote, local, serial=serial)
        return code == 0

    async def get_prop(self, serial: str, prop: str) -> str:
        """Get a device property."""
        _, stdout = await self.shell(serial, f"getprop {prop}")
        return stdout.strip()
