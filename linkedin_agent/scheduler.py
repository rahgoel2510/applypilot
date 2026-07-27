"""Background service / daemon runner for LinkedIn Job Agent.

Provides cross-platform scheduling via APScheduler with platform-specific
daemon support (systemd, launchd, Windows Task Scheduler) and a robust
foreground fallback mode.
"""

from __future__ import annotations

import atexit
import fcntl
import logging
import os
import platform
import signal
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from platformdirs import user_data_dir, user_log_dir

from linkedin_agent.config import Settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME = "linkedin-agent"
APP_AUTHOR = "linkedin-agent"

logger = logging.getLogger(__name__)


def _get_runtime_dir() -> Path:
    """Return a platform-appropriate runtime directory for PID/lock files."""
    data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _get_log_dir() -> Path:
    """Return a platform-appropriate log directory."""
    log_dir = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# ---------------------------------------------------------------------------
# PID / Lock file management
# ---------------------------------------------------------------------------


class PIDFile:
    """Manages a PID file to prevent duplicate instances."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (_get_runtime_dir() / "agent.pid")
        self._file = None

    def acquire(self) -> bool:
        """Attempt to acquire the PID file. Returns True on success."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.path, "w")
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._file.write(str(os.getpid()))
            self._file.flush()
            return True
        except (OSError, IOError):
            logger.error(
                "Another instance is already running (PID file: %s)", self.path
            )
            return False

    def release(self) -> None:
        """Release the PID file."""
        if self._file is not None:
            try:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
                self._file.close()
            except (OSError, IOError):
                pass
            finally:
                self._file = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def is_locked(self) -> bool:
        """Check if another process holds the PID file lock."""
        if not self.path.exists():
            return False
        try:
            f = open(self.path, "r+")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()
            return False
        except (OSError, IOError):
            return True


class LockFile:
    """File-based lock to serialize scheduler runs."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (_get_runtime_dir() / "agent.lock")
        self._file = None

    def __enter__(self) -> "LockFile":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "w")
        fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._file:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None


# ---------------------------------------------------------------------------
# AgentScheduler
# ---------------------------------------------------------------------------


class AgentScheduler:
    """Cross-platform scheduler that invokes the orchestrator at configured intervals.

    Args:
        config: Application Settings instance (from config module).
        orchestrator_callback: The main job scanning function to invoke each cycle.
    """

    def __init__(
        self,
        config: Settings,
        orchestrator_callback: Callable[[], Any],
    ) -> None:
        self.config = config
        self._callback = orchestrator_callback
        self._scheduler: BlockingScheduler | None = None
        self._pid_file = PIDFile()
        self._lock_file = LockFile()
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler (blocks the calling thread)."""
        if not self._pid_file.acquire():
            logger.error("Cannot start — another instance is running.")
            sys.exit(1)

        atexit.register(self._cleanup)
        self._register_signals()

        interval = self.config.scheduler.interval_minutes
        logger.info(
            "Starting scheduler: interval=%d min, active_hours=%d–%d",
            interval,
            self.config.scheduler.active_hours_start,
            self.config.scheduler.active_hours_end,
        )

        self._scheduler = BlockingScheduler()
        self._scheduler.add_job(
            self._run_cycle,
            trigger=IntervalTrigger(minutes=interval),
            id="linkedin_scan",
            name="LinkedIn Job Scan",
            next_run_time=datetime.now(),  # run immediately on start
            max_instances=1,
            misfire_grace_time=interval * 60,  # seconds
        )
        self._running = True

        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        logger.info("Shutting down scheduler...")
        self._running = False
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._cleanup()

    def is_within_active_hours(self) -> bool:
        """Check if the current time falls within configured active hours."""
        now = datetime.now()
        start = self.config.scheduler.active_hours_start
        end = self.config.scheduler.active_hours_end
        if start <= end:
            return start <= now.hour < end
        # Wrap-around (e.g., active_hours_start=22, end=6)
        return now.hour >= start or now.hour < end

    def get_next_run_time(self) -> datetime | None:
        """Return when the next scan will happen, or None if scheduler isn't running."""
        if self._scheduler is None:
            return None
        job = self._scheduler.get_job("linkedin_scan")
        if job and job.next_run_time:
            return job.next_run_time.replace(tzinfo=None)
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_cycle(self) -> None:
        """Execute a single scan cycle with crash recovery."""
        if not self.is_within_active_hours():
            logger.info(
                "Outside active hours (%d–%d). Skipping this cycle.",
                self.config.scheduler.active_hours_start,
                self.config.scheduler.active_hours_end,
            )
            return

        try:
            with self._lock_file:
                logger.info("Starting scan cycle at %s", datetime.now().isoformat())
                self._callback()
                logger.info("Scan cycle completed successfully.")
        except Exception as exc:
            logger.exception(
                "Scan cycle failed (will retry next interval): %s", exc
            )

    def _register_signals(self) -> None:
        """Register handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle termination signals."""
        logger.info("Received signal %d — stopping scheduler.", signum)
        self.stop()

    def _cleanup(self) -> None:
        """Release PID file and perform cleanup."""
        self._pid_file.release()


