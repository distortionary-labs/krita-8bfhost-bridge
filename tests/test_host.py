import json
import os
import sys
import textwrap

import pytest

from krita_8bfhost_bridge import host


def fake_host(tmp_path, body):
    """A stand-in for 8bf-host: a Python script run with this interpreter."""
    script = tmp_path / "fake_host.py"
    script.write_text("import sys, time\n" + textwrap.dedent(body))
    return [sys.executable, str(script)]


def test_configured_executable_wins():
    assert host.find_executable("/opt/8bf-host", which=lambda _name: "/usr/bin/8bf-host") == (
        "/opt/8bf-host"
    )


def test_executable_on_path():
    assert host.find_executable("", which=lambda _name: "/usr/bin/8bf-host") == "/usr/bin/8bf-host"


def test_executable_from_cargo_install(tmp_path):
    binary = (
        tmp_path / ".cargo" / "bin" / ("8bf-host.exe" if sys.platform == "win32" else "8bf-host")
    )
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    assert host.find_executable("", which=lambda _name: None, home=str(tmp_path)) == str(binary)


def test_missing_executable(tmp_path):
    assert host.find_executable("", which=lambda _name: None, home=str(tmp_path)) == ""


def test_missing_executable_explains_the_download(monkeypatch):
    monkeypatch.setattr(host, "find_executable", lambda _configured: "")
    with pytest.raises(host.HostError, match="github.com/distortionary-labs/8bf-host"):
        host.require_executable("")


def test_run_command():
    command = host.run_command(
        "8bf-host",
        ["/a", "/b"],
        "1a2b3c4d5e6f",
        "in.pam",
        "out.pam",
        dialog=False,
        preset="p.json",
        save_preset="p.json",
        mask="mask.pgm",
        rect=(1, 2, 30, 40),
        foreground=(255, 128, 0),
        background=(0, 0, 0),
        resolution=300.0,
        allow_8bit_fallback=False,
    )
    assert command == [
        "8bf-host", "run", "1a2b3c4d5e6f", "in.pam", "out.pam", "--verbose",
        "--plugin-dir", "/a", "--plugin-dir", "/b",
        "--preset", "p.json", "--save-preset", "p.json",
        "--mask", "mask.pgm", "--rect", "1,2,30,40",
        "--foreground", "#ff8000", "--background", "#000000", "--resolution", "300",
        "--no-8bit-fallback",
    ]  # fmt: skip


def test_run_command_defaults_show_the_dialog():
    command = host.run_command("8bf-host", [], "id", "in.pam", "out.pam")
    assert "--dialog" in command
    assert "--preset" not in command
    assert "--no-8bit-fallback" not in command


def test_other_commands():
    assert host.list_command("h", ["/a"], rescan=True) == [
        "h", "list", "--json", "--plugin-dir", "/a", "--rescan",
    ]  # fmt: skip
    assert host.about_command("h", [], "id") == ["h", "about", "id"]
    assert host.doctor_command("h", ["/a"]) == ["h", "doctor", "--plugin-dir", "/a"]


def test_successful_run_collects_output(tmp_path):
    command = fake_host(
        tmp_path,
        """
        print("hello")
        sys.stderr.write("[host] a log line\\n")
        """,
    )
    pumps = []
    result = host.run(command, pump=lambda: pumps.append(1))
    assert result.ok
    assert result.stdout == "hello\n"
    assert result.log == ["[host] a log line"]
    assert pumps


def test_failed_run_reports_the_error_line(tmp_path):
    command = fake_host(
        tmp_path,
        """
        sys.stderr.write("[host] details\\nerror: the filter failed on purpose\\nhint: x\\n")
        sys.exit(1)
        """,
    )
    result = host.run(command)
    assert result.status == "error"
    assert result.message == "the filter failed on purpose"
    assert "[host] details" in result.log


def test_crash_without_an_error_line(tmp_path):
    command = fake_host(tmp_path, "sys.stderr.write('Segmentation fault\\n'); sys.exit(139)")
    result = host.run(command)
    assert result.status == "error"
    assert "exited with code 139" in result.message
    assert "Segmentation fault" in result.message


def test_exit_code_130_is_a_cancel(tmp_path):
    assert host.run(fake_host(tmp_path, "sys.exit(130)")).status == "cancelled"


def test_program_that_cannot_start(tmp_path):
    result = host.run([str(tmp_path / "missing")])
    assert result.status == "error"
    assert "Could not start 8bf-host" in result.message


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGINT for such processes")
def test_cancel_interrupts_the_host(tmp_path):
    ready = tmp_path / "ready"
    marker = tmp_path / "interrupted"
    command = fake_host(
        tmp_path,
        """
        import signal
        def stop(*_):
            open(%r, "w").close()
            sys.exit(130)
        signal.signal(signal.SIGINT, stop)
        open(%r, "w").close()
        time.sleep(30)
        """
        % (str(marker), str(ready)),
    )
    result = host.run(command, cancelled=ready.exists)
    assert result.status == "cancelled"
    assert marker.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="uses SIGINT")
def test_cancel_kills_a_host_that_ignores_it(tmp_path):
    command = fake_host(
        tmp_path,
        """
        import signal
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        time.sleep(30)
        """,
    )
    result = host.run(command, cancelled=lambda: True, grace=0.3)
    assert result.status == "cancelled"


def test_list_filters_parses_json():
    payload = {"filters": [{"id": "abc", "name": "Invert"}], "problems": [{"path": "x"}]}

    def runner(command):
        assert command[1:3] == ["list", "--json"]
        return host.Result("ok", stdout=json.dumps(payload))

    assert host.list_filters("h", [], runner=runner) == (payload["filters"], payload["problems"])


def test_list_filters_failures():
    with pytest.raises(host.HostError, match="bad config"):
        host.list_filters("h", [], runner=lambda _c: host.Result("error", "bad config"))
    with pytest.raises(host.HostError, match="not JSON"):
        host.list_filters("h", [], runner=lambda _c: host.Result("ok", stdout="nope"))


def test_run_uses_the_working_directory(tmp_path):
    command = fake_host(tmp_path, "import os; print(os.getcwd())")
    work = tmp_path / "work"
    work.mkdir()
    result = host.run(command, cwd=str(work))
    assert os.path.samefile(result.stdout.strip(), str(work))
