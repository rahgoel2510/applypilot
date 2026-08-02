"""Allow running the package with `python -m linkedin_agent <command>`."""

from __future__ import annotations

import argparse
import asyncio
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

from linkedin_agent import __version__


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="linkedin_agent",
        description="LinkedIn Job Agent — automated job application bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python -m linkedin_agent run
              python -m linkedin_agent daemon
              python -m linkedin_agent status
              python -m linkedin_agent config
        """),
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-c", "--config", default="config.yaml", help="Path to config file"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run — single scan cycle
    sub_run = subparsers.add_parser("run", help="Run one scan cycle")
    sub_run.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Scan and score jobs but do NOT submit applications",
    )
    sub_run.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override max_postings_per_run from config",
    )
    sub_run.set_defaults(func=_cmd_run)

    # daemon — continuous background service
    sub_daemon = subparsers.add_parser("daemon", help="Run as background service")
    sub_daemon.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Scan and score jobs but do NOT submit applications",
    )
    sub_daemon.set_defaults(func=_cmd_daemon)

    # install-service
    sub_install = subparsers.add_parser(
        "install-service", help="Install as OS service (launchd/systemd)"
    )
    sub_install.set_defaults(func=_cmd_install_service)

    # uninstall-service
    sub_uninstall = subparsers.add_parser(
        "uninstall-service", help="Remove OS service"
    )
    sub_uninstall.set_defaults(func=_cmd_uninstall_service)

    # status
    sub_status = subparsers.add_parser("status", help="Show current tally/status")
    sub_status.set_defaults(func=_cmd_status)

    # config
    sub_config = subparsers.add_parser("config", help="Show current configuration")
    sub_config.set_defaults(func=_cmd_config)

    return parser


# ─── Command Handlers ───────────────────────────────────────────────────


def _cmd_run(args: argparse.Namespace) -> None:
    """Run a single scan cycle."""
    from linkedin_agent.config import get_config
    from linkedin_agent.logger import setup_logging
    from linkedin_agent.orchestrator import JobAgent

    setup_logging(level="INFO")
    config = get_config(validate=True)
    agent = JobAgent(config=config, dry_run=args.dry_run)

    if args.dry_run:
        print("🔍 DRY RUN MODE — jobs will be scanned and scored, NOT applied to")

    if args.limit:
        # Override max_postings_per_run for this invocation
        from dataclasses import replace

        new_js = replace(config.job_search, max_postings_per_run=args.limit)
        config = replace(config, job_search=new_js)
        agent = JobAgent(config=config, dry_run=args.dry_run)

    # Register signal handlers for graceful shutdown
    def _handle_signal(sig: int, frame) -> None:
        print("\n⚠️  Interrupt received, shutting down gracefully...")
        agent.request_shutdown()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    asyncio.run(agent.run_once())


def _cmd_daemon(args: argparse.Namespace) -> None:
    """Run the agent as a continuous daemon."""
    from linkedin_agent.config import get_config
    from linkedin_agent.logger import setup_logging
    from linkedin_agent.orchestrator import JobAgent

    setup_logging(level="INFO")
    config = get_config(validate=True)
    agent = JobAgent(config=config, dry_run=args.dry_run)

    if args.dry_run:
        print("🔍 DRY RUN MODE — jobs will be scanned and scored, NOT applied to")

    # Register signal handlers for graceful shutdown
    def _handle_signal(sig: int, frame) -> None:
        print("\n⚠️  Interrupt received, shutting down gracefully...")
        agent.request_shutdown()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    asyncio.run(agent.run_daemon())


def _cmd_install_service(args: argparse.Namespace) -> None:
    """Install the agent as an OS-level service."""
    if sys.platform == "darwin":
        _install_launchd(args)
    elif sys.platform == "linux":
        _install_systemd(args)
    else:
        print(f"❌ Unsupported platform for service installation: {sys.platform}")
        sys.exit(1)


def _cmd_uninstall_service(args: argparse.Namespace) -> None:
    """Remove the OS-level service."""
    if sys.platform == "darwin":
        _uninstall_launchd()
    elif sys.platform == "linux":
        _uninstall_systemd()
    else:
        print(f"❌ Unsupported platform for service removal: {sys.platform}")
        sys.exit(1)


def _cmd_status(args: argparse.Namespace) -> None:
    """Show current tally and agent status."""
    from linkedin_agent.config import get_config

    config = get_config(validate=False)
    print("📊 LinkedIn Job Agent Status")
    print("─" * 30)
    print(f"Version:    {__version__}")
    print(f"Collection: {config.job_search.collection}")
    print(f"Threshold:  {config.job_search.match_threshold}")
    print(f"Interval:   {config.scheduler.interval_minutes}m")
    print(
        f"Active:     "
        f"{config.scheduler.active_hours_start}:00–"
        f"{config.scheduler.active_hours_end}:00"
    )
    print(f"InMail:     {'enabled' if config.inmail.enabled else 'disabled'}")


def _cmd_config(args: argparse.Namespace) -> None:
    """Display the current configuration."""
    import dataclasses

    import yaml

    from linkedin_agent.config import get_config

    config = get_config(validate=False)

    # Convert Settings dataclass to a dict for display
    config_dict = _settings_to_dict(config)

    # Mask sensitive fields
    display = _mask_sensitive(config_dict)

    print("⚙️  Current Configuration")
    print("─" * 30)
    print(yaml.dump(display, default_flow_style=False, sort_keys=False))


def _settings_to_dict(settings) -> dict:
    """Recursively convert a Settings dataclass to a plain dict."""
    import dataclasses

    result = {}
    for f in dataclasses.fields(settings):
        value = getattr(settings, f.name)
        if dataclasses.is_dataclass(value):
            result[f.name] = _settings_to_dict(value)
        elif isinstance(value, Path):
            result[f.name] = str(value)
        elif isinstance(value, list):
            result[f.name] = list(value)
        else:
            result[f.name] = value
    return result


def _mask_sensitive(config: dict) -> dict:
    """Mask sensitive values in config for display."""
    import copy

    masked = copy.deepcopy(config)
    sensitive_keys = {"api_key", "token", "password", "secret", "bot_token", "chat_id"}

    def _walk(d: dict) -> None:
        for key, value in d.items():
            if isinstance(value, dict):
                _walk(value)
            elif isinstance(value, str) and any(s in key.lower() for s in sensitive_keys):
                if len(value) > 4:
                    d[key] = value[:4] + "****"
                elif value:
                    d[key] = "****"

    _walk(masked)
    return masked


# ─── Service Installation (macOS launchd) ──────────────────────────────


_LAUNCHD_LABEL = "com.linkedin-job-agent.daemon"
_LAUNCHD_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"


def _install_launchd(args: argparse.Namespace) -> None:
    """Install as a macOS LaunchAgent."""
    python_path = sys.executable
    working_dir = Path.cwd()
    config_path = Path(args.config).resolve()

    plist_content = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{_LAUNCHD_LABEL}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{python_path}</string>
                <string>-m</string>
                <string>linkedin_agent</string>
                <string>daemon</string>
                <string>-c</string>
                <string>{config_path}</string>
            </array>
            <key>WorkingDirectory</key>
            <string>{working_dir}</string>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
            <key>StandardOutPath</key>
            <string>{working_dir}/logs/agent-stdout.log</string>
            <key>StandardErrorPath</key>
            <string>{working_dir}/logs/agent-stderr.log</string>
        </dict>
        </plist>
    """)

    _LAUNCHD_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LAUNCHD_PLIST_PATH.write_text(plist_content)

    # Create logs directory
    (working_dir / "logs").mkdir(exist_ok=True)

    # Load the agent
    subprocess.run(["launchctl", "load", str(_LAUNCHD_PLIST_PATH)], check=True)
    print(f"✅ Service installed: {_LAUNCHD_LABEL}")
    print(f"   Plist: {_LAUNCHD_PLIST_PATH}")
    print(f"   Logs:  {working_dir}/logs/")