# ---------------------------------------------------------------------------
# Platform-specific service generation
# ---------------------------------------------------------------------------


def generate_systemd_service(install_path: str) -> str:
    """Generate a systemd service unit file for Linux.

    Args:
        install_path: Absolute path to the project/virtualenv.

    Returns:
        Contents of the .service file.
    """
    python_bin = os.path.join(install_path, "venv", "bin", "python")
    working_dir = install_path

    return textwrap.dedent(f"""\
        [Unit]
        Description=LinkedIn Job Agent — Automated Job Application Service
        After=network-online.target
        Wants=network-online.target

        [Service]
        Type=simple
        User={os.getenv("USER", "nobody")}
        WorkingDirectory={working_dir}
        ExecStart={python_bin} -m linkedin_agent
        Restart=on-failure
        RestartSec=30
        StandardOutput=journal
        StandardError=journal
        Environment=PATH={os.path.join(install_path, "venv", "bin")}:/usr/bin:/bin
        EnvironmentFile={os.path.join(install_path, ".env")}

        # Hardening
        NoNewPrivileges=yes
        ProtectSystem=strict
        ProtectHome=read-only
        ReadWritePaths={_get_runtime_dir()} {_get_log_dir()} {install_path}

        [Install]
        WantedBy=default.target
    """)


