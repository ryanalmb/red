"""Cyber-Red CLI Entry Point.

This module provides the command-line interface for controlling the Cyber-Red daemon
and managing engagements.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any
import asyncio

import structlog
import typer

from cyberred.core.config import (
    EngagementConfig,
    ConfigurationError,
    get_settings,
    load_yaml_file,
)
from cyberred.daemon.ipc import (
    IPCCommand,
    build_request,
    encode_message,
    decode_message,
)

# Initialize settings and logger
# Note: Full logging config happens after we potentially load a config file
settings = get_settings()

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# Main app
app = typer.Typer(
    name="cyber-red",
    help="Cyber-Red v2.0 - Autonomous Penetration Testing Framework",
    no_args_is_help=True,
)

# Daemon subcommand group
daemon_app = typer.Typer(help="Daemon management commands", no_args_is_help=True)
app.add_typer(daemon_app, name="daemon")


def get_socket_path() -> Path:
    """Get the daemon socket path from settings."""
    base_path = Path(get_settings().storage.base_path).expanduser()
    return base_path / "daemon.sock"


def configure_logging() -> None:
    """Reconfigure logging based on loaded settings."""
    cfg = get_settings().logging
    # In a real app we might change the renderer based on cfg.format
    # and the level based on cfg.level.
    # For now, we just log that we are configuring it.
    pass


def load_config_callback(config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to configuration file", is_eager=True)) -> Optional[Path]:
    """Load configuration file if provided."""
    if config:
        if not config.exists():
            typer.echo(f"Error: Config file '{config}' not found", err=True)
            raise typer.Exit(code=1)
        
        try:
            # Force reload to apply new system config
            get_settings(force_reload=True, system_config_path=config)
            log.info("config_loaded", path=str(config))
        except ConfigurationError as e:
            typer.echo(f"Error loading config: {e}", err=True)
            raise typer.Exit(code=1)
    
    configure_logging()
    return config


@app.callback()
def main(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", 
        callback=load_config_callback, 
        is_eager=True, 
        help="Path to global configuration file"
    ),
) -> None:
    """Cyber-Red CLI."""
    pass


async def _send_ipc_request(command: IPCCommand, params: Optional[dict[str, Any]] = None) -> Any:
    """Send IPC request and return response data.
    
    Args:
        command: IPC command to send.
        params: Optional parameters for the command.
        
    Returns:
        Response data if successful (dict or None).
        
    Raises:
        typer.Exit: If connection fails or server returns error.
    """
    socket_path = get_socket_path()
    if not socket_path.exists():
        typer.echo("Error: Daemon not running", err=True)
        raise typer.Exit(code=1)
        
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        request = build_request(command, **(params or {}))
        writer.write(encode_message(request))
        await writer.drain()
        
        data = await reader.readline()
        response = decode_message(data)
        
        writer.close()
        await writer.wait_closed()
        
        if response.status == "ok":
            return response.data
        
        # Handle known error cases nicely
        error_msg = response.error or "Unknown error"
        if "Engagement not found" in error_msg:
             typer.echo(f"Error: {error_msg}", err=True)
        elif "Invalid state transition" in error_msg:
             if command == IPCCommand.ENGAGEMENT_PAUSE:
                 typer.echo("Error: Cannot pause - engagement not running", err=True)
             elif command == IPCCommand.ENGAGEMENT_RESUME:
                 typer.echo("Error: Cannot resume - engagement not paused", err=True)
             else:
                 typer.echo(f"Error: {error_msg}", err=True)
        else:
             typer.echo(f"Error: {error_msg}", err=True)
             
        raise typer.Exit(code=1)
        
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        typer.echo("Error: Daemon not running", err=True)
        raise typer.Exit(code=1)


@daemon_app.command("start")
def daemon_start(
    foreground: bool = typer.Option(
        False, "--foreground", "-f", help="Run daemon in foreground (for systemd)"
    ),
    # Config is handled by global callback, but we keep it here if user specifically
    # calls `daemon start -c ...` which might be intercepted by global callback anyway.
    # To be safe and compatible with old habit, we can leave it but it might be redundant.
    # Actually, typer parses options greedily. If we put it in callback, it handles it.
    # But `daemon start` specifically might want to RELOAD it if it wasn't passed globally?
    # No, global callback runs before command.
    # However, specialized `daemon start` logic re-reloading might be redundant but safe.
) -> None:
    """Start the Cyber-Red daemon."""
    # Check if daemon is already running (alive)
    socket_path = get_socket_path()
    if socket_path.exists():
        # Check if it's actually alive
        async def check_alive() -> bool:
            try:
                reader, writer = await asyncio.open_unix_connection(str(socket_path))
                writer.close()
                await writer.wait_closed()
                return True
            except (ConnectionRefusedError, OSError):
                return False

        if asyncio.run(check_alive()):
            typer.echo("Error: Daemon is already running", err=True)
            raise typer.Exit(code=1)
        else:
            log.warning("stale_socket_detected", path=str(socket_path))
            # DaemonServer will handle cleanup of the file itself if we proceed
    
    # Config already loaded by main callback if provided
    
    log.info("daemon_starting", foreground=foreground)
    
    # Import and run the daemon server
    from cyberred.daemon.server import run_daemon
    
    if foreground:
        typer.echo("Starting daemon in foreground...")
        asyncio.run(run_daemon(foreground=True))
    else:
        # For background mode, we'd fork or use systemd
        # For now, run in foreground
        typer.echo("Starting daemon...")
        asyncio.run(run_daemon(foreground=False))


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the Cyber-Red daemon gracefully."""
    socket_path = get_socket_path()
    pid_path = Path(get_settings().storage.base_path).expanduser() / "daemon.pid"
    
    # We can try to send stop command even if socket file check fails? No, need socket.
    if not socket_path.exists():
        typer.echo("Daemon not running")
        raise typer.Exit(code=1)
    
    async def send_stop() -> bool:
        # Use low-level call here because we want custom error handling/logic
        # or we could use _send_ipc_request? 
        # _send_ipc_request raises Exit on error.
        # Let's keep manual implementation for daemon control commands to be safe/granular
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            request = build_request(IPCCommand.DAEMON_STOP)
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            writer.close()
            await writer.wait_closed()
            return response.status == "ok"
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return False
    
    log.info("daemon_stopping")
    success = asyncio.run(send_stop())
    
    if success:
        typer.echo("Daemon stopping...", nl=False)
        # Verify shutdown
        import time
        # Fix: CLI Timeout (Review Finding #3)
        # Daemon allows up to 30s for graceful shutdown so we wait 40s to be safe
        max_retries = 400  # 40 seconds (0.1s * 400)
        for _ in range(max_retries):
            if not pid_path.exists() and not socket_path.exists():
                typer.echo(" Done.")
                return
            time.sleep(0.1)
        
        typer.echo(" Timeout awaiting shutdown.", err=True)
        # Still raise exit code 0 as request was sent, but warn user
    else:
        typer.echo("Failed to stop daemon (not responding)", err=True)
        raise typer.Exit(code=1)