def _uninstall_launchd() -> None:
    """Uninstall the macOS LaunchAgent."""
    if _LAUNCHD_PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(_LAUNCHD_PLIST_PATH)], check=False)
        _LAUNCHD_PLIST_PATH.unlink()
        print(f"✅ Service removed: {_LAUNCHD_LABEL}")
    else:
        print(f"⚠️  Service not found: {_LAUNCHD_PLIST_PATH}")


# ─── Service Installation (Linux systemd) ──────────────────────────────


_SYSTEMD_SERVICE = "linkedin-job-agent"
_SYSTEMD_UNIT_PATH = Path.home() / ".config" / "systemd" / "user" / f"{_SYSTEMD_SERVICE}.service"


def _install_systemd(args: argparse.Namespace) -> None:
    """Install as a systemd user service."""
    python_path = sys.executable
    working_dir = Path.cwd()
    config_path = Path(args.config).resolve()

    unit_content = textwrap.dedent(f"""\
        [Unit]
        Description=LinkedIn Job Agent
        After=network-online.target
        Wants=network-online.target

        [Service]
        Type=simple
        WorkingDirectory={working_dir}
        ExecStart={python_path} -m linkedin_agent daemon -c {config_path}
        Restart=on-failure
        RestartSec=30

        [Install]
        WantedBy=default.target
    """)

    _SYSTEMD_UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SYSTEMD_UNIT_PATH.write_text(unit_content)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", _SYSTEMD_SERVICE], check=True)
    subprocess.run(["systemctl", "--user", "start", _SYSTEMD_SERVICE], check=True)
    print(f"✅ Service installed and started: {_SYSTEMD_SERVICE}")
    print(f"   Unit: {_SYSTEMD_UNIT_PATH}")
    print(f"   Check: systemctl --user status {_SYSTEMD_SERVICE}")


def _uninstall_systemd() -> None:
    """Uninstall the systemd user service."""
    if _SYSTEMD_UNIT_PATH.exists():
        subprocess.run(
            ["systemctl", "--user", "stop", _SYSTEMD_SERVICE], check=False
        )
        subprocess.run(
            ["systemctl", "--user", "disable", _SYSTEMD_SERVICE], check=False
        )
        _SYSTEMD_UNIT_PATH.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        print(f"✅ Service removed: {_SYSTEMD_SERVICE}")
    else:
        print(f"⚠️  Service not found: {_SYSTEMD_UNIT_PATH}")


# ─── CLI Entry Point ────────────────────────────────────────────────────


def cli() -> None:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    cli()