def generate_launchd_plist(install_path: str) -> str:
    """Generate a macOS launchd plist file.

    Args:
        install_path: Absolute path to the project/virtualenv.

    Returns:
        Contents of the .plist file.
    """
    python_bin = os.path.join(install_path, "venv", "bin", "python")
    log_dir = _get_log_dir()
    stdout_log = os.path.join(str(log_dir), "agent-stdout.log")
    stderr_log = os.path.join(str(log_dir), "agent-stderr.log")

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>com.linkedin-agent</string>

            <key>ProgramArguments</key>
            <array>
                <string>{python_bin}</string>
                <string>-m</string>
                <string>linkedin_agent</string>
            </array>

            <key>WorkingDirectory</key>
            <string>{install_path}</string>

            <key>RunAtLoad</key>
            <true/>

            <key>KeepAlive</key>
            <dict>
                <key>SuccessfulExit</key>
                <false/>
            </dict>

            <key>ThrottleInterval</key>
            <integer>30</integer>

            <key>StandardOutPath</key>
            <string>{stdout_log}</string>

            <key>StandardErrorPath</key>
            <string>{stderr_log}</string>

            <key>EnvironmentVariables</key>
            <dict>
                <key>PATH</key>
                <string>{os.path.join(install_path, "venv", "bin")}:/usr/local/bin:/usr/bin:/bin</string>
            </dict>
        </dict>
        </plist>
    """)


def generate_windows_task_xml(install_path: str) -> str:
    """Generate a Windows Task Scheduler XML definition.

    Args:
        install_path: Absolute path to the project/virtualenv.

    Returns:
        Contents of the Task Scheduler XML file.
    """
    python_bin = os.path.join(install_path, "venv", "Scripts", "python.exe")
    username = os.getenv("USERNAME", os.getenv("USER", "SYSTEM"))

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-16"?>
        <Task version="1.4"
              xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <RegistrationInfo>
            <Description>LinkedIn Job Agent — Automated Job Application Service</Description>
            <Author>{username}</Author>
          </RegistrationInfo>
          <Triggers>
            <LogonTrigger>
              <Enabled>true</Enabled>
            </LogonTrigger>
          </Triggers>
          <Principals>
            <Principal id="Author">
              <UserId>{username}</UserId>
              <LogonType>InteractiveToken</LogonType>
              <RunLevel>LeastPrivilege</RunLevel>
            </Principal>
          </Principals>
          <Settings>
            <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
            <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
            <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
            <AllowHardTerminate>true</AllowHardTerminate>
            <StartWhenAvailable>true</StartWhenAvailable>
            <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
            <AllowStartOnDemand>true</AllowStartOnDemand>
            <Enabled>true</Enabled>
            <Hidden>false</Hidden>
            <RestartOnFailure>
              <Interval>PT1M</Interval>
              <Count>3</Count>
            </RestartOnFailure>
            <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
          </Settings>
          <Actions>
            <Exec>
              <Command>{python_bin}</Command>
              <Arguments>-m linkedin_agent</Arguments>
              <WorkingDirectory>{install_path}</WorkingDirectory>
            </Exec>
          </Actions>
        </Task>
    """)