@daemon_app.command("status")
def daemon_status() -> None:
    """Show the current daemon status."""
    pid_path = Path(get_settings().storage.base_path).expanduser() / "daemon.pid"
    
    # Use helper
    try:
        data = asyncio.run(_send_ipc_request(IPCCommand.SESSIONS_LIST))
        engagements = data.get("engagements", []) if data else []
        pid = pid_path.read_text().strip() if pid_path.exists() else "unknown"
        typer.echo(f"Daemon running (PID {pid}), {len(engagements)} active engagements")
    except typer.Exit:
        # Helper prints "Daemon not running" automatically for us?
        # Check helper: raises Exit(1) and prints Error. 
        # But status command usually prints "Daemon not running" without Error prefix if intended.
        # Let's override for status or just let it be.
        # The requirement was "Daemon not running".
        # Helper prints "Error: Daemon not running".
        # Re-implementing lightly to match exact output style if needed
        # But consistency is good.
        raise


@app.command()
def sessions() -> None:
    """List all engagements."""
    # Placeholder - actual implementation will query daemon via IPC
    try:
        data = asyncio.run(_send_ipc_request(IPCCommand.SESSIONS_LIST))
        engagements = data.get("engagements", []) if data else []
        typer.echo(f"{len(engagements)} engagements")
    except typer.Exit:
        raise


