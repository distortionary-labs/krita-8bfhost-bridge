"""Finding the 8bf-host program and running it.

The plug-in does not load filters itself. Every filter runs in 8bf-host
(https://github.com/distortionary-labs/8bf-host), which the user installs
separately. This module builds its command lines and runs them; nothing
here imports Qt, so the caller passes callbacks to keep the UI alive.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import List

DOWNLOAD_URL = "https://github.com/distortionary-labs/8bf-host/releases"
PROGRAM = "8bf-host"

# 8bf-host's exit codes (see `8bf-host --help`).
EXIT_CANCELLED = 130


class HostError(RuntimeError):
    """8bf-host is missing or failed."""


@dataclass
class Result:
    status: str
    message: str = ""
    stdout: str = ""
    log: List[str] = field(default_factory=list)

    @property
    def ok(self):
        return self.status == "ok"


def _candidates(home):
    suffix = ".exe" if sys.platform == "win32" else ""
    return [
        os.path.join(home, ".cargo", "bin", PROGRAM + suffix),
        os.path.join(home, ".local", "bin", PROGRAM + suffix),
    ]


def find_executable(configured="", which=shutil.which, home=None):
    """Return the 8bf-host to use, or "" when there is none.

    A configured path wins. Otherwise look on PATH and in the folders
    ``cargo install`` and user installs use, since Krita started from a
    desktop menu often has a shorter PATH than a terminal.
    """
    if configured:
        return configured
    found = which(PROGRAM)
    if found:
        return found
    for path in _candidates(home or os.path.expanduser("~")):
        if os.path.isfile(path):
            return path
    return ""


def require_executable(configured=""):
    executable = find_executable(configured)
    if not executable:
        raise HostError(
            "8bf-host was not found. Download it from %s, then set its location in "
            "Tools > Scripts > 8bf Filter Settings." % DOWNLOAD_URL
        )
    return executable


def folder_args(folders):
    args = []
    for folder in folders:
        args += ["--plugin-dir", folder]
    return args


def list_command(executable, folders, rescan=False):
    return [executable, "list", "--json"] + folder_args(folders) + (["--rescan"] if rescan else [])


def about_command(executable, folders, filter_id):
    return [executable, "about", filter_id] + folder_args(folders)


def doctor_command(executable, folders):
    return [executable, "doctor"] + folder_args(folders)


def run_command(
    executable,
    folders,
    filter_id,
    input_path,
    output_path,
    dialog=True,
    preset=None,
    save_preset=None,
    mask=None,
    rect=None,
    foreground=(0, 0, 0),
    background=(255, 255, 255),
    resolution=72.0,
    allow_8bit_fallback=True,
):
    """Build an ``8bf-host run`` command. ``rect`` is ``(x, y, width, height)``."""
    command = [executable, "run", filter_id, input_path, output_path, "--verbose"]
    command += folder_args(folders)
    if dialog:
        command.append("--dialog")
    if preset:
        command += ["--preset", preset]
    if save_preset:
        command += ["--save-preset", save_preset]
    if mask:
        command += ["--mask", mask]
    if rect:
        command += ["--rect", "%d,%d,%d,%d" % tuple(rect)]
    command += [
        "--foreground",
        "#%02x%02x%02x" % tuple(foreground),
        "--background",
        "#%02x%02x%02x" % tuple(background),
        "--resolution",
        "%g" % resolution,
    ]
    if not allow_8bit_fallback:
        command.append("--no-8bit-fallback")
    return command


def _popen_flags():
    if sys.platform == "win32":
        # Do not flash a console window for the host.
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def _interrupt(process):
    """Ask 8bf-host to stop the filter, as Ctrl+C does in a terminal."""
    if sys.platform == "win32":
        # A process without a console cannot receive Ctrl+C.
        process.terminate()
    else:
        process.send_signal(signal.SIGINT)


def _collect(stream, sink):
    for raw in iter(stream.readline, b""):
        sink.append(raw.decode("utf-8", "replace"))
    stream.close()


def _error_message(lines, returncode):
    for line in reversed(lines):
        if line.startswith("error: "):
            return line[len("error: ") :]
    detail = "\n".join(lines[-15:]).strip()
    return "8bf-host exited with code %s.%s" % (returncode, ("\n\n" + detail) if detail else "")


def run(command, pump=lambda: None, cancelled=lambda: False, grace=10.0, cwd=None):
    """Run 8bf-host and wait for it, calling ``pump`` while it runs.

    When ``cancelled()`` turns true the host is asked to stop the filter;
    if it has not exited ``grace`` seconds later it is killed.
    """
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            **_popen_flags(),
        )
    except OSError as exc:
        return Result("error", "Could not start 8bf-host (%s): %s" % (command[0], exc))
    stdout, stderr = [], []
    readers = [
        threading.Thread(target=_collect, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_collect, args=(process.stderr, stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    cancel_sent = None
    while process.poll() is None:
        pump()
        if cancel_sent is None and cancelled():
            _interrupt(process)
            cancel_sent = time.monotonic()
        if cancel_sent is not None and time.monotonic() - cancel_sent > grace:
            process.kill()
            process.wait()
            return Result("cancelled", "Cancelled.")
        time.sleep(0.03)
    for reader in readers:
        reader.join(5)
    pump()
    log = [line.rstrip() for line in stderr]
    output = "".join(stdout)
    if process.returncode == 0:
        return Result("ok", stdout=output, log=log)
    if process.returncode == EXIT_CANCELLED or cancel_sent is not None:
        return Result("cancelled", "Cancelled.", output, log)
    return Result("error", _error_message(log, process.returncode), output, log)


def list_filters(executable, folders, rescan=False, runner=run):
    """Return ``(filters, problems)`` as 8bf-host's ``list --json`` reports them."""
    result = runner(list_command(executable, folders, rescan))
    if not result.ok:
        raise HostError(result.message)
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise HostError("8bf-host printed a filter list that is not JSON: %s" % exc) from exc
    return payload.get("filters", []), payload.get("problems", [])