# ---------------------------------------------------------------------------
# Service installation helpers
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Detect the current platform. Returns 'linux', 'darwin', or 'windows'."""
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "windows":
        return "windows"
    return "linux"


def install_service(install_path: str | None = None) -> None:
    """Auto-detect platform and install the background service.

    Args:
        install_path: Project root. Defaults to this module's project root.
    """
    if install_path is None:
        install_path = str(Path(__file__).resolve().parent.parent)

    plat = _detect_platform()
    logger.info("Detected platform: %s", plat)

    if plat == "linux":
        _install_systemd(install_path)
    elif plat == "darwin":
        _install_launchd(install_path)
    elif plat == "windows":
        _install_windows_task(install_path)
    else:
        logger.warning(
            "Unsupported platform '%s'. Use the foreground scheduler instead.", plat
        )


def uninstall_service() -> None:
    """Auto-detect platform and remove the background service."""
    plat = _detect_platform()
    logger.info("Uninstalling service for platform: %s", plat)

    if plat == "linux":
        _uninstall_systemd()
    elif plat == "darwin":
        _uninstall_launchd()
    elif plat == "windows":
        _uninstall_windows_task()


# ------------------------------------------------------------------
# Linux / systemd
# ------------------------------------------------------------------


def _install_systemd(install_path: str) -> None:
    """Install systemd user service."""
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_file = service_dir / "linkedin-agent.service"

    content = generate_systemd_service(install_path)
    service_file.write_text(content, encoding="utf-8")

    logger.info("Service file written to %s", service_file)
    print(
        textwrap.dedent(f"""\
        ✅ systemd service installed at: {service_file}

        To enable and start:
            systemctl --user daemon-reload
            systemctl --user enable linkedin-agent.service
            systemctl --user start linkedin-agent.service

        To check status:
            systemctl --user status linkedin-agent.service
            journalctl --user -u linkedin-agent.service -f
        """)
    )


def _uninstall_systemd() -> None:
    """Remove systemd user service."""
    service_file = Path.home() / ".config" / "systemd" / "user" / "linkedin-agent.service"
    cmds = [
        ["systemctl", "--user", "stop", "linkedin-agent.service"],
        ["systemctl", "--user", "disable", "linkedin-agent.service"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, check=False, capture_output=True)
        except FileNotFoundError:
            pass

    if service_file.exists():
        service_file.unlink()
        logger.info("Removed %s", service_file)
    else:
        logger.info("Service file not found at %s — nothing to remove.", service_file)

    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass

    print("✅ systemd service uninstalled.")


# ------------------------------------------------------------------
# macOS / launchd
# ------------------------------------------------------------------


def _install_launchd(install_path: str) -> None:
    """Install macOS launchd agent."""
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_file = agents_dir / "com.linkedin-agent.plist"

    content = generate_launchd_plist(install_path)
    plist_file.write_text(content, encoding="utf-8")

    logger.info("Plist written to %s", plist_file)
    print(
        textwrap.dedent(f"""\
        ✅ launchd agent installed at: {plist_file}

        To load and start:
            launchctl load {plist_file}

        To stop and unload:
            launchctl unload {plist_file}

        To check status:
            launchctl list | grep linkedin-agent

        Logs:
            {_get_log_dir() / "agent-stdout.log"}
            {_get_log_dir() / "agent-stderr.log"}
        """)
    )


def _uninstall_launchd() -> None:
    """Remove macOS launchd agent."""
    plist_file = Path.home() / "Library" / "LaunchAgents" / "com.linkedin-agent.plist"

    if plist_file.exists():
        try:
            subprocess.run(
                ["launchctl", "unload", str(plist_file)],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pass
        plist_file.unlink()
        logger.info("Removed %s", plist_file)
    else:
        logger.info("Plist not found at %s — nothing to remove.", plist_file)

    print("✅ launchd agent uninstalled.")


# ------------------------------------------------------------------
# Windows / Task Scheduler
# ------------------------------------------------------------------


def _install_windows_task(install_path: str) -> None:
    """Install Windows Task Scheduler task."""
    task_dir = Path(install_path)
    xml_file = task_dir / "linkedin-agent-task.xml"
    bat_file = task_dir / "run-agent.bat"

    # Write XML
    xml_content = generate_windows_task_xml(install_path)
    xml_file.write_text(xml_content, encoding="utf-16")

    # Write batch file
    python_bin = os.path.join(install_path, "venv", "Scripts", "python.exe")
    bat_content = textwrap.dedent(f"""\
        @echo off
        cd /d "{install_path}"
        "{python_bin}" -m linkedin_agent
    """)
    bat_file.write_text(bat_content, encoding="utf-8")

    logger.info("Task XML written to %s", xml_file)
    logger.info("Batch file written to %s", bat_file)
    print(
        textwrap.dedent(f"""\
        ✅ Windows Task Scheduler files created:
            XML:   {xml_file}
            Batch: {bat_file}

        To register the task (run as admin):
            schtasks /create /tn "LinkedInAgent" /xml "{xml_file}"

        To run immediately:
            schtasks /run /tn "LinkedInAgent"

        To check status:
            schtasks /query /tn "LinkedInAgent"
        """)
    )


def _uninstall_windows_task() -> None:
    """Remove Windows Task Scheduler task."""
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", "LinkedInAgent", "/f"],
            check=False,
            capture_output=True,
        )
        print("✅ Windows scheduled task 'LinkedInAgent' removed.")
    except FileNotFoundError:
        logger.warning("schtasks not found — are you running on Windows?")
        print("⚠️  Could not remove task. Manually delete 'LinkedInAgent' from Task Scheduler.")


# ---------------------------------------------------------------------------
# CLI entry point (for direct execution)
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the scheduler as a foreground process (cross-platform fallback)."""
    from linkedin_agent.config import get_config

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = get_config()

    # Placeholder callback — in production, this comes from the orchestrator
    def _orchestrator_stub() -> None:
        logger.info("Orchestrator callback invoked (stub).")

    scheduler = AgentScheduler(config=config, orchestrator_callback=_orchestrator_stub)
    scheduler.start()


if __name__ == "__main__":
    main()