@app.command()
def attach(
    engagement_id: str = typer.Argument(..., help="Engagement ID to attach to"),
) -> None:
    """Attach TUI to a running engagement."""
    from cyberred.tui.daemon_client import (
        TUIClient,
        DaemonNotRunningError,
        DaemonConnectionError,
        EngagementError,
    )
    from cyberred.tui.app import CyberRedApp

    log.info("attaching", engagement_id=engagement_id)
    socket_path = get_socket_path()

    async def run_attached_tui() -> None:
        client = TUIClient()
        try:
            await client.connect(socket_path)

            # Verify engagement exists and is attachable by checking via IPC first
            # This gives us a nice error message before launching TUI
            response = await _send_ipc_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                {"engagement_id": engagement_id},
            )

            # Get subscription_id from response
            if response:
                sub_id = response.get("subscription_id")
                if sub_id:
                    # Detach immediately since we'll reattach in TUI
                    await _send_ipc_request(
                        IPCCommand.ENGAGEMENT_DETACH,
                        {"subscription_id": sub_id, "engagement_id": engagement_id},
                    )

            # Now launch TUI with the client
            app = CyberRedApp(daemon_client=client, engagement_id=engagement_id)
            await app.run_async()

        except DaemonNotRunningError:
            typer.echo("Error: Daemon not running", err=True)
            raise typer.Exit(code=1)
        except DaemonConnectionError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)
        except EngagementError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)
        finally:
            await client.close()

    asyncio.run(run_attached_tui())


@app.command()
def detach(
    engagement_id: str = typer.Argument(..., help="Engagement ID to detach from"),
) -> None:
    """Detach TUI from engagement (engagement continues running).

    Note: This command is primarily for programmatic use. In the TUI,
    use Ctrl+D or type 'detach' to disconnect.
    """
    log.info("detaching", engagement_id=engagement_id)
    asyncio.run(_send_ipc_request(IPCCommand.ENGAGEMENT_DETACH, {"engagement_id": engagement_id}))
    typer.echo(f"Detached from {engagement_id}")



@app.command("new")
def new_engagement(
    config: Path = typer.Option(
        ..., "--config", "-c", help="Path to engagement configuration file"
    ),
) -> None:
    """Start a new engagement."""
    if not config.exists():
        typer.echo(f"Error: Engagement config file '{config}' not found", err=True)
        raise typer.Exit(code=1)

    try:
        # Validate against EngagementConfig schema
        data = load_yaml_file(config)
        EngagementConfig(**data)
        log.info("engagement_config_valid", path=str(config))
    except (ConfigurationError, ValueError) as e:
        typer.echo(f"Error: Invalid engagement config: {e}", err=True)
        raise typer.Exit(code=1)

    log.info("new_engagement", config=str(config))
    # Placeholder - actual implementation in Story 2.6
    typer.echo(f"Starting engagement from {config}...")


@app.command()
def pause(
    engagement_id: str = typer.Argument(..., help="Engagement ID to pause"),
) -> None:
    """Pause a running engagement (hot state preservation)."""
    log.info("pausing", engagement_id=engagement_id)
    
    asyncio.run(_send_ipc_request(
        IPCCommand.ENGAGEMENT_PAUSE, 
        {"engagement_id": engagement_id}
    ))
    
    typer.echo(f"Engagement {engagement_id} paused (state preserved in memory)")


@app.command()
def resume(
    engagement_id: str = typer.Argument(..., help="Engagement ID to resume"),
) -> None:
    """Resume a paused engagement."""
    log.info("resuming", engagement_id=engagement_id)
    
    asyncio.run(_send_ipc_request(
        IPCCommand.ENGAGEMENT_RESUME, 
        {"engagement_id": engagement_id}
    ))
    
    typer.echo(f"Engagement {engagement_id} resumed")


@app.command("stop")
def stop_engagement(
    engagement_id: str = typer.Argument(..., help="Engagement ID to stop"),
) -> None:
    """Stop an engagement with checkpoint (cold state)."""
    log.info("stopping", engagement_id=engagement_id)
    
    async def _stop() -> dict:
        return await _send_ipc_request(
            IPCCommand.ENGAGEMENT_STOP,
            {"engagement_id": engagement_id}
        )
    
    result = asyncio.run(_stop())
    
    if result.get("error"):
        typer.echo(f"Error: {result.get('error')}", err=True)
        raise typer.Exit(1)
    
    checkpoint_path = result.get("checkpoint_path")
    typer.echo(f"Engagement {engagement_id} stopped (checkpoint saved)")
    if checkpoint_path:
        typer.echo(f"Checkpoint: {checkpoint_path}")


@daemon_app.command("install")
def daemon_install(
    user: str = typer.Option(
        "cyberred", "--user", "-u", help="Username to run the service as"
    ),
    no_enable: bool = typer.Option(
        False, "--no-enable", help="Don't enable service to start on boot"
    ),
    create_user: bool = typer.Option(
        False, "--create-user", help="Create service user if it doesn't exist"
    ),
) -> None:
    """Install Cyber-Red as a systemd service (requires root)."""
    import os
    import subprocess
    from cyberred.daemon.systemd import (
        generate_service_file,
        write_service_file,
        create_service_user,
        ensure_storage_directory,
        reload_systemd,
        enable_service,
        DEFAULT_SERVICE_PATH,
    )

    # Check root privileges
    if os.geteuid() != 0:
        typer.echo("Error: This command requires root privileges", err=True)
        raise typer.Exit(code=1)

    log.info("daemon_install_starting", user=user, no_enable=no_enable, create_user=create_user)

    # Handle user creation
    if create_user:
        try:
            created = create_service_user(user)
            if created:
                typer.echo(f"Created service user: {user}")
            else:
                typer.echo(f"Service user already exists: {user}")
        except subprocess.CalledProcessError as e:
            typer.echo(f"Error creating user: {e}", err=True)
            raise typer.Exit(code=1)

    # Ensure storage directory exists with correct ownership
    storage_path = Path(get_settings().storage.base_path).expanduser()
    # For service user, use /var/lib/cyber-red instead of ~/.cyber-red
    if user != "root":
        service_storage = Path(f"/var/lib/cyber-red")
    else:
        service_storage = storage_path

    try:
        ensure_storage_directory(service_storage, user)
        typer.echo(f"Storage directory configured: {service_storage}")
    except subprocess.CalledProcessError as e:
        typer.echo(f"Error configuring storage directory: {e}", err=True)
        raise typer.Exit(code=1)

    # Generate and write service file
    try:
        content = generate_service_file(user=user)
        write_service_file(content)
        typer.echo(f"Service file installed: {DEFAULT_SERVICE_PATH}")
    except PermissionError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except OSError as e:
        typer.echo(f"Error writing service file: {e}", err=True)
        raise typer.Exit(code=1)

    # Reload systemd
    try:
        reload_systemd()
        typer.echo("Reloaded systemd configuration")
    except subprocess.CalledProcessError as e:
        typer.echo(f"Error reloading systemd: {e}", err=True)
        raise typer.Exit(code=1)

    # Enable service (unless --no-enable)
    if not no_enable:
        try:
            enable_service()
            typer.echo("Service enabled to start on boot")
        except subprocess.CalledProcessError as e:
            typer.echo(f"Error enabling service: {e}", err=True)
            raise typer.Exit(code=1)

    typer.echo("")
    typer.echo("✅ Cyber-Red daemon installed successfully!")
    typer.echo("")
    typer.echo("Next steps:")
    typer.echo("  systemctl start cyber-red    # Start the daemon")
    typer.echo("  systemctl status cyber-red   # Check status")
    typer.echo("  journalctl -u cyber-red -f   # Follow logs")


@daemon_app.command("uninstall")
def daemon_uninstall() -> None:
    """Uninstall Cyber-Red systemd service (requires root)."""
    import os
    import subprocess
    from cyberred.daemon.systemd import (
        stop_service,
        disable_service,
        remove_service_file,
        reload_systemd,
        DEFAULT_SERVICE_PATH,
    )

    # Check root privileges
    if os.geteuid() != 0:
        typer.echo("Error: This command requires root privileges", err=True)
        raise typer.Exit(code=1)

    log.info("daemon_uninstall_starting")

    # Stop service if running
    typer.echo("Stopping service...")
    stop_service()

    # Disable service
    try:
        disable_service()
        typer.echo("Service disabled")
    except subprocess.CalledProcessError:
        # Service might not be enabled, that's OK
        pass

    # Remove service file
    try:
        remove_service_file()
        typer.echo(f"Removed service file: {DEFAULT_SERVICE_PATH}")
    except FileNotFoundError:
        typer.echo("Service file not found (already removed)")

    # Reload systemd
    try:
        reload_systemd()
        typer.echo("Reloaded systemd configuration")
    except subprocess.CalledProcessError as e:
        typer.echo(f"Warning: Error reloading systemd: {e}", err=True)

    typer.echo("")
    typer.echo("✅ Cyber-Red daemon uninstalled successfully!")


@daemon_app.command("logs")
def daemon_logs(
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Follow log output (like tail -f)"
    ),
    lines: int = typer.Option(
        50, "--lines", "-n", help="Number of lines to show"
    ),
) -> None:
    """View Cyber-Red daemon logs from journald."""
    import subprocess
    import sys

    cmd = ["journalctl", "-u", "cyber-red"]

    if follow:
        cmd.append("-f")
    else:
        cmd.extend(["-n", str(lines)])

    log.debug("daemon_logs_command", cmd=cmd)

    try:
        # Use subprocess.run with inherited stdout/stderr for interactive output
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)
    except FileNotFoundError:
        typer.echo("Error: journalctl not found. Is systemd installed?", err=True)
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        pass


if __name__ == "__main__":  # pragma: no cover
    app()

